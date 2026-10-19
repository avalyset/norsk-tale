"""Stillhetsvakten: pre-roll, 1,5 s stillhet, tak, null-signal.

Rammene er konstruerte PCM-tallrekker for å teste tilstandsmaskinen — ikke
tale og ikke ASR-bevis. Ekte transkripsjon testes i test_kjede.py og test_kjerne.py.
"""
import array, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lytter"))
import norsk_lytter as nl  # noqa: E402

N = nl.RAMME_BYTES // 2   # sampler per ramme


def ramme(amplitude):
    return array.array("h", [amplitude if i % 2 else -amplitude for i in range(N)]).tobytes()


STILLE, HOY, NULL = ramme(20), ramme(4000), ramme(0)


def mat(vakt, r, antall):
    for _ in range(antall):
        grunn = vakt.mat(r)
        if grunn:
            return grunn
    return None


def rammer(s):
    return round(s * 1000 / nl.RAMME_MS)


def test_preroll_er_en_halv_sekund_for_innsats():
    v = nl.Stillhetsvakt()
    assert mat(v, STILLE, rammer(2.0)) is None
    assert mat(v, HOY, 3) is None and v.har_tale
    # pre-roll-bufferet (0,5 s) inneholder de tre høye rammene; resten er stillhet før innsats
    assert len(v.tale) == rammer(0.5) * nl.RAMME_BYTES
    assert v.tale.endswith(HOY * 3)


def test_ett_og_et_halvt_sekund_stillhet_avslutter():
    v = nl.Stillhetsvakt()
    mat(v, HOY, rammer(1.0))
    assert mat(v, STILLE, rammer(1.5) - 1) is None
    assert v.mat(STILLE) == "stillhet"


def test_kort_pause_avslutter_ikke():
    v = nl.Stillhetsvakt()
    mat(v, HOY, rammer(1.0))
    assert mat(v, STILLE, rammer(1.0)) is None
    assert mat(v, HOY, rammer(0.5)) is None
    assert mat(v, STILLE, rammer(1.2)) is None


def test_tak_paa_to_minutter():
    v = nl.Stillhetsvakt()
    assert mat(v, HOY, rammer(120) + 5) == "tak"
    assert v.rammer == rammer(120)


def test_bare_nuller_gir_mikrofonfeil():
    v = nl.Stillhetsvakt()
    mat(v, NULL, rammer(1.0))
    assert v.bare_nuller() and not v.har_tale
    v2 = nl.Stillhetsvakt()
    mat(v2, STILLE, rammer(1.0))
    assert not v2.bare_nuller()


def test_tale_rett_etter_trykket_gir_innsats():
    """Talen skal ikke løfte sin egen terskel: gulvet har et tak."""
    v = nl.Stillhetsvakt()
    assert mat(v, HOY, 3) is None and v.har_tale


def test_stoy_over_gulvet_er_ikke_tale():
    """Jevn bakgrunnsstøy måles som gulv (×3) og utløser ikke."""
    v = nl.Stillhetsvakt()
    stoy = ramme(400)
    assert mat(v, stoy, rammer(3.0)) is None
    assert not v.har_tale


def test_mikrofon_argv_tvinger_16k_mono():
    argv = nl.mikrofon_argv("ffmpeg")
    assert argv[-7:] == ["-ac", "1", "-ar", "16000", "-f", "s16le", "-"]


# ------------------------------------------------- modellens livsløp (falsk kjerne)
class FalskResident:
    startet = 0
    stoppet = 0

    def __init__(self, oppsett):
        self.sha = "f" * 64
        self.aktiv = False

    def start(self):
        FalskResident.startet += 1
        self.aktiv = True
        return self

    def stopp(self):
        FalskResident.stoppet += 1
        self.aktiv = False


class FalskOppsett:
    whisper_server = "whisper-server"


class FalskKjerne:
    Resident = FalskResident
    mangler = []
    oppsett = FalskOppsett()
    filkall = []

    @classmethod
    def standard_oppsett(cls, **_):
        return cls.oppsett

    @classmethod
    def transkriber(cls, wav, oppsett):
        cls.filkall.append(wav)
        return {"verbatim": "ja", "korrigert": "ja", "substitusjonslogg": [],
                "modell_sha256": "f" * 64, "versjon": "0"}

    @classmethod
    def sjekk_oppsett(cls, o, verifiser_sha=True):
        return {"ok": not cls.mangler, "mangler": list(cls.mangler)}


class FalskOpptak:
    def __init__(self, ffmpeg, vakt):
        self.vakt = vakt
        self.feil = None
        self.grunn = "trykk"
        self.ferdig = __import__("threading").Event()
        self.ferdig.set()

    def stopp(self):
        pass


def _lytter(monkeypatch, klokke):
    FalskResident.startet = FalskResident.stoppet = 0
    FalskKjerne.mangler = []
    FalskKjerne.oppsett = FalskOppsett()
    FalskKjerne.filkall = []
    monkeypatch.setattr(nl, "Opptak", FalskOpptak)
    return nl.Lytter(FalskKjerne, {}, frigjor_s=600, klokke=lambda: klokke[0])


def test_modellen_lastes_forst_ved_trykk(monkeypatch):
    t = [0.0]
    lytter = _lytter(monkeypatch, t)
    assert FalskResident.startet == 0 and lytter.resident is None
    lytter.start()
    lytter.laster.join()
    assert FalskResident.startet == 1 and lytter.resident is not None


def test_frigjores_etter_ti_minutter_uten_aktivitet(monkeypatch, capsys):
    t = [0.0]
    lytter = _lytter(monkeypatch, t)
    lytter.start()
    lytter.laster.join()
    lytter.poll()                      # opptaket (uten tale) avsluttes, aktivitet nå
    t[0] = 599.0
    lytter.poll()
    assert lytter.resident is not None and FalskResident.stoppet == 0
    t[0] = 600.0
    lytter.poll()
    assert lytter.resident is None and FalskResident.stoppet == 1
    assert '"type": "frigjort"' in capsys.readouterr().out


def test_nytt_trykk_etter_frigjoring_laster_paa_nytt(monkeypatch):
    t = [0.0]
    lytter = _lytter(monkeypatch, t)
    lytter.start(); lytter.laster.join(); lytter.poll()
    t[0] = 700.0
    lytter.poll()
    assert lytter.resident is None
    lytter.start(); lytter.laster.join()
    assert FalskResident.startet == 2 and lytter.resident is not None


def test_mangel_gir_en_melding_og_ingen_lasting(monkeypatch, capsys):
    t = [0.0]
    lytter = _lytter(monkeypatch, t)
    FalskKjerne.mangler = ["modell"]
    lytter.start()
    ut = capsys.readouterr().out
    assert "mangler: modell" in ut and "/norsk oppsett" in ut
    assert FalskResident.startet == 0 and lytter.opptak is None
    FalskKjerne.mangler = []          # rettet installasjon virker uten omstart
    lytter.start(); lytter.laster.join()
    assert FalskResident.startet == 1


def test_uten_whisper_server_brukes_filbanen(monkeypatch, capsys):
    """Homebrew bygger ikke whisper-server: da transkriberes hvert opptak med
    kjernens filbane, og ingen resident startes."""
    t = [0.0]
    lytter = _lytter(monkeypatch, t)
    FalskKjerne.oppsett = type("UtenServer", (), {"whisper_server": None})()

    class MedTale(FalskOpptak):
        def __init__(self, ffmpeg, vakt):
            super().__init__(ffmpeg, vakt)
            vakt.har_tale = True
            vakt.tale.extend(b"\x00\x01" * 160)

    monkeypatch.setattr(nl, "Opptak", MedTale)
    lytter.start()
    assert lytter.laster is None and FalskResident.startet == 0
    lytter.poll()
    assert len(FalskKjerne.filkall) == 1
    assert '"type": "tekst"' in capsys.readouterr().out
