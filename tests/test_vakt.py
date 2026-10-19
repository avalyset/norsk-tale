"""Vakthunden: avbryter egen kjøring ved lite minne eller lite disk, rører ingenting annet."""
import pathlib, subprocess, sys, time

ROT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT / "kalibrering"))
import vakt  # noqa: E402

NORREGEL = pathlib.Path.home() / "dev" / "norregel" / "scripts" / "run_v2.sh"


def test_samme_minnemaal_som_run_v2():
    """Formelen i run_v2.sh er memory_pressure -Q, linja «free percentage», siste tall."""
    if NORREGEL.is_file():
        tekst = NORREGEL.read_text(encoding="utf-8")
        assert "memory_pressure -Q 2>/dev/null | grep -i 'free percentage'" in tekst
        assert "grep -oE '[0-9]+' | tail -1" in tekst
    m = vakt.ledig_minne_prosent()
    assert m is None or 0 <= m <= 100


def test_avbryter_ved_lite_minne_og_logger(tmp_path):
    logg = tmp_path / "vakt.log"
    malinger = iter([60, 60, 15, 15, 15])
    t0 = time.monotonic()
    kode, grunn = vakt.kjor(["sleep", "30"], str(logg), intervall=0.2,
                            maal_minne=lambda: next(malinger), maal_disk=lambda: 50.0)
    assert grunn == "minne 15 % < 20 %" and time.monotonic() - t0 < 10
    tekst = logg.read_text(encoding="utf-8")
    assert "AVBRYTER: minne 15 % < 20 %" in tekst and "SLUTT" in tekst


def test_avbryter_ved_lite_disk(tmp_path):
    disk = iter([50.0, 9.5, 9.5])
    kode, grunn = vakt.kjor(["sleep", "30"], str(tmp_path / "v.log"), intervall=0.2,
                            maal_minne=lambda: 60, maal_disk=lambda: next(disk))
    assert grunn == "disk 9.5 GiB < 10.0 GiB"


def test_starter_ikke_naar_grensen_alt_er_brutt(tmp_path):
    kode, grunn = vakt.kjor(["sleep", "30"], str(tmp_path / "v.log"), maal_minne=lambda: 12, maal_disk=lambda: 50.0)
    assert kode == 3 and "STOPP før start" in (tmp_path / "v.log").read_text(encoding="utf-8")


def test_gaar_ferdig_innenfor_grensene(tmp_path):
    kode, grunn = vakt.kjor([sys.executable, "-c", "pass"], str(tmp_path / "v.log"), intervall=0.2,
                            maal_minne=lambda: 60, maal_disk=lambda: 50.0)
    assert kode == 0 and grunn is None


def test_kjorer_med_nice_19(tmp_path):
    ut = tmp_path / "nice.txt"
    vakt.kjor(["sh", "-c", f"ps -o nice= -p $$ > {ut}"], str(tmp_path / "v.log"), intervall=0.2,
              maal_minne=lambda: 60, maal_disk=lambda: 50.0)
    assert ut.read_text().strip() == "19"
