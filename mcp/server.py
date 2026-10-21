"""norsk-tale — lokal MCP-server (stdio), bygget med den offisielle MCP-Python-SDK-en.

All oppstart av lokale programmer i pluginen skjer her (docs/decisions/NTA-0007):
lytteren (ffmpeg + whisper-cli/whisper-server via kjernen), kjernens
oppsettsjekk, kalibreringsriggen og nettleseren som åpner den. Det eneste pluginen
skriver (selvtestrapporten) skrives også her. Modden og skillen
starter ingen prosesser selv.

Kjernen (kjerne/kjerne.py, kjerne/korriger.py og vokabularfilene) importeres
uendret: den er låst med SHA256 i kalibrering/manifest.json (prereg-v1), og
tests/test_preregistrering.py feiler hvis den endres.

Konfigurasjon: pluginens innstillinger kommer fra .mcp.json som
NORSK_TALE_VALGT_{MODELLVALG,MALFORM,MODELL,WHISPER,OPPTAK}. En tom innstilling
faller tilbake på kjernens egne miljøvariabler (NORSK_TALE_MODELL osv.) og
deretter standardene, som i kjernen: innstilling > miljø > standard.

Verktøyene start_opptak og stopp_opptak åpner og lukker mikrofonen. Modden
nekter modellen å kalle dem (og alle andre verktøy enn transkriber_fil);
bare brukerens trykk eller snarvei, via modden, starter et opptak.

Ingen nettverkskall: den eneste forbindelsen er loopback til en lokal
whisper-server, når den finnes.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import time

HER = pathlib.Path(__file__).resolve().parent
ROT = HER.parent
sys.path.insert(0, str(ROT / "kjerne"))
sys.path.insert(0, str(ROT / "lytter"))
import kjerne  # noqa: E402
import norsk_lytter  # noqa: E402

from mcp.server.mcpserver import MCPServer  # noqa: E402

TALE = ("start_opptak", "stopp_opptak")


def konfig():
    """Pluginens innstillinger slik .mcp.json gir dem. None lar kjernen lese sine
    egne miljøvariabler og standarder."""
    return {k: os.environ.get(f"NORSK_TALE_VALGT_{k.upper()}") or None
            for k in ("modellvalg", "modell", "whisper", "malform")}


def bruk_valgt_opptaksmappe():
    """En valgt opptaksmappe gjelder også kjernens og riggens standard."""
    valgt = os.environ.get("NORSK_TALE_VALGT_OPPTAK")
    if valgt:
        os.environ["NORSK_TALE_OPPTAK"] = valgt


class Hendelser:
    """Lytterens hendelser med løpenummer, så modden kan hente det som er nytt."""

    def __init__(self, maks=200):
        self.las = threading.Lock()
        self.liste = []
        self.nr = 0
        self.maks = maks

    def legg_til(self, **h):
        with self.las:
            self.nr += 1
            self.liste.append({"nr": self.nr, **h})
            del self.liste[:-self.maks]

    def etter(self, nr):
        with self.las:
            return [h for h in self.liste if h["nr"] > nr], self.nr


class Tjeneste:
    """Én lytter per server; en tråd driver lytterens poll()-løkke."""

    def __init__(self, lytter_klasse=norsk_lytter.Lytter, kjerne_modul=kjerne, intervall=0.05):
        self.hendelser = Hendelser()
        # Lytteren melder hendelser med modulfunksjonen emit(); her går de til
        # hendelseslisten i stedet for stdout, som er MCP-protokollen.
        norsk_lytter.emit = self.hendelser.legg_til
        self.kjerne = kjerne_modul
        self.lytter = lytter_klasse(kjerne_modul, konfig())
        self.las = threading.Lock()
        self.rigg = None
        self.rigg_url = None
        self._stopp = threading.Event()
        self._traad = threading.Thread(target=self._løkke, args=(intervall,), daemon=True)
        self._traad.start()

    def _løkke(self, intervall):
        while not self._stopp.is_set():
            with self.las:
                self.lytter.poll()
            time.sleep(intervall)

    def start_opptak(self, malform=""):
        nr = self.hendelser.etter(10 ** 12)[1]
        with self.las:
            self.lytter.start(malform or None)
        return {"etter": nr}

    def stopp_opptak(self):
        self.lytter.stopp()
        return {"ok": True}

    def status(self, etter=0):
        nye, nr = self.hendelser.etter(int(etter))
        return {"hendelser": nye, "nr": nr, "opptak": self.lytter.opptak is not None}

    def frigjor(self):
        with self.las:
            self.lytter.avslutt()
        return {"ok": True}

    def transkriber_fil(self, sti, malform=""):
        oppsett = self.kjerne.standard_oppsett(**{**konfig(), "malform": malform or konfig()["malform"]})
        return self.kjerne.transkriber(sti, oppsett)

    def oppsett(self):
        try:
            o = self.kjerne.standard_oppsett(**konfig())
            return self.kjerne.sjekk_oppsett(o, verifiser_sha=True)
        except Exception as e:
            return {"ok": False, "melding": f"Oppsettet kan ikke leses: {e}"}

    def lagre_selvtest(self, rapport, stempel):
        """Skriver selvtestrapporten (JSON, uten lyd) som selvtest-claude-<stempel>.json i
        opptaksmappa. Mappa og stien bestemmes her, ikke av modden; et umontert eksternt
        volum stopper skrivingen i stedet for å gi en mappe på intern disk."""
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{6}", str(stempel)):
            return {"ok": False, "melding": "Ugyldig tidsstempel for selvtestrapporten."}
        try:
            data = json.loads(rapport)
        except (TypeError, json.JSONDecodeError):
            return {"ok": False, "melding": "Selvtestrapporten er ikke gyldig JSON."}
        mappe = self.kjerne.standard_opptaksmappe()
        try:
            self.kjerne.krev_montert(mappe)
            mappe.mkdir(parents=True, exist_ok=True)
            fil = mappe / f"selvtest-claude-{stempel}.json"
            fil.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except self.kjerne.KjerneFeil as e:
            return {"ok": False, "melding": str(e)}
        except OSError as e:
            return {"ok": False, "melding": f"Kunne ikke skrive selvtestrapporten: {e}"}
        return {"ok": True, "fil": str(fil)}

    def start_kalibrering(self):
        """Starter riggen (127.0.0.1, token i adressen) og åpner den i nettleseren."""
        if self.rigg is not None and self.rigg.poll() is None and self.rigg_url:
            return {"url": self.rigg_url, "apnet": apne_nettleser(self.rigg_url), "allerede": True}
        k = konfig()
        argv = [sys.executable, "-I", str(ROT / "kalibrering" / "rigg.py"),
                "--modellvalg", k["modellvalg"] or "", "--modell", k["modell"] or "",
                "--whisper", k["whisper"] or "", "--opptak", os.environ.get("NORSK_TALE_OPPTAK", "")]
        self.rigg = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     stdin=subprocess.DEVNULL, text=True)
        linje = self.rigg.stdout.readline()
        try:
            svar = json.loads(linje)
        except json.JSONDecodeError:
            return {"feil": f"Riggen startet ikke: {linje.strip()[:200] or 'ingen utdata'}"}
        if svar.get("type") != "klar":
            return {"feil": svar.get("melding", "Riggen startet ikke.")}
        self.rigg_url = svar["url"]
        return {"url": self.rigg_url, "apnet": apne_nettleser(self.rigg_url), "allerede": False}

    def avslutt(self):
        self._stopp.set()
        self.lytter.avslutt()
        if self.rigg is not None and self.rigg.poll() is None:
            self.rigg.terminate()


def apne_nettleser(url):
    for program in ("open", "xdg-open"):
        sti = shutil.which(program)
        if sti and subprocess.run([sti, url], capture_output=True, timeout=10).returncode == 0:
            return True
    return False


def lag_server(tjeneste):
    app = MCPServer("norsk-tale", instructions=(
        "Lokal norsk tale-til-tekst med NB-Whisper. Bare transkriber_fil er for deg: den transkriberer "
        "en lydfil brukeren peker på. De andre verktøyene brukes av pluginens knapp og kommandoer."))

    @app.tool(description="Transkriberer en lokal lydfil på norsk (bokmål eller nynorsk) med NB-Whisper på "
                          "denne maskinen. sti: absolutt sti til lydfila. malform: nb, nn, auto eller tom "
                          "for innstillingen. Svaret er JSON med verbatim, korrigert og substitusjonslogg.")
    def transkriber_fil(sti: str, malform: str = "") -> dict:
        return tjeneste.transkriber_fil(sti, malform)

    @app.tool(description="Bare for norsk-tale-modden: åpner mikrofonen etter brukerens trykk.")
    def start_opptak(malform: str = "") -> dict:
        return tjeneste.start_opptak(malform)

    @app.tool(description="Bare for norsk-tale-modden: stopper opptaket som pågår.")
    def stopp_opptak() -> dict:
        return tjeneste.stopp_opptak()

    @app.tool(description="Bare for norsk-tale-modden: lytterens hendelser etter løpenummer.")
    def status(etter: int = 0) -> dict:
        return tjeneste.status(etter)

    @app.tool(description="Bare for norsk-tale-modden: frigjør modellen og stopper lytteren.")
    def frigjor() -> dict:
        return tjeneste.frigjor()

    @app.tool(description="Bare for norsk-tale-modden: sjekker ffmpeg, whisper.cpp og modellen (/norsk oppsett).")
    def oppsett() -> dict:
        return tjeneste.oppsett()

    @app.tool(description="Bare for norsk-tale-modden: lagrer selvtestrapporten (JSON, uten lyd) i opptaksmappa.")
    def lagre_selvtest(rapport: str, stempel: str) -> dict:
        return tjeneste.lagre_selvtest(rapport, stempel)

    @app.tool(description="Bare for norsk-tale-modden: starter kalibreringsriggen og åpner den i nettleseren.")
    def start_kalibrering() -> dict:
        return tjeneste.start_kalibrering()

    return app


def main():
    bruk_valgt_opptaksmappe()
    tjeneste = Tjeneste()
    try:
        lag_server(tjeneste).run("stdio")
    finally:
        tjeneste.avslutt()


if __name__ == "__main__":
    main()
