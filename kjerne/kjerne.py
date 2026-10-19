#!/usr/bin/env python3
"""norsk-tale — kjerne: én lydfil inn, ett JSON-objekt ut.

  {verbatim, korrigert, substitusjonslogg, modell_sha256, versjon}

  verbatim           whisper.cpp + NB-Whisper, språk tvunget til norsk,
                     vokabularet som --prompt
  korrigert          verbatim gjennom korriger.py (fasittabellen, ingen LLM)
  substitusjonslogg  korrektorens hendelser, én per forekomst
  modell_sha256      verifisert mot verdien Hugging Face publiserer
                     (modeller.json) FØR bruk; avvik = stopp

Utgått fra NORSKRIBER. Modden og skillen kaller denne modulen; de dupliserer den
ikke. Kjernen åpner ingen nettverksforbindelse: filbanen (`transkriber`) bruker
bare underprosesser og filer. `Resident` holder modellen lastet i en
whisper-server bundet til 127.0.0.1 og snakker med den over loopback — lyden
forlater ikke maskinen, men det ER en lokal TCP-port, og den er dokumentert som det.
Ingenting lastes ned: mangler noe, sier `--sjekk` hva og hvordan.

Konfigurasjon (argument > miljø > standard):
  --modellvalg  NORSK_TALE_MODELLVALG  large | medium | small      (large)
  --modell      NORSK_TALE_MODELL      sti til ggml-fila           (~/.cache/norsk-tale/nb-whisper-<valg>.bin)
  --whisper     NORSK_TALE_WHISPER     whisper-cli, navn eller sti (whisper-cli på PATH)
  --malform     NORSK_TALE_MALFORM     nb | nn | auto → whisper -l no | nn | auto  (nb)
                NORSK_TALE_WHISPER_ARGS ekstra flagg til whisper-cli/-server, f.eks. «-ng -t 4»
                                       (bare CPU, fire tråder) når andre jobber skal ha GPU-en
whisper-server finnes ved siden av whisper-cli når en sti er gitt, ellers på PATH.

Kryssplattform: pathlib overalt, ingen macOS-spesifikke kall. Kun testet på macOS.
"""
import argparse
import dataclasses
import hashlib
import json
import os
import pathlib
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

# Kjøres ofte med `python3 -I` (skillen, lytteren), som utelater skriptets egen
# katalog fra sys.path; korrektoren ligger ved siden av.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import korriger  # noqa: E402

VERSJON = "0.1.0"
HER = pathlib.Path(__file__).resolve().parent
MODELLER = HER / "modeller.json"
# Målform → whisper-språkkode. whisper.cpp har både «no» (norwegian) og «nn»
# (nynorsk); NB-Whisper-modellkortet bruker language='nn' for nynorsk-utdata.
SPRAKKODE = {"nb": "no", "nn": "nn", "auto": "auto"}
EXE = ".exe" if os.name == "nt" else ""
# Dekoding satt eksplisitt, så filbanen og Resident gir samme parametre
# (whisper-server har andre standarder enn whisper-cli).
STRALE = 5        # -bs, beam size
BESTE_AV = 5      # -bo, best of
TEMPERATUR = "0.0"
# Prefiks foran hver underprosess. Tom i drift; testene setter den for å kjøre
# whisper under et nettverksforbud på OS-nivå.
PREFIKS: list = []
# Øvre grense i sekunder for én underprosess. None i drift; kalibreringen
# (reproduser.py) setter den, så en hengende whisper-kjøring blir et tidsavbrudd.
TIDSGRENSE_S = None


class KjerneFeil(Exception):
    """Én tydelig feilmelding, beregnet på et menneske."""


class ModellAvvik(KjerneFeil):
    pass


class Tidsavbrudd(KjerneFeil):
    pass


@dataclasses.dataclass(frozen=True)
class Oppsett:
    modellvalg: str
    modell: pathlib.Path
    sha256: str
    bytes: int
    repo: str
    whisper_cli: object      # pathlib.Path, eller None når den ikke finnes
    whisper_server: object   # pathlib.Path, eller None når den ikke finnes
    fasit: tuple
    vokabular: tuple
    malform: str = "nb"

    @property
    def sprak(self):
        return SPRAKKODE[self.malform]


def modellkatalog():
    with MODELLER.open(encoding="utf-8") as fh:
        return {k: v for k, v in json.load(fh).items() if not k.startswith("_")}


def standard_modellsti(valg):
    return pathlib.Path.home() / ".cache" / "norsk-tale" / f"nb-whisper-{valg}.bin"


def finn_binar(navn_eller_sti):
    """En sti (inneholder skilletegn eller ~) tas som den er; et navn slås opp på PATH."""
    if not navn_eller_sti:
        return None
    if os.sep in navn_eller_sti or "/" in navn_eller_sti or navn_eller_sti.startswith("~"):
        p = pathlib.Path(navn_eller_sti).expanduser()
        return p if p.is_file() else None
    funnet = shutil.which(navn_eller_sti)
    return pathlib.Path(funnet) if funnet else None


def standard_oppsett(modellvalg=None, modell=None, whisper=None, malform=None):
    """Argument > miljø > standard. SHA256 kommer ALLTID fra modeller.json —
    konfigurasjonen kan flytte modellen, ikke endre hva den skal være."""
    valg = modellvalg or os.environ.get("NORSK_TALE_MODELLVALG") or "large"
    malform = malform or os.environ.get("NORSK_TALE_MALFORM") or "nb"
    if malform not in SPRAKKODE:
        raise KjerneFeil(f"Ukjent målform «{malform}». Gyldige: {', '.join(SPRAKKODE)}.")
    katalog = modellkatalog()
    if valg not in katalog:
        raise KjerneFeil(f"Ukjent modellvalg «{valg}». Gyldige: {', '.join(katalog)}.")
    m = katalog[valg]
    modell = modell or os.environ.get("NORSK_TALE_MODELL") or ""
    modellsti = pathlib.Path(modell).expanduser() if modell else standard_modellsti(valg)
    whisper = whisper or os.environ.get("NORSK_TALE_WHISPER") or f"whisper-cli{EXE}"
    cli = finn_binar(whisper)
    if cli is not None and ("/" in whisper or os.sep in whisper or whisper.startswith("~")):
        server = cli.parent / f"whisper-server{EXE}"
        server = server if server.is_file() else None
    else:
        server = finn_binar(f"whisper-server{EXE}")
    return Oppsett(valg, modellsti, m["sha256"], m["bytes"], m["repo"], cli, server,
                   (HER / "vokabular" / "fasit_offentlig.tsv",),
                   (HER / "vokabular" / "offentlig_no.txt",), malform)


def krev_montert(sti):
    """En sti på et eksternt volum (/Volumes/<navn>/…, også via symlenke) brukes
    bare når volumet faktisk er montert. Ellers stopp: mkdir under /Volumes på et
    umontert volum ville lagt filene på intern disk uten at noen merket det."""
    ekte = pathlib.Path(os.path.realpath(pathlib.Path(sti).expanduser()))
    deler = ekte.parts
    if len(deler) >= 3 and deler[1] == "Volumes":
        rot = pathlib.Path("/", "Volumes", deler[2])
        if not os.path.ismount(rot):
            raise KjerneFeil(f"{rot} er ikke montert. Ingenting kjøres, og ingenting legges på intern disk "
                             f"i stedet ({sti}).")
    return ekte


def standard_opptaksmappe():
    return pathlib.Path(os.environ.get("NORSK_TALE_OPPTAK") or pathlib.Path.home() / "norsk-tale-opptak").expanduser()


def verifiser_modell(sti, forventet):
    """Strømmer SHA256 over modellfila. Avvik eller manglende fil = KjerneFeil."""
    krev_montert(sti)
    sti = pathlib.Path(sti)
    if not sti.is_file():
        raise KjerneFeil(f"Fant ikke modellen: {sti}")
    h = hashlib.sha256()
    with sti.open("rb") as fh:
        for blokk in iter(lambda: fh.read(8 << 20), b""):
            h.update(blokk)
    faktisk = h.hexdigest()
    if faktisk != forventet.lower():
        raise ModellAvvik(f"Modellfila avviker fra låst SHA256 — stopper.\n"
                          f"  fil:      {sti}\n  låst:     {forventet}\n  faktisk:  {faktisk}")
    return faktisk


def vokabular_prompt(stier):
    """Formene i vokabularfilene som én whisper-prompt (--prompt)."""
    former = []
    for sti in stier:
        for ln in pathlib.Path(sti).read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and ln not in former:
                former.append(ln)
    return ", ".join(former) + "." if former else ""


def ekstra_whisper_args():
    return shlex.split(os.environ.get("NORSK_TALE_WHISPER_ARGS", ""))


def _kjor(argv):
    try:
        r = subprocess.run([*PREFIKS, *map(str, argv)], capture_output=True, timeout=TIDSGRENSE_S)
    except subprocess.TimeoutExpired:
        raise Tidsavbrudd(f"{pathlib.Path(str(argv[0])).name} brukte mer enn {TIDSGRENSE_S} s") from None
    if r.returncode != 0:
        hale = r.stderr.decode("utf-8", "replace").strip()[-600:]
        raise KjerneFeil(f"{pathlib.Path(str(argv[0])).name} feilet "
                         f"(kode {r.returncode}): {hale or 'ingen feiltekst'}")
    return r


def til_wav(lyd, wav):
    """Alt inn til 16 kHz mono s16le — samme konvertering som bygget alltid har brukt."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise KjerneFeil("Fant ikke ffmpeg på PATH.")
    _kjor([ffmpeg, "-nostdin", "-loglevel", "error", "-y", "-i", lyd,
           "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav])


def _sjekk_binar(sti, navn):
    if sti is None or not pathlib.Path(sti).is_file():
        raise KjerneFeil(f"Fant ikke {navn}. {_installer_hint()}")


def _installer_hint():
    if sys.platform == "darwin":
        return "Installer med: brew install whisper-cpp ffmpeg"
    return "Installer whisper.cpp og ffmpeg fra pakkesystemet ditt (ikke testet utenfor macOS)."


def bygg_resultat(verbatim, oppsett, sha):
    rader = korriger.les_fasit(list(oppsett.fasit))
    korrigert, hendelser, _ = korriger.korriger(verbatim, rader)
    return {"verbatim": verbatim, "korrigert": korrigert,
            "substitusjonslogg": hendelser, "modell_sha256": sha, "versjon": VERSJON}


SPESIALTOKEN = re.compile(r"<\|[a-z_]+\|>")


def _rens(tekst):
    """Segmentlinjer uten whisper-spesialtokens. NB-Whisper-basen skriver
    `<|nocaptions|>` inn i teksten over stillhet/støy; det er et
    tokenizer-merke, ikke tale, og fjernes her — ingenting annet endres.

    whisper.cpp har ikke et flagg som dekker dette: `--suppress-nst` demper bare
    symbolene i `non_speech_tokens` (src/whisper.cpp), og `--suppress-regex
    '<\\|nocaptions\\|>'` hadde ingen virkning, målt 19.10.2026 med large og medium
    (tokenet sto i utdata med og uten flagget). Filteret her er derfor primært."""
    linjer = (SPESIALTOKEN.sub("", ln).strip() for ln in tekst.splitlines())
    return "\n".join(ln for ln in linjer if ln)


def sjekk_oppsett(oppsett, verifiser_sha=True):
    """Hva som er på plass og hva som mangler, uten å transkribere og uten å
    laste ned noe. Returnerer {ok, mangler, tiltak, modell_sha256, melding}."""
    mangler, tiltak, merknader = [], [], []
    if not shutil.which("ffmpeg"):
        mangler.append("ffmpeg")
    if oppsett.whisper_cli is None:
        mangler.append("whisper-cli")
    if mangler:
        tiltak.append(_installer_hint())
    if oppsett.whisper_server is None:
        # Homebrew-formelen bygger whisper.cpp med WHISPER_BUILD_SERVER=OFF.
        merknader.append("whisper-server ble ikke funnet (Homebrew-pakken bygger den ikke). "
                         "Dikteringen bruker da whisper-cli og laster modellen for hvert "
                         "opptak, som er tregere enn å holde den lastet.")
    sha = None
    if not oppsett.modell.is_file():
        mangler.append("modell")
        url = f"https://huggingface.co/{oppsett.repo}/resolve/main/ggml-model.bin"
        tiltak.append(
            f"Modellen mangler: {oppsett.modell}\n"
            f"  {oppsett.repo}, ggml-model.bin, {oppsett.bytes / 1e9:.2f} GB. "
            f"Ingenting lastes ned automatisk. Vil du laste ned selv:\n"
            f"  mkdir -p \"{oppsett.modell.parent}\" && curl -L -o \"{oppsett.modell}\" {url}\n"
            f"  SHA256 sjekkes mot {oppsett.sha256} hver gang modellen lastes.")
    elif verifiser_sha:
        try:
            sha = verifiser_modell(oppsett.modell, oppsett.sha256)
        except ModellAvvik as e:
            mangler.append("modell-sha256")
            tiltak.append(str(e))
    ok = not mangler
    linjer = [f"norsk-tale {VERSJON} — modellvalg {oppsett.modellvalg}, målform {oppsett.malform} (whisper -l {oppsett.sprak})",
              f"  ffmpeg:          {'ok' if 'ffmpeg' not in mangler else 'MANGLER'}",
              f"  whisper-cli:     {oppsett.whisper_cli or 'MANGLER'}",
              f"  whisper-server:  {oppsett.whisper_server or 'finnes ikke (valgfri)'}",
              f"  modell:          {oppsett.modell}"
              + ("" if oppsett.modell.is_file() else "  (MANGLER)")]
    if sha:
        linjer.append(f"  SHA256:          ok ({sha[:12]}…)")
    linjer.extend(merknader)
    linjer.append("Alt er på plass." if ok else "\n".join(tiltak))
    return {"ok": ok, "mangler": mangler, "tiltak": tiltak, "merknader": merknader,
            "modell_sha256": sha,
            "versjon": VERSJON, "melding": "\n".join(linjer)}


def transkriber(lydfil, oppsett=None, sha=None):
    """Filbanen: én whisper-cli-kjøring per fil. Ingen sockets.

    `sha`: en SHA256 den som kaller allerede har verifisert i samme prosess
    (kalibreringsriggen kjører mange filer); ellers verifiseres modellen her."""
    oppsett = oppsett or standard_oppsett()
    lyd = pathlib.Path(lydfil).expanduser()
    if not lyd.is_file():
        raise KjerneFeil(f"Fant ikke lydfila: {lyd}")
    _sjekk_binar(oppsett.whisper_cli, "whisper-cli")
    sha = sha if sha == oppsett.sha256 else verifiser_modell(oppsett.modell, oppsett.sha256)
    prompt = vokabular_prompt(oppsett.vokabular)
    with tempfile.TemporaryDirectory(prefix="norsk-tale-") as tmp:
        tmp = pathlib.Path(tmp)
        wav, utbase = tmp / "lyd.wav", tmp / "ut"
        til_wav(lyd, wav)
        argv = [oppsett.whisper_cli, "-l", oppsett.sprak, "-m", oppsett.modell, "-f", wav,
                "-otxt", "-of", utbase, "-np", "-bs", str(STRALE), "-bo", str(BESTE_AV),
                "-tp", TEMPERATUR, *ekstra_whisper_args()]
        if prompt:
            argv += ["--prompt", prompt]
        _kjor(argv)
        verbatim = _rens((tmp / "ut.txt").read_text(encoding="utf-8"))
    return bygg_resultat(verbatim, oppsett, sha)


class Resident:
    """Modellen lastet én gang i en whisper-server på 127.0.0.1.

    Bruk som kontekstbehandler. Porten bindes kun til loopback; klienten går
    utenom alle proxy-innstillinger. Modellen verifiseres før serveren starter.
    """

    def __init__(self, oppsett=None, oppstart_s=180):
        self.oppsett = oppsett or standard_oppsett()
        self.oppstart_s = oppstart_s
        self.proc = None
        self.port = None
        self.sha = None
        self._logg = None
        self._apner = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stopp()

    def start(self):
        o = self.oppsett
        _sjekk_binar(o.whisper_server, "whisper-server")
        self.sha = verifiser_modell(o.modell, o.sha256)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        argv = [*PREFIKS, str(o.whisper_server), "--host", "127.0.0.1",
                "--port", str(self.port), "-m", str(o.modell), "-l", o.sprak,
                "-bs", str(STRALE), "-bo", str(BESTE_AV), *ekstra_whisper_args()]
        # whisper-server har ikke -tp; temperaturen sendes per forespørsel.
        # Serverloggen går til en midlertidig fil: en pipe ingen leser fylles
        # etter nok forespørsler, og da blokkerer serveren.
        self._logg = tempfile.TemporaryFile()
        self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=self._logg)
        frist = time.monotonic() + self.oppstart_s
        while time.monotonic() < frist:
            if self.proc.poll() is not None:
                self._logg.seek(0)
                hale = self._logg.read().decode("utf-8", "replace")[-600:]
                raise KjerneFeil(f"whisper-server stoppet under oppstart: {hale}")
            try:
                with self._apner.open(f"http://127.0.0.1:{self.port}/health", timeout=2) as r:
                    if r.status == 200:
                        return self
            except OSError:
                time.sleep(0.25)
        self.stopp()
        raise KjerneFeil("whisper-server svarte ikke innen fristen.")

    def stopp(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None
        if self._logg is not None:
            self._logg.close()
            self._logg = None

    @property
    def lastet(self):
        return self.proc is not None and self.proc.poll() is None

    def transkriber(self, lydfil, malform=None):
        """`malform` overstyrer oppsettets målform for denne forespørselen."""
        if not self.proc:
            raise KjerneFeil("Resident er ikke startet.")
        lyd = pathlib.Path(lydfil).expanduser()
        if not lyd.is_file():
            raise KjerneFeil(f"Fant ikke lydfila: {lyd}")
        with tempfile.TemporaryDirectory(prefix="norsk-tale-") as tmp:
            wav = pathlib.Path(tmp) / "lyd.wav"
            til_wav(lyd, wav)
            sprak = SPRAKKODE[malform] if malform else self.oppsett.sprak
            felt = {"language": sprak, "response_format": "text",
                    "temperature": TEMPERATUR, "beam_size": str(STRALE),
                    "best_of": str(BESTE_AV)}
            prompt = vokabular_prompt(self.oppsett.vokabular)
            if prompt:
                felt["prompt"] = prompt
            kropp, ctype = _multipart(felt, wav.read_bytes())
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/inference",
                                     data=kropp, headers={"Content-Type": ctype})
        with self._apner.open(req, timeout=600) as r:
            verbatim = _rens(r.read().decode("utf-8"))
        return bygg_resultat(verbatim, self.oppsett, self.sha)


def _multipart(felt, wavdata):
    grense = uuid.uuid4().hex
    deler = []
    for k, v in felt.items():
        deler.append(f'--{grense}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n'
                     f'{v}\r\n'.encode("utf-8"))
    deler.append(f'--{grense}\r\nContent-Disposition: form-data; name="file"; '
                 f'filename="lyd.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode("utf-8")
                 + wavdata + b"\r\n")
    deler.append(f"--{grense}--\r\n".encode("utf-8"))
    return b"".join(deler), f"multipart/form-data; boundary={grense}"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="norsk-tale-kjernen: lydfil inn, JSON ut på stdout. Ingenting lastes ned.")
    ap.add_argument("lydfil", nargs="?", type=pathlib.Path)
    ap.add_argument("--modellvalg", default=None, help="large | medium | small")
    ap.add_argument("--modell", default=None, help="sti til ggml-fila")
    ap.add_argument("--whisper", default=None, help="whisper-cli, navn eller sti")
    ap.add_argument("--malform", default=None, help="nb | nn | auto")
    ap.add_argument("--sjekk", action="store_true",
                    help="Sjekk ffmpeg, whisper.cpp og modell (med SHA256) uten å transkribere.")
    ap.add_argument("--uten-sha", action="store_true",
                    help="Hopp over SHA256 i --sjekk (raskere; ikke ved transkripsjon).")
    ap.add_argument("--krev-montert", metavar="STI", default=None,
                    help="Avslutt med kode 5 hvis STI ligger på et eksternt volum som ikke er montert.")
    ap.add_argument("--versjon", action="store_true")
    a = ap.parse_args(argv)
    if a.krev_montert:
        try:
            krev_montert(a.krev_montert)
            return 0
        except KjerneFeil as e:
            print(f"norsk-tale: {e}", file=sys.stderr)
            return 5
    if a.versjon:
        print(VERSJON)
        return 0
    try:
        oppsett = standard_oppsett(a.modellvalg, a.modell, a.whisper, a.malform)
        if a.sjekk:
            rapport = sjekk_oppsett(oppsett, verifiser_sha=not a.uten_sha)
            print(json.dumps(rapport, ensure_ascii=False, indent=2))
            return 0 if rapport["ok"] else 4
        if a.lydfil is None:
            ap.error("lydfil mangler")
        print(json.dumps(transkriber(a.lydfil, oppsett), ensure_ascii=False, indent=2))
        return 0
    except korriger.Avvisning as e:
        print(f"norsk-tale: fasittabellen avvist: {e}", file=sys.stderr)
        return 2
    except ModellAvvik as e:
        print(f"norsk-tale: {e}", file=sys.stderr)
        return 3
    except KjerneFeil as e:
        print(f"norsk-tale: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
