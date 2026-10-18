#!/usr/bin/env python3
"""norsk-tale — resident lytter for Claude Code-modden.

Tynn adapter rundt NORSKRIBER-kjernen. Den eier tre ting kjernen ikke eier:
mikrofonen, stillhetsvakten og protokollen mot modden. Selve transkripsjonen
(modell-SHA, whisper, korrektur) er `kjerne.Resident` — den dupliseres ikke her.

  - mikrofonen er lukket til et trykk: ffmpeg startes ved «start», stoppes ved
    «stopp», 1,5 s stillhet etter tale, eller taket på 2 min
  - 0,5 s pre-roll: lyden før taleinnsatsen som beholdes, så første stavelse
    ikke klippes når den ledende stillheten skjæres bort
  - modellen lastes ved første trykk og blir liggende til økten slutter
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
                self.tale.extend(b"".join(self.preroll))
                self.preroll.clear()
        else:
            self.tale.extend(ramme)
            self.under = 0 if hoy else self.under + 1
            if self.under >= self.stillhet_rammer:
                return "stillhet"
        if self.rammer >= self.tak_rammer:
            return "tak"
        return None

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
    def __init__(self, norskriber):
        self.kjerne = None
        self.resident = None
        self.laster = None
        self.lastefeil = None
        self.opptak = None
        self.ffmpeg = shutil.which("ffmpeg")
        sys.path.insert(0, str(norskriber))
        try:
            import kjerne
            self.kjerne = kjerne
        except ImportError as e:
            self.oppsettfeil = f"Fant ikke NORSKRIBER-kjernen i {norskriber} ({e})."
            return
        self.oppsettfeil = self._oppsettsjekk()

    def _oppsettsjekk(self):
        """Billige sjekker uten SHA; SHA-en verifiseres når modellen lastes."""
        if not self.ffmpeg:
            return "Fant ikke ffmpeg på PATH."
        try:
            o = self.kjerne.standard_oppsett()
        except Exception as e:
            return f"NORSKRIBER-oppsettet kan ikke leses: {e}"
        if not o.whisper_server.is_file():
            return f"Fant ikke whisper.cpp-binæren: {o.whisper_server}"
        if not o.modell.is_file():
            return f"Fant ikke modellen: {o.modell}"
        return None

    def _last(self):
        try:
            emit(type="laster")
            self.resident = self.kjerne.Resident().start()
            emit(type="modell_klar", modell_sha256=self.resident.sha)
        except Exception as e:
            self.lastefeil = str(e)
            emit(type="feil", melding=self.lastefeil)

    def start(self):
        if self.oppsettfeil:
            emit(type="feil", melding=self.oppsettfeil)
            return
        if self.lastefeil:
            emit(type="feil", melding=self.lastefeil)
            return
        if self.opptak:
            return
        if not self.resident and not self.laster:
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

    def poll(self):
        """Kalles i hovedløkka: avslutter et opptak som er ferdig."""
        o = self.opptak
        if not o or not o.ferdig.is_set():
            return
        self.opptak = None
        if o.feil:
            emit(type="feil", melding=MIKROFON_FEIL if o.feil == "nuller" else
                 f"Mikrofonen feilet: {o.feil}")
            return
        if not o.vakt.har_tale:
            emit(type="tom", slutt=o.grunn)
            return
        emit(type="behandler", slutt=o.grunn)
        if self.laster:
            self.laster.join()
        if not self.resident:
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
                resultat = self.resident.transkriber(wav)
            except Exception as e:
                emit(type="feil", melding=f"Transkripsjonen feilet: {e}")
                return
        emit(type="tekst", slutt=o.grunn, resultat=resultat)

    def avslutt(self):
        self.stopp()
        if self.resident:
            self.resident.stopp()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kontroll", required=True, type=pathlib.Path)
    ap.add_argument("--norskriber", required=True, type=pathlib.Path)
    a = ap.parse_args(argv)
    kontroll = a.kontroll.expanduser()
    kontroll.mkdir(parents=True, exist_ok=True)
    lytter = Lytter(a.norskriber.expanduser())
    forelder = os.getppid()
    emit(type="oppe", feil=lytter.oppsettfeil)
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
