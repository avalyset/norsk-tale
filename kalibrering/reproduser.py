#!/usr/bin/env python3
"""norsk-tale — standardkalibrering prereg-v1: ett inngangspunkt (METHOD.md).

  verifiser    SHA256 for modeller, whisper-cli, dataarkiver, id-lister og kode
               mot manifest.json; avvik = stopp (kode 2) med filnavn
  utvalg       genererer id-listene fra data etter utvalgsregelen; med --sjekk
               sammenlignes de med de frosne (avvik = kode 2)
  determinisme 5 FLEURS-ytringer, medium, nb, prompt på, to ganger; skriver
               bare SHA256 av utdata (kode 6 hvis ikke byte-identisk)
  kjor         hele cellematrisen, medium før large, gjenopptakbar; stopper
               rolig med kode 7 når Ollama har en modell lastet
  scor         WER/CER med bootstrap-KI, nektelser, markører og kjøretid;
               bare tall, ingen tekst fra datasettene
  miljo        miljødump (OS, CPU/GPU, Python og pakker, whisper-cli, ffmpeg)

Stier kommer bare fra miljøet: NORSK_TALE_DATA, NORSK_TALE_MODELLER,
NORSK_TALE_ARBEID, NORSK_TALE_WHISPER_CLI. Kjøringen skal gå under vakt.py.
"""
import argparse
import dataclasses
import hashlib
import json
import os
import pathlib
import platform
import random
import re
import subprocess
import sys
import time

HER = pathlib.Path(__file__).resolve().parent
ROT = HER.parent
sys.path.insert(0, str(HER))
sys.path.insert(0, str(ROT / "kjerne"))
import feilanalyse  # noqa: E402
import kjerne  # noqa: E402
import norm  # noqa: E402
import sett  # noqa: E402

MANIFEST = HER / "manifest.json"
MARKOR = re.compile(r"⟦(.*?) → .*?\?⟧")


class Avvik(SystemExit):
    def __init__(self, melding):
        print(f"AVVIK: {melding}", file=sys.stderr)
        super().__init__(2)


# ------------------------------------------------------------------ oppsett
def les_manifest(sti=MANIFEST):
    return json.loads(pathlib.Path(sti).read_text(encoding="utf-8"))


def sti_fra_miljo(navn):
    verdi = os.environ.get(navn)
    if not verdi:
        raise SystemExit(f"Miljøvariabelen {navn} mangler (se manifest.json → stier).")
    return kjerne.krev_montert(verdi)


def sha256(sti):
    h = hashlib.sha256()
    with open(sti, "rb") as fh:
        for blokk in iter(lambda: fh.read(8 << 20), b""):
            h.update(blokk)
    return h.hexdigest()


def sha_tekst(tekst):
    return hashlib.sha256(tekst.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- verifiser
def verifiser(m, data=True, modeller=True):
    """Alle SHA-er i manifestet. Stopper ved første avvik."""
    for rel, forventet in m["kode_sha256"].items():
        if sha256(ROT / rel) != forventet:
            raise Avvik(f"kode {rel} er endret siden frysen")
    for navn, s in m["sett"].items():
        liste = ROT / s["idliste"]
        if not liste.is_file() or sha256(liste) != s["idliste_sha256"]:
            raise Avvik(f"id-listen {s['idliste']} mangler eller er endret")
    if modeller:
        mappe = sti_fra_miljo("NORSK_TALE_MODELLER")
        for navn, mod in m["modeller"].items():
            f = mappe / mod["fil"]
            if not f.is_file() or f.stat().st_size != mod["bytes"] or sha256(f) != mod["sha256"]:
                raise Avvik(f"modell {f.name} avviker")
        cli = sti_fra_miljo("NORSK_TALE_WHISPER_CLI")
        if sha256(cli) != m["whisper_cpp"]["cli_sha256"]:
            raise Avvik(f"whisper-cli {cli} avviker fra frosset binær")
        for navn, forventet in m["whisper_cpp"]["bibliotek_sha256"].items():
            f = cli.parent / navn
            if not f.is_file() or sha256(f) != forventet:
                raise Avvik(f"whisper.cpp-biblioteket {navn} mangler eller avviker")
    if data:
        rot = sti_fra_miljo("NORSK_TALE_DATA")
        for navn, s in m["sett"].items():
            for rel, forventet in s["filer"].items():
                f = rot / rel
                if not f.is_file() or sha256(f) != forventet:
                    raise Avvik(f"datafil {rel} mangler eller avviker")
    return True


# ------------------------------------------------------------------- utvalg
def trekk(rader, regel, seed):
    """Sorterte id-er; strata i sortert rekkefølge med én Random-instans."""
    ider = [r.id for r in rader]
    if len(set(ider)) != len(ider):
        raise Avvik("id-ene i settet er ikke unike")
    rng = random.Random(seed)
    strata = {}
    for r in rader:
        strata.setdefault(r.stratum, []).append(r.id)
    valgt = []
    for s in sorted(strata):
        pool = sorted(strata[s])
        n = regel.get("n_per_stratum", {}).get(s, regel.get("n"))
        if n is None or n == "alle":
            valgt += pool
        else:
            if n > len(pool):
                raise Avvik(f"stratum {s!r}: n={n} > {len(pool)} kvalifiserte")
            valgt += rng.sample(pool, n)
    return sorted(valgt)


def idliste_tekst(navn, s, ider, ute, seed):
    return (f"# prereg-v1 id-liste for {navn}. Bare id-er; ingen lyd eller tekst fra datasettet.\n"
            f"# regel={json.dumps(s['utvalg'], ensure_ascii=False, sort_keys=True)} seed={seed} n={len(ider)}\n"
            f"# utelukket før utvalget: {json.dumps(ute, sort_keys=True)}\n"
            + "\n".join(ider) + "\n")


def les_idliste(sti):
    return [ln.strip() for ln in pathlib.Path(sti).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")]


def utvalg(m, sjekk=False, bare=None):
    rot = sti_fra_miljo("NORSK_TALE_DATA")
    ut = {}
    for navn, s in m["sett"].items():
        if bare and navn not in bare:
            continue
        rader, ute = sett.SETT[navn][0](rot)
        ider = trekk(rader, s["utvalg"], m["seed"])
        tekst = idliste_tekst(navn, s, ider, ute, m["seed"])
        liste = ROT / s["idliste"]
        if sjekk:
            if not liste.is_file() or liste.read_text(encoding="utf-8") != tekst:
                raise Avvik(f"id-listen for {navn} kan ikke regenereres byte-identisk fra data")
        else:
            liste.parent.mkdir(parents=True, exist_ok=True)
            liste.write_text(tekst, encoding="utf-8")
        ut[navn] = {"n": len(ider), "utelukket_for_utvalg": ute, "sha256": sha_tekst(tekst)}
    return ut


# ------------------------------------------------------------------ kjøring
def ollama_fri():
    try:
        ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=20).stdout.splitlines()[1:]
    except (OSError, subprocess.TimeoutExpired):
        ps = []
    insp = subprocess.run(["pgrep", "-f", "inspect eval.*--model ollama/"], capture_output=True).returncode == 0
    return not [ln for ln in ps if ln.strip()] and not insp


def oppsett_for(m, modellvalg, malform, prompt):
    mod = m["modeller"][modellvalg]
    o = kjerne.standard_oppsett(modellvalg=modellvalg,
                                modell=str(sti_fra_miljo("NORSK_TALE_MODELLER") / mod["fil"]),
                                whisper=str(sti_fra_miljo("NORSK_TALE_WHISPER_CLI")), malform=malform)
    if o.sha256 != mod["sha256"]:
        raise Avvik(f"kjerne/modeller.json og manifestet er uenige om {modellvalg}")
    return o if prompt == "pa" else dataclasses.replace(o, vokabular=())


def kjor_en(lyd, o, sha, gjentak):
    """Én ytring i én celle. Returnerer et resultatobjekt (status ok/feil/tidsavbrudd)."""
    t = time.monotonic()
    for forsok in range(gjentak + 1):
        try:
            r = kjerne.transkriber(lyd, o, sha=sha)
            return {"status": "ok", "ra": r["verbatim"], "korrigert": r["korrigert"],
                    "vegg_s": round(time.monotonic() - t, 3), "forsok": forsok + 1}
        except kjerne.Tidsavbrudd as e:
            return {"status": "tidsavbrudd", "melding": str(e)[:200], "vegg_s": round(time.monotonic() - t, 3)}
        except kjerne.KjerneFeil as e:
            siste = str(e)[:300]
    return {"status": "feil", "melding": siste, "vegg_s": round(time.monotonic() - t, 3), "forsok": gjentak + 1}


def resultatfil(arbeid, navn, modellvalg):
    return arbeid / "resultater" / f"{navn}.{modellvalg}.jsonl"


def ferdige(fil):
    gjort = set()
    if fil.exists():
        for ln in fil.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                d = json.loads(ln)
                gjort.add((d["id"], d["malform"], d["prompt"]))
    return gjort


def lyd_for(m, navn, ider, arbeid):
    mappe = arbeid / "lyd" / navn
    kart = arbeid / "lyd" / f"{navn}.json"
    if kart.exists():
        lyd = {k: pathlib.Path(v) for k, v in json.loads(kart.read_text(encoding="utf-8")).items()}
        if set(lyd) <= set(ider) and all(p.is_file() for p in lyd.values()) and len(lyd) == len(ider):
            return lyd
    lyd = sett.SETT[navn][1](sti_fra_miljo("NORSK_TALE_DATA"), ider, mappe)
    kart.parent.mkdir(parents=True, exist_ok=True)
    kart.write_text(json.dumps({k: str(v) for k, v in sorted(lyd.items())}), encoding="utf-8")
    return lyd


def kjor(m, sjekk_hver=25, bare_sett=None, bare_modell=None, kjor_en=kjor_en):
    arbeid = sti_fra_miljo("NORSK_TALE_ARBEID") / m["versjon"]
    (arbeid / "resultater").mkdir(parents=True, exist_ok=True)
    kjerne.TIDSGRENSE_S = m["tidsgrense_s"]
    os.environ["NORSK_TALE_WHISPER_ARGS"] = m["whisper_cpp"]["ekstra_args"]
    teller = 0
    for modellvalg in m["modellrekkefolge"]:
        if bare_modell and modellvalg != bare_modell:
            continue
        sha = None
        for navn, s in m["sett"].items():
            if bare_sett and navn not in bare_sett:
                continue
            ider = les_idliste(ROT / s["idliste"])
            fil = resultatfil(arbeid, navn, modellvalg)
            gjort = ferdige(fil)
            celler = [(mf, p) for mf in s["malformer"] for p in s["prompt"]]
            if all((i, mf, p) in gjort for i in ider for mf, p in celler):
                continue
            if sha is None:
                sha = kjerne.verifiser_modell(sti_fra_miljo("NORSK_TALE_MODELLER") / m["modeller"][modellvalg]["fil"],
                                              m["modeller"][modellvalg]["sha256"])
            lyd = lyd_for(m, navn, ider, arbeid)
            oppsett = {(mf, p): oppsett_for(m, modellvalg, mf, p) for mf, p in celler}
            print(f"{modellvalg}/{navn}: {len(ider)} ytringer × {len(celler)} celler, {len(gjort)} ferdig", flush=True)
            with fil.open("a", encoding="utf-8") as fh:
                for i, uid in enumerate(ider):
                    if teller % sjekk_hver == 0 and not ollama_fri():
                        print("Ollama har en modell lastet, eller ollama-inspect lever: stopper (gjenopptas)", flush=True)
                        return 7
                    teller += 1
                    for mf, p in celler:
                        if (uid, mf, p) in gjort:
                            continue
                        if uid not in lyd:
                            r = {"status": "mangler_lyd"}
                        else:
                            r = kjor_en(lyd[uid], oppsett[(mf, p)], sha, m["maks_gjentak"])
                        fh.write(json.dumps({"id": uid, "malform": mf, "prompt": p, **r}, ensure_ascii=False) + "\n")
                        fh.flush()
                    if (i + 1) % 100 == 0:
                        print(f"  {modellvalg}/{navn}: {i + 1}/{len(ider)}", flush=True)
    print("ferdig", flush=True)
    return 0


# ------------------------------------------------------------- determinisme
def determinisme(m, n=5):
    os.environ["NORSK_TALE_WHISPER_ARGS"] = m["whisper_cpp"]["ekstra_args"]
    kjerne.TIDSGRENSE_S = m["tidsgrense_s"]
    ider = les_idliste(ROT / m["sett"]["fleurs"]["idliste"])[:n]
    arbeid = sti_fra_miljo("NORSK_TALE_ARBEID") / m["versjon"] / "determinisme"
    lyd = sett.fleurs_pakk_ut(sti_fra_miljo("NORSK_TALE_DATA"), ider, arbeid / "lyd")
    o = oppsett_for(m, "medium", "nb", "pa")
    sha = kjerne.verifiser_modell(o.modell, o.sha256)
    runder = []
    for _ in range(2):
        runde = {}
        for uid in ider:
            r = kjerne.transkriber(lyd[uid], o, sha=sha)
            runde[uid] = {"ra_sha256": sha_tekst(r["verbatim"]), "korrigert_sha256": sha_tekst(r["korrigert"])}
        runder.append(runde)
    return {"ider": ider, "modell": "medium", "malform": "nb", "prompt": "pa",
            "backend": m["whisper_cpp"]["backend"], "runde_1": runder[0], "runde_2": runder[1],
            "identisk": runder[0] == runder[1]}


# --------------------------------------------------------------------- scor
def uten_markorer(tekst):
    return MARKOR.sub(r"\1", tekst)


def bootstrap_indekser(n, sett_navn, seed, B):
    rng = random.Random(f"{seed}/{sett_navn}")
    return [[rng.randrange(n) for _ in range(n)] for _ in range(B)]


def ki(feil, lengde, indekser, nedre, ovre):
    verdier = sorted(sum(feil[i] for i in ix) / max(1, sum(lengde[i] for i in ix)) for ix in indekser)
    return [round(verdier[nedre], 4), round(verdier[ovre], 4)]


def nektelser_per_type(par):
    """METHOD § 5: per ytring og type, max(0, ref−hyp) og max(0, hyp−ref), summert."""
    s = feilanalyse.sum_tapte(par)
    n = len(par)
    return {**s, "tapt_per_100": round(100 * s["tapt"] / n, 2) if n else None,
            "lagt_til_per_100": round(100 * s["lagt_til"] / n, 2) if n else None}


def scor(m, arbeid=None):
    arbeid = arbeid or sti_fra_miljo("NORSK_TALE_ARBEID") / m["versjon"]
    rot = sti_fra_miljo("NORSK_TALE_DATA")
    b = m["bootstrap"]
    rapport = {"versjon": m["versjon"], "sett": {}}
    for navn, s in m["sett"].items():
        rader, _ = sett.SETT[navn][0](rot)
        fasit = {r.id: r for r in rader}
        ider = les_idliste(ROT / s["idliste"])
        celler = {}
        for mv in m["modellrekkefolge"]:
            fil = resultatfil(arbeid, navn, mv)
            if not fil.exists():
                continue
            for ln in fil.read_text(encoding="utf-8").splitlines():
                d = json.loads(ln)
                celler.setdefault((mv, d["malform"], d["prompt"]), {})[d["id"]] = d
        forventet = [(mv, mf, p) for mv in m["modellrekkefolge"] for mf in s["malformer"] for p in s["prompt"]]
        mangler_celle = [c for c in forventet if c not in celler]
        utelukket = {"/".join(c): {} for c in forventet}
        gyldige = []
        for uid in ider:
            ok = True
            for c in forventet:
                st = celler.get(c, {}).get(uid, {}).get("status", "ikke_kjort")
                if st != "ok":
                    ok = False
                    utelukket["/".join(c)][st] = utelukket["/".join(c)].get(st, 0) + 1
            if ok:
                gyldige.append(uid)
        sett_rapport = {"n_utvalg": len(ider), "n_analyse": len(gyldige),
                        "andel_utelukket": round(1 - len(gyldige) / len(ider), 4) if ider else None,
                        "utelukket_ved_kjoring": utelukket, "mangler_celler": ["/".join(c) for c in mangler_celle],
                        "celler": {}}
        delsett = {"alle": gyldige}
        if navn == "npsc":
            delsett = {mf: [u for u in gyldige if fasit[u].malform == mf] for mf in ("nb", "nn")}
        if navn == "nb_tale":
            for g in sorted({fasit[u].gruppe for u in gyldige}):
                delsett[f"gruppe_{g}"] = [u for u in gyldige if fasit[u].gruppe == g]
        for dnavn, uids in delsett.items():
            if not uids:
                continue
            indekser = bootstrap_indekser(len(uids), f"{navn}/{dnavn}" if dnavn != "alle" else navn, m["seed"], b["B"])
            for c in forventet:
                if c in mangler_celle:
                    continue
                res = celler[c]
                cell = {"n": len(uids)}
                for tekst in ("ra", "korrigert"):
                    hyp = [res[u][tekst] for u in uids]
                    if tekst == "korrigert":
                        cell["markorer"] = sum(len(MARKOR.findall(h)) for h in hyp)
                        hyp = [uten_markorer(h) for h in hyp]
                    ref = [fasit[u].fasit for u in uids]
                    of = [norm.ordfeil(r, h) for r, h in zip(ref, hyp)]
                    tf = [norm.tegnfeil(r, h) for r, h in zip(ref, hyp)]
                    cell[tekst] = {
                        "wer": round(sum(x[0] for x in of) / max(1, sum(x[1] for x in of)), 4),
                        "wer_ki95": ki([x[0] for x in of], [x[1] for x in of], indekser, b["nedre_indeks"], b["ovre_indeks"]),
                        "cer": round(sum(x[0] for x in tf) / max(1, sum(x[1] for x in tf)), 4),
                        "cer_ki95": ki([x[0] for x in tf], [x[1] for x in tf], indekser, b["nedre_indeks"], b["ovre_indeks"]),
                        "nektelser": nektelser_per_type(list(zip(ref, hyp))),
                    }
                tider = sorted(res[u]["vegg_s"] for u in uids)
                cell["vegg_s"] = {"median": tider[len(tider) // 2], "sum": round(sum(tider), 1)}
                sett_rapport["celler"].setdefault(dnavn, {})["/".join(c)] = cell
        rapport["sett"][navn] = sett_rapport
    return rapport


# -------------------------------------------------------------------- miljø
def _kommando(argv):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"utilgjengelig: {e}"


def miljo(m):
    cli = os.environ.get("NORSK_TALE_WHISPER_CLI", "")
    pakker = _kommando([sys.executable, "-m", "pip", "list", "--format=freeze"])
    return {
        "tid_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "os": platform.platform(), "maskin": platform.machine(),
        "cpu": _kommando(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "minne_bytes": _kommando(["sysctl", "-n", "hw.memsize"]),
        "gpu": [ln.strip() for ln in _kommando(["system_profiler", "SPDisplaysDataType"]).splitlines()
                if "Chipset" in ln or "Metal" in ln or "Total Number of Cores" in ln],
        "python": sys.version, "python_pakker": pakker.splitlines(),
        "whisper_cli_sha256": sha256(cli) if cli and pathlib.Path(cli).is_file() else None,
        "whisper_cpp": m["whisper_cpp"]["describe"],
        "ffmpeg": _kommando(["ffmpeg", "-version"]).splitlines()[0],
        "norsk_tale_whisper_args": m["whisper_cpp"]["ekstra_args"],
    }


# --------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", default=str(MANIFEST))
    sub = ap.add_subparsers(dest="steg", required=True)
    v = sub.add_parser("verifiser")
    v.add_argument("--uten-data", action="store_true")
    u = sub.add_parser("utvalg")
    u.add_argument("--sjekk", action="store_true")
    u.add_argument("--sett", nargs="*")
    sub.add_parser("determinisme")
    k = sub.add_parser("kjor")
    k.add_argument("--sett", nargs="*")
    k.add_argument("--modell")
    sub.add_parser("scor")
    sub.add_parser("miljo")
    a = ap.parse_args(argv)
    m = les_manifest(a.manifest)

    if a.steg == "verifiser":
        verifiser(m, data=not a.uten_data)
        print("alle SHA-er stemmer")
        return 0
    if a.steg == "utvalg":
        print(json.dumps(utvalg(m, sjekk=a.sjekk, bare=a.sett), ensure_ascii=False, indent=1))
        return 0
    if a.steg == "determinisme":
        verifiser(m)
        r = determinisme(m)
        print(json.dumps(r, indent=1))
        return 0 if r["identisk"] else 6
    if a.steg == "kjor":
        verifiser(m)
        utvalg(m, sjekk=True)
        arbeid = sti_fra_miljo("NORSK_TALE_ARBEID") / m["versjon"]
        arbeid.mkdir(parents=True, exist_ok=True)
        (arbeid / f"miljo-{time.strftime('%Y%m%dT%H%M%S')}.json").write_text(
            json.dumps(miljo(m), ensure_ascii=False, indent=1), encoding="utf-8")
        return kjor(m, bare_sett=a.sett, bare_modell=a.modell)
    if a.steg == "scor":
        verifiser(m, data=False)
        arbeid = sti_fra_miljo("NORSK_TALE_ARBEID") / m["versjon"]
        r = scor(m, arbeid)
        (arbeid / "rapport.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"rapport: {arbeid / 'rapport.json'}")
        return 0
    if a.steg == "miljo":
        print(json.dumps(miljo(m), ensure_ascii=False, indent=1))
        return 0


if __name__ == "__main__":
    sys.exit(main())
