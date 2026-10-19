#!/usr/bin/env python3
"""norsk-tale — resident lytter for Claude Code-modden.

Tynn adapter rundt kjernen (kjerne/). Den eier tre ting kjernen ikke eier:
mikrofonen, stillhetsvakten og protokollen mot modden. Selve transkripsjonen
(modell-SHA, whisper, korrektur) er `kjerne.Resident` — den dupliseres ikke her.

  - mikrofonen er lukket til et trykk: ffmpeg startes ved «start», stoppes ved
    «stopp», 1,5 s stillhet etter tale, eller taket på 2 min
  - 0,5 s pre-roll: lyden før taleinnsatsen som beholdes, så første stavelse
    ikke klippes når den ledende stillheten skjæres bort
  - modellen lastes ved første trykk og frigjøres etter 10 min uten aktivitet
  - lyden skrives bare til en midlertidig katalog og slettes etter transkripsjon

Protokoll: modden skriver `<kontroll>/<løpenr>.cmd` med `start`, `stopp` eller
`avslutt`. Lytteren svarer med én JSON-linje per hendelse på stdout.
"""
import argparse
import array
import collections
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave

RATE = 16000
RAMME_MS = 30
RAMME_BYTES = RATE * RAMME_MS // 1000 * 2


def emit(**hendelse):
    print(json.dumps(hendelse, ensure_ascii=False), flush=True)


def rms(ramme):
    a = array.array("h")
    a.frombytes(ramme[: len(ramme) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    if not a:
        return 0.0
    return (sum(x * x for x in a) / len(a)) ** 0.5


class Stillhetsvakt:
    """Ren tilstandsmaskin over 30 ms-rammer. `mat` returnerer None, eller
    hvorfor opptaket er ferdig: «stillhet» eller «tak»."""

    def __init__(self, preroll_s=0.5, stillhet_s=1.5, tak_s=120.0,
                 terskel_min=300.0, faktor=3.0, innsats_rammer=3,
                 kalibrering_s=0.3, gulv_tak=1000.0):
        n = lambda s: max(1, round(s * 1000 / RAMME_MS))
        self.preroll = collections.deque(maxlen=n(preroll_s))
        self.stillhet_rammer = n(stillhet_s)
        self.tak_rammer = n(tak_s)
        self.terskel_min = terskel_min
        self.faktor = faktor
        self.innsats_rammer = innsats_rammer
        # Støygulvet måles på de første 0,3 s og fryses deretter, så talen
        # aldri løfter sin egen terskel. Taket på gulvet gjør at tale som
        # starter med en gang trykket er gjort, fortsatt gir innsats.
        self.kalibrering = collections.deque(maxlen=n(kalibrering_s))
        self.gulv_tak = gulv_tak
        self.tale = bytearray()
        self.har_tale = False
        self.rammer = 0
        self.over = 0
        self.under = 0
        self.nuller = 0
        self.innsats = None     # rammenummer for taleinnsats
        self.siste_tale = None  # rammenummer for siste ramme over terskelen

    def terskel(self):
        if not self.kalibrering:
            return self.terskel_min
        gulv = sorted(self.kalibrering)[len(self.kalibrering) // 10]
        return max(self.terskel_min, min(gulv, self.gulv_tak) * self.faktor)

    def mat(self, ramme):
        self.rammer += 1
        e = rms(ramme)
        if e == 0.0:
            self.nuller += 1
        hoy = e > self.terskel()
        if self.rammer <= self.kalibrering.maxlen:
            self.kalibrering.append(e)
        if not self.har_tale:
            self.preroll.append(ramme)
            self.over = self.over + 1 if hoy else 0
            if self.over >= self.innsats_rammer:
                self.har_tale = True
                self.innsats = self.siste_tale = self.rammer
                self.tale.extend(b"".join(self.preroll))
                self.preroll.clear()
        else:
            self.tale.extend(ramme)
            if hoy:
                self.siste_tale = self.rammer
            self.under = 0 if hoy else self.under + 1
            if self.under >= self.stillhet_rammer:
                return "stillhet"
        if self.rammer >= self.tak_rammer:
            return "tak"
        return None

    def maling(self):
        """Lydtid i ms: fra siste ramme med tale til stopp, og talens lengde.
        Målt i rammer, så det er uavhengig av hvor travel maskinen er."""
        if not self.har_tale or self.innsats is None or self.siste_tale is None:
            return {"stillhet_ms": None, "tale_ms": None}
        return {"stillhet_ms": (self.rammer - self.siste_tale) * RAMME_MS,
                "tale_ms": (self.siste_tale - self.innsats + self.innsats_rammer) * RAMME_MS}

    def bare_nuller(self):
        """Ett sekund med eksakt null-signal: macOS leverer det når appen
        mangler mikrofontilgang."""
        return self.rammer >= 1000 // RAMME_MS and self.nuller == self.rammer


def mikrofon_argv(ffmpeg):
    enhet = os.environ.get("NORSK_TALE_MIKROFON")
    base = [ffmpeg, "-nostdin", "-loglevel", "error"]
    ut = ["-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"]
    testkilde = os.environ.get("NORSK_TALE_TESTKILDE")
    if testkilde:
        # Kun for tester: en ekte opptaksfil spilt i sanntid (-re) i stedet for
        # mikrofonen, så hele kjeden kan prøves uten å åpne mikrofonen.
        return base + ["-re", "-i", testkilde] + ut
    if sys.platform == "darwin":
        return base + ["-f", "avfoundation", "-i", f":{enhet or 'default'}"] + ut
    if sys.platform.startswith("linux"):
        return base + ["-f", "pulse", "-i", enhet or "default"] + ut
    if os.name == "nt":  # ikke testet
        if not enhet:
            raise RuntimeError("Sett NORSK_TALE_MIKROFON til dshow-navnet på mikrofonen.")
        return base + ["-f", "dshow", "-i", f"audio={enhet}"] + ut
    raise RuntimeError(f"Ukjent plattform for mikrofon: {sys.platform}")


class Opptak:
    """Mikrofonen er åpen nøyaktig så lenge dette objektet lever."""

    def __init__(self, ffmpeg, vakt):
        self.vakt = vakt
        self.grunn = None
        self.ferdig = threading.Event()
        self.stoppet = threading.Event()
        self.feil = None
        self.proc = subprocess.Popen(mikrofon_argv(ffmpeg), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.trad = threading.Thread(target=self._les, daemon=True)
        self.trad.start()

    def _les(self):
        meldt_tale = False
        try:
            while not self.stoppet.is_set():
                ramme = self.proc.stdout.read(RAMME_BYTES)
                if not ramme:
                    if self.vakt.har_tale:
                        # Kilden sluttet etter tale: det som er tatt opp, transkriberes.
                        self.grunn = "kilden sluttet"
                        break
                    hale = self.proc.stderr.read().decode("utf-8", "replace").strip()
                    self.feil = hale or "lydstrømmen sluttet før det kom tale"
                    break
                grunn = self.vakt.mat(ramme)
                if self.vakt.har_tale and not meldt_tale:
                    meldt_tale = True
                    emit(type="tale")
                if self.vakt.bare_nuller() and not self.vakt.har_tale:
                    self.feil = "nuller"
                    break
                if grunn:
                    self.grunn = grunn
                    break
        finally:
            self._lukk()
            self.ferdig.set()

    def _lukk(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def stopp(self):
        self.stoppet.set()
        self.grunn = self.grunn or "trykk"
        self._lukk()
        self.ferdig.wait(5)


MIKROFON_FEIL = ("Ingen mikrofontilgang: macOS leverer bare stillhet. Gi appen som kjører "
                 "Claude Code (Terminal, iTerm, Claude) tilgang under Systeminnstillinger → "
                 "Personvern og sikkerhet → Mikrofon, og start den på nytt.")


class Lytter:
    """Eier modellens livsløp: lastes ved første trykk, frigjøres etter
    `frigjor_s` sekunder uten aktivitet, lastes på nytt ved neste trykk.

    Uten whisper-server (Homebrew bygger den ikke) brukes kjernens filbane:
    whisper-cli per opptak, modellen lastes hver gang og holdes aldri."""

    def __init__(self, kjerne, konfig, frigjor_s=600.0, klokke=time.monotonic):
        self.kjerne = kjerne
        self.konfig = konfig
        self.frigjor_s = frigjor_s
        self.klokke = klokke
        self.resident = None
        self.laster = None
        self.lastefeil = None
        self.opptak = None
        self.ffmpeg = shutil.which("ffmpeg")
        self.sist_aktiv = klokke()
        self.oppsett = None

    def oppsettfeil(self):
        """Billige sjekker uten SHA (den verifiseres når modellen lastes).
        Kjøres ved hvert trykk, så en rettet installasjon virker uten omstart."""
        try:
            o = self.kjerne.standard_oppsett(**self.konfig)
            rapport = self.kjerne.sjekk_oppsett(o, verifiser_sha=False)
        except Exception as e:
            return f"Oppsettet kan ikke leses: {e}"
        if rapport["ok"]:
            return None
        return (f"Oppsettet er ikke komplett (mangler: {', '.join(rapport['mangler'])}). "
                "Kjør /norsk oppsett for hva som må gjøres.")

    def _last(self):
        try:
            emit(type="laster")
            r = self.kjerne.Resident(self.kjerne.standard_oppsett(**self.konfig))
            self.resident = r.start()
            emit(type="modell_klar", modell_sha256=self.resident.sha)
        except Exception as e:
            self.lastefeil = str(e)
            emit(type="feil", melding=self.lastefeil)

    def _laster_na(self):
        return self.laster is not None and self.laster.is_alive()

    def start(self):
        if self.opptak:
            return
        feil = self.oppsettfeil()
        if feil:
            emit(type="feil", melding=feil)
            return
        self.lastefeil = None
        self.sist_aktiv = self.klokke()
        self.oppsett = self.kjerne.standard_oppsett(**self.konfig)
        if self.oppsett.whisper_server is not None and self.resident is None and not self._laster_na():
            self.laster = threading.Thread(target=self._last, daemon=True)
            self.laster.start()
        try:
            self.opptak = Opptak(self.ffmpeg, Stillhetsvakt())
        except Exception as e:
            emit(type="feil", melding=f"Kunne ikke åpne mikrofonen: {e}")
            return
        emit(type="lytter")

    def stopp(self):
        if self.opptak:
            self.opptak.stopp()

    def frigjor_ved_inaktivitet(self):
        if (self.resident is not None and self.opptak is None and not self._laster_na()
                and self.klokke() - self.sist_aktiv >= self.frigjor_s):
            self.resident.stopp()
            self.resident = None
            emit(type="frigjort", etter_s=self.frigjor_s)

    def poll(self):
        """Kalles i hovedløkka: avslutter et opptak som er ferdig, og frigjør
        modellen når den har ligget ubrukt lenge nok."""
        o = self.opptak
        if not o or not o.ferdig.is_set():
            self.frigjor_ved_inaktivitet()
            return
        self.opptak = None
        self.sist_aktiv = self.klokke()
        if o.feil:
            emit(type="feil", melding=MIKROFON_FEIL if o.feil == "nuller" else
                 f"Mikrofonen feilet: {o.feil}")
            return
        if not o.vakt.har_tale:
            emit(type="tom", slutt=o.grunn)
            return
        maling = o.vakt.maling()
        emit(type="behandler", slutt=o.grunn, **maling)
        filbane = self.oppsett is not None and self.oppsett.whisper_server is None
        if self.laster:
            self.laster.join()
        if not filbane and self.resident is None:
            emit(type="feil", melding=self.lastefeil or "Modellen ble ikke lastet.")
            return
        with tempfile.TemporaryDirectory(prefix="norsk-tale-") as tmp:
            wav = pathlib.Path(tmp) / "opptak.wav"
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(bytes(o.vakt.tale))
            try:
                resultat = (self.kjerne.transkriber(wav, self.oppsett) if filbane
                            else self.resident.transkriber(wav))
            except Exception as e:
                emit(type="feil", melding=f"Transkripsjonen feilet: {e}")
                return
        self.sist_aktiv = self.klokke()
        emit(type="tekst", slutt=o.grunn, resultat=resultat, **maling)

    def avslutt(self):
        self.stopp()
        if self.resident is not None:
            self.resident.stopp()
            self.resident = None


def last_kjerne():
    """Kjernen ligger i pluginens egen kjerne/-mappe ved siden av lytter/."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "kjerne"))
    import kjerne
    return kjerne


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kontroll", required=True, type=pathlib.Path)
    ap.add_argument("--modellvalg", default="")
    ap.add_argument("--modell", default="")
    ap.add_argument("--whisper", default="")
    ap.add_argument("--frigjor-etter", type=float, default=600.0,
                    help="Sekunder uten aktivitet før modellen frigjøres (standard 600).")
    a = ap.parse_args(argv)
    kontroll = a.kontroll.expanduser()
    kontroll.mkdir(parents=True, exist_ok=True)
    konfig = {"modellvalg": a.modellvalg or None, "modell": a.modell or None,
              "whisper": a.whisper or None}
    lytter = Lytter(last_kjerne(), konfig, frigjor_s=a.frigjor_etter)
    forelder = os.getppid()
    emit(type="oppe", feil=lytter.oppsettfeil())
    try:
        while True:
            if os.getppid() != forelder:
                break
            for cmd in sorted(kontroll.glob("*.cmd"), key=lambda p: int(p.stem)):
                ord_ = cmd.read_text(encoding="utf-8").strip()
                cmd.unlink()
                if ord_ == "start":
                    lytter.start()
                elif ord_ == "stopp":
                    lytter.stopp()
                elif ord_ == "avslutt":
                    return 0
            lytter.poll()
            time.sleep(0.05)
    finally:
        lytter.avslutt()
    return 0


if __name__ == "__main__":
    sys.exit(main())
