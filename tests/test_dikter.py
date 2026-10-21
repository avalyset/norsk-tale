"""scripts/dikter: stdout er bare transkripsjonen, kode 0 også uten tale, opptaket
stopper på stillhet eller taket, og lyden slettes. Kjernen byttes ut med en falsk, så
ingen whisper kjøres her; ende-til-ende med modellen står nederst og hoppes over uten
NORSK_TALE_TESTLYD, NORSK_TALE_MODELL og NORSK_TALE_WHISPER.

Opptaksbanen prøves uten mikrofon: NORSK_TALE_TESTKILDE gir ffmpeg en fil å spille i
sanntid (-re) i stedet for mikrofonen."""
import importlib.machinery
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

ROT = pathlib.Path(__file__).resolve().parents[1]
SKRIPT = ROT / "scripts" / "dikter"
sys.path.insert(0, str(ROT / "lytter"))
import norsk_lytter  # noqa: E402

_loader = importlib.machinery.SourceFileLoader("dikter", str(SKRIPT))
_spec = importlib.util.spec_from_loader("dikter", _loader)
dikter = importlib.util.module_from_spec(_spec)
_loader.exec_module(dikter)

FFMPEG = shutil.which("ffmpeg")
trenger_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="krever ffmpeg")


class Oppsett:
    pass


class FalskKjerne:
    """Samme grensesnitt som kjerne/kjerne.py, så langt skriptet bruker det."""

    def __init__(self, tekst="hei verden", ok=True, melding="", feil=None):
        self.tekst, self.ok, self.melding, self.feil = tekst, ok, melding, feil
        self.oppsett_arg = None
        self.lydfiler = []

    def standard_oppsett(self, **kw):
        self.oppsett_arg = kw
        return Oppsett()

    def sjekk_oppsett(self, oppsett, verifiser_sha=True):
        assert verifiser_sha is False       # SHA verifiseres av transkriber, ikke her
        return {"ok": self.ok, "melding": self.melding}

    def transkriber(self, lyd, oppsett=None):
        lyd = pathlib.Path(lyd)
        self.lydfiler.append((lyd, lyd.stat().st_size if lyd.exists() else None))
        if self.feil:
            raise self.feil
        return {"korrigert": self.tekst, "verbatim": self.tekst}


def kjor(argv, kjerne, capsys):
    kode = dikter.hoved(argv, kjerne=kjerne)
    return kode, capsys.readouterr().out


def lag_kilde(sti, grafikk):
    """Lager en testlydfil med ffmpeg: (kilde, sekunder) per bit, rekkefølge bevart."""
    deler, inn, i = [], [], 0
    for kilde, s in grafikk:
        inn += ["-f", "lavfi", "-t", str(s), "-i", kilde]
        deler.append(f"[{i}:a]")
        i += 1
    filter_ = "".join(deler) + f"concat=n={i}:v=0:a=1[ut]"
    subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-y", *inn, "-filter_complex", filter_,
                    "-map", "[ut]", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(sti)], check=True)
    return sti


TONE = "sine=frequency=300:sample_rate=16000,volume=8"            # rms godt over terskelen
STILLE = "anoisesrc=a=0.001:sample_rate=16000"                     # bråk under terskelen, ikke null
NULL = "anullsrc=r=16000:cl=mono"                                  # eksakt null: ingen mikrofontilgang


# ---------------------------------------------------------------- stdout og kode
def test_stdout_er_bare_transkripsjonen_og_koden_er_0(capsys):
    k = FalskKjerne(tekst="  hei \n  verden  ")
    kode, ut = kjor(["--fil", "/x/finnes.wav"], k, capsys)
    assert (kode, ut) == (0, "hei verden\n")


def test_tom_tale_gir_tydelig_melding_og_kode_0(capsys):
    kode, ut = kjor(["--fil", "/x/a.wav"], FalskKjerne(tekst="   "), capsys)
    assert kode == 0
    assert ut.startswith(dikter.PREFIKS) and "Ingen ord" in ut and ut.count("\n") == 1


def test_manglende_oppsett_gir_melding_og_kode_0_uten_a_ta_opp(capsys):
    k = FalskKjerne(ok=False, melding="whisper-cli: MANGLER")
    kode, ut = kjor(["--fil", "/x/a.wav"], k, capsys)
    assert (kode, ut) == (0, "[norsk-tale] whisper-cli: MANGLER\n")
    assert k.lydfiler == []


def test_feil_i_kjernen_gir_melding_og_kode_0(capsys):
    kode, ut = kjor(["--fil", "/x/a.wav"], FalskKjerne(feil=RuntimeError("SHA256 stemmer ikke")), capsys)
    assert kode == 0 and ut == "[norsk-tale] FEIL: SHA256 stemmer ikke\n"


def test_innstillingene_fra_skillen_naar_kjernen_tomme_som_ingen(capsys):
    k = FalskKjerne()
    kjor(["--fil", "/x/a.wav", "--modellvalg", "medium", "--malform", "nn", "--modell", "", "--whisper", "/w/cli"], k, capsys)
    assert k.oppsett_arg == {"modellvalg": "medium", "modell": None, "whisper": "/w/cli", "malform": "nn"}


def test_markorer_fra_korrektoren_blir_staende(capsys):
    _, ut = kjor(["--fil", "/x/a.wav"], FalskKjerne(tekst="møt ⟦ola → Ola?⟧ i morgen"), capsys)
    assert ut == "møt ⟦ola → Ola?⟧ i morgen\n"


# ---------------------------------------------------------------- opptaksbanen
@trenger_ffmpeg
def test_opptaket_stopper_paa_stillhet_etter_tale(tmp_path, monkeypatch):
    kilde = lag_kilde(tmp_path / "k.wav", [(NULL, 0.1), (TONE, 1.5), (STILLE, 4)])
    monkeypatch.setenv("NORSK_TALE_TESTKILDE", str(kilde))
    pcm, grunn = dikter.ta_opp(FFMPEG, maks_s=20, ingen_tale_s=5)
    sek = len(pcm) / 2 / 16000
    assert grunn == "stillhet"
    assert 2.0 < sek < 4.2, sek            # pre-roll + tale + 1,5 s stillhet, ikke hele kilden


@trenger_ffmpeg
def test_opptaket_stopper_paa_taket(tmp_path, monkeypatch):
    kilde = lag_kilde(tmp_path / "k.wav", [(TONE, 8)])
    monkeypatch.setenv("NORSK_TALE_TESTKILDE", str(kilde))
    pcm, grunn = dikter.ta_opp(FFMPEG, maks_s=2.5, ingen_tale_s=5)
    assert grunn == "tak"
    assert len(pcm) / 2 / 16000 <= 2.6


@trenger_ffmpeg
def test_ingen_tale_gir_avbrutt_med_melding(tmp_path, monkeypatch):
    kilde = lag_kilde(tmp_path / "k.wav", [(STILLE, 6)])
    monkeypatch.setenv("NORSK_TALE_TESTKILDE", str(kilde))
    with pytest.raises(dikter.Avbrutt, match="Ingen tale hørt"):
        dikter.ta_opp(FFMPEG, maks_s=20, ingen_tale_s=1.5)


@trenger_ffmpeg
def test_bare_nuller_betyr_manglende_mikrofontilgang(tmp_path, monkeypatch):
    kilde = lag_kilde(tmp_path / "k.wav", [(NULL, 3)])
    monkeypatch.setenv("NORSK_TALE_TESTKILDE", str(kilde))
    with pytest.raises(dikter.Avbrutt, match="Ingen mikrofontilgang"):
        dikter.ta_opp(FFMPEG, maks_s=20, ingen_tale_s=5)


@trenger_ffmpeg
def test_hele_kjeden_med_testkilde_gir_wav_til_kjernen_og_sletter_den_etterpaa(tmp_path, monkeypatch, capsys):
    kilde = lag_kilde(tmp_path / "k.wav", [(NULL, 0.1), (TONE, 1.2), (STILLE, 4)])
    monkeypatch.setenv("NORSK_TALE_TESTKILDE", str(kilde))
    monkeypatch.setattr(dikter.shutil, "which", lambda n: FFMPEG if n == "ffmpeg" else None)
    k = FalskKjerne(tekst="diktert tekst")
    kode, ut = kjor(["--ingen-tale-s", "5"], k, capsys)
    assert (kode, ut) == (0, "diktert tekst\n")
    (wav, storrelse), = k.lydfiler
    assert storrelse > 16000 * 2          # minst ett sekund PCM var med
    assert not wav.exists(), "opptaket skal slettes etter transkripsjonen"
    assert not wav.parent.exists()


@trenger_ffmpeg
def test_uten_ffmpeg_gir_melding_og_kode_0(monkeypatch, capsys):
    monkeypatch.setattr(dikter.shutil, "which", lambda n: None)
    kode, ut = kjor([], FalskKjerne(), capsys)
    assert kode == 0 and ut.startswith("[norsk-tale] Fant ikke ffmpeg")


def test_taket_og_ingen_tale_grensene_er_som_spesifisert():
    assert dikter.MAKS_S == 90.0 and dikter.INGEN_TALE_S == 10.0
    assert norsk_lytter.Stillhetsvakt(tak_s=dikter.MAKS_S).stillhet_rammer == round(1.5 * 1000 / norsk_lytter.RAMME_MS)


# ---------------------------------------------------------------- ende til ende
TESTLYD = os.environ.get("NORSK_TALE_TESTLYD")
MODELL = os.environ.get("NORSK_TALE_MODELL")
WHISPER = os.environ.get("NORSK_TALE_WHISPER")
ekte = pytest.mark.skipif(not (TESTLYD and MODELL and WHISPER and pathlib.Path(MODELL).is_file()),
                          reason="krever NORSK_TALE_TESTLYD, NORSK_TALE_MODELL og NORSK_TALE_WHISPER")


@ekte
def test_ende_til_ende_med_ekte_modell_via_fil():
    """Én ny whisper-cli-prosess, SHA256 verifisert i kjernen, én linje på stdout."""
    r = subprocess.run([str(SKRIPT), "--fil", TESTLYD], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    assert r.stderr == ""
    linjer = r.stdout.splitlines()
    assert len(linjer) == 1 and linjer[0] and not linjer[0].startswith(dikter.PREFIKS), r.stdout
    forventet = os.environ.get("NORSK_TALE_TESTTEKST")
    if forventet:
        assert linjer[0] == forventet


@ekte
def test_ende_til_ende_med_feil_modellsha_gir_melding_og_kode_0(tmp_path):
    falsk = tmp_path / "ggml-model.bin"
    falsk.write_bytes(b"ikke en modell")
    r = subprocess.run([str(SKRIPT), "--fil", TESTLYD, "--modell", str(falsk)], capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0
    assert r.stdout.startswith("[norsk-tale]") and ("SHA256" in r.stdout or "sha256" in r.stdout.lower())
