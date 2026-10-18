"""Stillhetsvakten: pre-roll, 1,5 s stillhet, tak, null-signal.

Rammene er konstruerte PCM-tallrekker for å teste tilstandsmaskinen — ikke
tale og ikke ASR-bevis. Ekte transkripsjon testes mot ekte opptak i NORSKRIBER.
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
