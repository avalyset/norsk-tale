#!/usr/bin/env python3
"""norsk-tale kalibreringsrigg — lokal nettleserserver for å måle diktering for én
taler og én mikrofon.

Bygger på mønsteret fra NORSKRIBERs transkriber.py (http.server, opptak i
nettleseren med MediaRecorder, ffmpeg til 16 kHz mono wav), med strammere
grenser:

  - binder bare 127.0.0.1, tilfeldig port
  - tilfeldig token i URL-en, påkrevd på alle forespørsler (feil token → 404)
  - Host må være 127.0.0.1/localhost med riktig port (mot DNS-rebinding)
  - Origin påkrevd og kontrollert på alle POST; ingen CORS-hoder
  - Content-Security-Policy som forbyr eksterne ressurser
  - stopper etter 30 min uten forespørsler, eller ved «Avslutt»

Opptak og resultater lagres under ~/norsk-tale-opptak/<runde>/, aldri i repoet.
Transkripsjon startes bare når brukeren ber om det. Bare standardbiblioteket,
pluss ffmpeg og whisper.cpp via kjernen.
"""
import argparse
import dataclasses
import datetime
import html
import http.server
import json
import pathlib
import re
import secrets
import sys
import tempfile
import threading
import time
import urllib.parse

HER = pathlib.Path(__file__).resolve().parent
ROT = HER.parent
sys.path.insert(0, str(HER))
sys.path.insert(0, str(ROT / "kjerne"))
import aggreger  # noqa: E402
import kjerne  # noqa: E402
import score  # noqa: E402

PLUGIN_VERSJON = json.loads((ROT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
MANUS = HER / "manus_v1.tsv"
SIDE = HER / "side.html"
REGIONER = ["Østlandet", "Sørlandet", "Vestlandet", "Trøndelag", "Nord-Norge", "annet"]
KILDER = ["morsmål", "imitert"]
MALFORMER = ["nb", "nn"]
MODUS = ["fullt", "dialekt"]
TESTSETNING = "Dette er bare en test av mikrofonen, og den teller ikke med i resultatet."
MAKS_OPPLASTING = 50 * 1024 * 1024
RUNDE_ID = re.compile(r"^runde-\d{8}-\d{6}-[0-9a-f]{6}$")
CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
       "connect-src 'self'; media-src 'self' blob:; img-src 'self' data:; base-uri 'none'; "
       "form-action 'none'; frame-ancestors 'none'")


class Feil(Exception):
    def __init__(self, status, melding):
        super().__init__(melding)
        self.status = status


class Rigg:
    def __init__(self, opptaksrot, konfig, inaktiv_s=1800):
        self.rot = pathlib.Path(opptaksrot).expanduser()
        self.konfig = konfig
        self.manus = score.les_setninger(MANUS)
        self.fasit = {s["id"]: s for s in self.manus}
        self.token = secrets.token_urlsafe(24)
        self.inaktiv_s = inaktiv_s
        self.sist = time.monotonic()
        self.jobb = {"kjorer": False, "runde": None, "ferdig": 0, "totalt": 0, "feil": None}
        self.las = threading.Lock()
        self.port = None

    # ------------------------------------------------------------------ runder
    def runde_dir(self, runde_id):
        if not runde_id or not RUNDE_ID.match(runde_id):
            raise Feil(400, "Ugyldig runde.")
        d = self.rot / runde_id
        if not (d / "runde.json").is_file():
            raise Feil(404, "Fant ikke runden.")
        return d

    def les_runde(self, runde_id):
        return json.loads((self.runde_dir(runde_id) / "runde.json").read_text(encoding="utf-8"))

    def skriv_runde(self, runde):
        d = self.rot / runde["id"]
        (d / "runde.json").write_text(json.dumps(runde, ensure_ascii=False, indent=2), encoding="utf-8")

    def ny_runde(self, data):
        modus = data.get("modus")
        if modus not in MODUS:
            raise Feil(400, "Velg modus: fullt manus eller dialektrunde.")
        region = data.get("dialektregion") or None
        kilde = data.get("dialektkilde") or None
        malform = data.get("malform") or None
        if region is not None and region not in REGIONER:
            raise Feil(400, "Ukjent dialektregion.")
        if region is not None and kilde not in KILDER:
            raise Feil(400, "Dialektkilde (morsmål eller imitert) er påkrevd når region er valgt.")
        if region is None and kilde is not None:
            raise Feil(400, "Dialektkilde gir bare mening sammen med en region.")
        if malform is not None and malform not in MALFORMER:
            raise Feil(400, "Ukjent målform.")
        naa = datetime.datetime.now()
        runde = {"id": f"runde-{naa:%Y%m%d-%H%M%S}-{secrets.token_hex(3)}", "modus": modus,
                 "dialektregion": region, "dialektkilde": kilde, "malform": malform,
                 "opprettet": naa.isoformat(timespec="seconds"), "hoppet": []}
        (self.rot / runde["id"] / "opptak").mkdir(parents=True)
        self.skriv_runde(runde)
        return runde

    def ider(self, runde):
        return [s["id"] for s in self.manus if runde["modus"] == "fullt" or s["dialektutvalg"]]

    def wav(self, runde_id, manus_id):
        if manus_id not in self.fasit:
            raise Feil(400, "Ukjent manus-id.")
        return self.runde_dir(runde_id) / "opptak" / f"{manus_id}.wav"

    def status(self, runde_id):
        runde = self.les_runde(runde_id)
        rader = []
        for i in self.ider(runde):
            rader.append({"id": i, "opptak": self.wav(runde_id, i).is_file(), "hoppet": i in runde["hoppet"]})
        return {"runde": runde, "rader": rader,
                "har_resultat": (self.runde_dir(runde_id) / "resultater.json").is_file()}

    def runder(self):
        ut = []
        if self.rot.is_dir():
            for d in sorted(self.rot.iterdir()):
                if RUNDE_ID.match(d.name) and (d / "runde.json").is_file():
                    r = json.loads((d / "runde.json").read_text(encoding="utf-8"))
                    r["antall_opptak"] = len(list((d / "opptak").glob("*.wav")))
                    ut.append(r)
        return ut

    # ----------------------------------------------------------------- opptak
    def lagre_opptak(self, runde_id, manus_id, data, ctype):
        mal = self.wav(runde_id, manus_id)
        endelse = ".webm" if "webm" in ctype else ".mp4" if "mp4" in ctype else ".ogg" if "ogg" in ctype else ".lyd"
        with tempfile.TemporaryDirectory(prefix="norsk-tale-") as tmp:
            kilde = pathlib.Path(tmp) / f"inn{endelse}"
            kilde.write_bytes(data)
            ut = pathlib.Path(tmp) / "ut.wav"
            kjerne.til_wav(kilde, ut)
            ut.replace(mal)
        runde = self.les_runde(runde_id)
        if manus_id in runde["hoppet"]:
            runde["hoppet"].remove(manus_id)
            self.skriv_runde(runde)
        return {"ok": True, "bytes": mal.stat().st_size}

    def hopp(self, runde_id, manus_id):
        runde = self.les_runde(runde_id)
        if manus_id not in self.fasit:
            raise Feil(400, "Ukjent manus-id.")
        if manus_id not in runde["hoppet"]:
            runde["hoppet"].append(manus_id)
            self.skriv_runde(runde)
        return {"ok": True}

    def slett_opptak(self, runde_id=None):
        """Sletter lydfilene riggen selv har laget: <runde>/opptak/<manus-id>.wav."""
        runder = [runde_id] if runde_id else [r["id"] for r in self.runder()]
        slettet = 0
        for rid in runder:
            for s in self.manus:
                f = self.wav(rid, s["id"])
                if f.is_file():
                    f.unlink()
                    slettet += 1
        return {"ok": True, "slettet": slettet}

    # ------------------------------------------------------------ transkripsjon
    def start_transkripsjon(self, runde_id, kjor=None):
        self.runde_dir(runde_id)
        with self.las:
            if self.jobb["kjorer"]:
                raise Feil(409, "En transkripsjon kjører allerede.")
            self.jobb = {"kjorer": True, "runde": runde_id, "ferdig": 0, "totalt": 0, "feil": None}
        t = threading.Thread(target=self._transkriber, args=(runde_id, kjor or kjerne.transkriber), daemon=True)
        t.start()
        return dict(self.jobb)

    def _transkriber(self, runde_id, kjor):
        try:
            oppsett = kjerne.standard_oppsett(**self.konfig)
            sha = kjerne.verifiser_modell(oppsett.modell, oppsett.sha256)
            runde = self.les_runde(runde_id)
            ider = [i for i in self.ider(runde) if self.wav(runde_id, i).is_file()]
            plan = []
            for i in ider:
                # nn-setninger kjøres både med nb og nn, så målformfeil skilles fra hørselsfeil
                for mf in (["nb", "nn"] if self.fasit[i]["malform"] == "nn" else ["nb"]):
                    for vok in ("med", "uten"):
                        plan.append((i, mf, vok))
            self.jobb["totalt"] = len(plan)
            rader = {}
            for i, mf, vok in plan:
                o = dataclasses.replace(oppsett, malform=mf,
                                        vokabular=oppsett.vokabular if vok == "med" else ())
                r = kjor(self.wav(runde_id, i), o, sha=sha)
                rad = rader.setdefault(i, {"manus_id": i, "fasit": self.fasit[i]["setning"], "varianter": {}})
                rad["varianter"][f"{mf}/{vok}"] = {
                    "ra": {"utdata": r["verbatim"], "scoring": score.score_setning(self.fasit[i], r["verbatim"])},
                    "korrigert": {"utdata": r["korrigert"],
                                  "scoring": score.score_setning(self.fasit[i], r["korrigert"])},
                }
                self.jobb["ferdig"] += 1
                self.sist = time.monotonic()
            resultat = {"modell": {"modellvalg": oppsett.modellvalg, "modell_sha256": sha,
                                   "kjerne_versjon": kjerne.VERSJON, "norsk_tale_versjon": PLUGIN_VERSJON},
                        "transkribert": datetime.datetime.now().isoformat(timespec="seconds"),
                        "rader": list(rader.values())}
            (self.runde_dir(runde_id) / "resultater.json").write_text(
                json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self.jobb["feil"] = str(e)
        finally:
            self.jobb["kjorer"] = False
            self.sist = time.monotonic()

    # ------------------------------------------------------------- resultater
    def resultater(self, runde_id):
        f = self.runde_dir(runde_id) / "resultater.json"
        if not f.is_file():
            raise Feil(404, "Runden er ikke transkribert ennå.")
        return json.loads(f.read_text(encoding="utf-8"))

    def rapport(self, runde_id, vokabular="med", tekst="korrigert"):
        """Lokal rapport for taleren: tallene, og hver bom ordrett. Teksten blir
        på maskinen; den er ikke med i bidraget."""
        runde = self.les_runde(runde_id)
        res = self.resultater(runde_id)
        tabell = aggreger.aggreger([("denne taleren", self.bidrag(runde_id))], vokabular, tekst, min_talere=1)
        bom = []
        for rad in res["rader"]:
            s = self.fasit[rad["manus_id"]]
            for nokkel, v in sorted(rad["varianter"].items()):
                mf_valgt, vok = nokkel.split("/")
                if vok != vokabular or tekst not in v:
                    continue
                sc = v[tekst]["scoring"]
                for b in sc["bom"]:
                    bom.append({"manus_id": rad["manus_id"], "klasse": s["klasse"], "malform": s["malform"],
                                "malform_valgt": mf_valgt, **b})
                if sc["malform"]["funn"]:
                    bom.append({"manus_id": rad["manus_id"], "klasse": s["klasse"], "malform": s["malform"],
                                "malform_valgt": mf_valgt, "type": "målform",
                                "fasit": s["malform"], "utdata": v[tekst]["utdata"]})
        return {"runde": {k: runde[k] for k in ("id", "modus", "dialektregion", "dialektkilde", "malform", "opprettet")},
                "modell": res["modell"], "vokabular": vokabular, "tekst": tekst, "tabell": tabell, "bom": bom,
                "merknad": ("Én taler og én mikrofon. WER/CER etter NB-Whisper-prosjektets normalisering. "
                            "Feiltellingene er feilanalyse, ikke en score. Dette er et brukerverktøy, ikke en "
                            "benchmark. Ingen lyd er med.")}

    def bidrag(self, runde_id):
        """Det som kan deles: KUN tall (WER/CER-tellere, feiltelling per klasse,
        antall talere) og etiketter (region, dialektkilde, målform, modell/versjon).
        Ingen lyd og ingen tekst. Rulles opp til region under 3 talere."""
        runde = self.les_runde(runde_id)
        res = self.resultater(runde_id)
        celler = aggreger.celler_for_runde(res, self.fasit)
        return aggreger.lag_bidrag(celler, res["modell"], runde["dialektregion"], runde["dialektkilde"],
                                   runde["malform"], manus=MANUS.stem)

    def lagre_bidrag(self, runde_id):
        innhold = self.bidrag(runde_id)
        d = self.rot / "bidrag"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"bidrag-{runde_id}.json"
        f.write_text(json.dumps(innhold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"ok": True, "fil": str(f)}


def rapport_html(rapport):
    e = html.escape
    rader = []
    for r in rapport["tabell"]:
        for kilde, c in r["kilder"].items():
            f = c["feil"]
            rader.append(f"<tr><td>{e(r['klasse'])}</td><td>{e(r['malform'])}</td><td>{e(r['malform_valgt'])}</td>"
                         f"<td>{c['n_setninger']}</td><td>{c['wer']}</td><td>{c['cer']}</td>"
                         f"<td>{f['nektelse']['bom']}/{f['nektelse']['av']}</td>"
                         f"<td>{f['tall']['bom']}/{f['tall']['av']}</td><td>{f['navn']['bom']}/{f['navn']['av']}</td>"
                         f"<td>{f['første ord']['bom']}/{f['første ord']['av']}</td><td>{f['målform']}</td></tr>")
    for ex in rapport.get("bom", []):
        rader.append(f"<tr class='bom'><td colspan='11'>{e(ex['manus_id'])} ({e(ex['malform'])}, whisper "
                     f"{e(ex['malform_valgt'])}) bom {e(ex['type'])}: fasit «{e(ex['fasit'])}» — "
                     f"utdata «{e(ex['utdata'])}»</td></tr>")
    ru = rapport["runde"]
    return ("<!doctype html><html lang='no'><meta charset='utf-8'><title>norsk-tale kalibrering</title>"
            "<style>body{font:14px system-ui,sans-serif;margin:24px}td,th{border:1px solid #ccc;padding:4px 6px}"
            "table{border-collapse:collapse}.bom td{color:#a00;border-top:none}</style>"
            f"<h1>Kalibrering {e(ru['id'])}</h1><p>Modus {e(ru['modus'])}, region {e(str(ru['dialektregion']))}, "
            f"kilde {e(str(ru['dialektkilde']))}, målform {e(str(ru['malform']))}. Modell "
            f"{e(rapport['modell']['modellvalg'])}, vokabular {e(rapport['vokabular'])}, tekst {e(rapport['tekst'])}.</p>"
            f"<p>{e(rapport['merknad'])}</p><table><tr><th>klasse</th><th>målform</th><th>whisper</th><th>n</th>"
            "<th>WER</th><th>CER</th><th>nektelse-bom</th><th>tall-bom</th><th>navn-bom</th><th>første ord</th>"
            "<th>målformfeil</th></tr>" + "".join(rader) + "</table></html>")


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    rigg: Rigg = None

    def log_message(self, fmt, *args):
        pass

    # --------------------------------------------------------------- vakter
    def _vakt(self, metode):
        r = self.rigg
        vert = self.headers.get("Host", "")
        if vert not in (f"127.0.0.1:{r.port}", f"localhost:{r.port}"):
            raise Feil(403, "Feil Host.")
        sti = urllib.parse.urlsplit(self.path)
        deler = sti.path.split("/", 2)
        if len(deler) < 2 or not secrets.compare_digest(deler[1], r.token):
            raise Feil(404, "Ikke funnet.")
        if metode == "POST":
            opphav = self.headers.get("Origin")
            if opphav not in (f"http://127.0.0.1:{r.port}", f"http://localhost:{r.port}"):
                raise Feil(403, "Feil eller manglende Origin.")
        r.sist = time.monotonic()
        rest = "/" + (deler[2] if len(deler) > 2 else "")
        return rest, dict(urllib.parse.parse_qsl(sti.query))

    def _svar(self, status, kropp, ctype="application/json; charset=utf-8", ekstra=None):
        if isinstance(kropp, (dict, list)):
            kropp = json.dumps(kropp, ensure_ascii=False).encode("utf-8")
        elif isinstance(kropp, str):
            kropp = kropp.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(kropp)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (ekstra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(kropp)

    def _les(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAKS_OPPLASTING:
            raise Feil(413, "Opptaket er for stort.")
        data = bytearray()
        while len(data) < n:
            bit = self.rfile.read(min(65536, n - len(data)))
            if not bit:
                break
            data.extend(bit)
        return bytes(data)

    def _json(self):
        try:
            return json.loads(self._les() or b"{}")
        except json.JSONDecodeError:
            raise Feil(400, "Ugyldig JSON.")

    # -------------------------------------------------------------- ruter
    def do_GET(self):
        try:
            sti, q = self._vakt("GET")
            r = self.rigg
            if sti == "/":
                side = SIDE.read_text(encoding="utf-8").replace("__TOKEN__", r.token)
                return self._svar(200, side, "text/html; charset=utf-8")
            if sti == "/api/oppsett":
                return self._svar(200, {
                    "manus": [{k: s[k] for k in ("id", "malform", "klasse", "setning", "dialektutvalg")} for s in r.manus],
                    "regioner": REGIONER, "kilder": KILDER, "malformer": MALFORMER, "testsetning": TESTSETNING,
                    "runder": r.runder(), "opptaksrot": str(r.rot), "modellvalg": r.konfig.get("modellvalg") or "large"})
            if sti == "/api/runde":
                return self._svar(200, r.status(q.get("runde")))
            if sti == "/api/opptak":
                f = r.wav(q.get("runde"), q.get("id"))
                if not f.is_file():
                    raise Feil(404, "Ikke tatt opp.")
                return self._svar(200, f.read_bytes(), "audio/wav")
            if sti == "/api/transkriber":
                return self._svar(200, dict(r.jobb))
            if sti == "/api/resultat":
                return self._svar(200, r.rapport(q.get("runde"), q.get("vokabular", "med"), q.get("tekst", "korrigert")))
            if sti == "/api/rapport":
                rap = r.rapport(q.get("runde"), q.get("vokabular", "med"), q.get("tekst", "korrigert"))
                navn = f"norsk-tale-rapport-{rap['runde']['id']}"
                if q.get("format") == "html":
                    return self._svar(200, rapport_html(rap), "text/html; charset=utf-8",
                                      {"Content-Disposition": f'attachment; filename="{navn}.html"'})
                return self._svar(200, rap, ekstra={"Content-Disposition": f'attachment; filename="{navn}.json"'})
            if sti == "/api/bidrag":
                return self._svar(200, r.bidrag(q.get("runde")))
            raise Feil(404, "Ikke funnet.")
        except Feil as e:
            self._svar(e.status, {"feil": str(e)})
        except Exception as e:
            self._svar(500, {"feil": f"{type(e).__name__}: {e}"})

    def do_POST(self):
        try:
            sti, q = self._vakt("POST")
            r = self.rigg
            if sti == "/api/runde":
                return self._svar(200, r.ny_runde(self._json()))
            if sti == "/api/opptak":
                data = self._les()
                if not data:
                    raise Feil(400, "Tomt opptak.")
                return self._svar(200, r.lagre_opptak(q.get("runde"), q.get("id"), data,
                                                      self.headers.get("Content-Type", "")))
            if sti == "/api/hopp":
                return self._svar(200, r.hopp(q.get("runde"), q.get("id")))
            if sti == "/api/transkriber":
                return self._svar(200, r.start_transkripsjon(q.get("runde")))
            if sti == "/api/bidrag":
                return self._svar(200, r.lagre_bidrag(q.get("runde")))
            if sti == "/api/slett":
                return self._svar(200, r.slett_opptak(q.get("runde") or None))
            if sti == "/api/avslutt":
                self._svar(200, {"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            raise Feil(404, "Ikke funnet.")
        except Feil as e:
            self._svar(e.status, {"feil": str(e)})
        except kjerne.KjerneFeil as e:
            self._svar(500, {"feil": str(e)})
        except Exception as e:
            self._svar(500, {"feil": f"{type(e).__name__}: {e}"})


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def vakt_inaktivitet(server, rigg, intervall=1.0):
    while True:
        time.sleep(intervall)
        if not rigg.jobb["kjorer"] and time.monotonic() - rigg.sist > rigg.inaktiv_s:
            server.shutdown()
            return


def main(argv=None):
    ap = argparse.ArgumentParser(description="norsk-tale kalibreringsrigg (lokal nettleserserver).")
    ap.add_argument("--opptak", default="~/norsk-tale-opptak", help="Rotkatalog for runder (utenfor repoet).")
    ap.add_argument("--modellvalg", default="")
    ap.add_argument("--modell", default="")
    ap.add_argument("--whisper", default="")
    ap.add_argument("--inaktiv-sekunder", type=float, default=1800)
    a = ap.parse_args(argv)
    konfig = {"modellvalg": a.modellvalg or None, "modell": a.modell or None, "whisper": a.whisper or None}
    rigg = Rigg(a.opptak, konfig, a.inaktiv_sekunder)
    rigg.rot.mkdir(parents=True, exist_ok=True)
    Handler.rigg = rigg
    server = Server(("127.0.0.1", 0), Handler)
    rigg.port = server.server_address[1]
    threading.Thread(target=vakt_inaktivitet, args=(server, rigg), daemon=True).start()
    print(json.dumps({"type": "klar", "url": f"http://127.0.0.1:{rigg.port}/{rigg.token}/",
                      "opptak": str(rigg.rot)}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        print(json.dumps({"type": "stoppet"}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
