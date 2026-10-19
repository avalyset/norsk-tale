"""Hele kjeden uten mikrofon: lytterprosessen, kontrollkatalogen, stillhetsvakten,
resident whisper-server og kjernen — på et EKTE norsk opptak, som ligger UTENFOR
repoet, spilt i sanntid som om det var mikrofonen (NORSK_TALE_TESTKILDE).

  NORSK_TALE_TESTLYD=/sti/til/opptak.m4a NORSK_TALE_MODELL=... NORSK_TALE_WHISPER=... \
  python3 -m pytest tests/test_kjede.py -s
"""
import json, os, pathlib, subprocess, sys, tempfile, time
import pytest

LYTTER = pathlib.Path(__file__).resolve().parents[1] / "lytter" / "norsk_lytter.py"
TESTLYD = os.environ.get("NORSK_TALE_TESTLYD")
sys.path.insert(0, str(LYTTER.parents[1] / "kjerne"))
import kjerne  # noqa: E402


def _klar():
    try:
        o = kjerne.standard_oppsett()
    except Exception:
        return False
    return o.modell.is_file() and o.whisper_server is not None


@pytest.mark.skipif(not (TESTLYD and pathlib.Path(TESTLYD).is_file() and _klar()),
                    reason="krever NORSK_TALE_TESTLYD (ekte opptak utenfor repoet), modellen og whisper.cpp")
@pytest.mark.parametrize("stillhet_etter", [0, 3])
def test_kjede_fra_trykk_til_tekst(tmp_path, stillhet_etter):
    """stillhet_etter=0: opptaket som det er (kilden slutter). =3: tre sekunder
    digital stillhet lagt etter, så 1,5 s-regelen må avslutte opptaket."""
    kilde = TESTLYD
    if stillhet_etter:
        kilde = str(tmp_path / "med_stillhet.wav")
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", TESTLYD,
                        "-af", f"apad=pad_dur={stillhet_etter}", "-ar", "16000", "-ac", "1", kilde],
                       check=True)
    kontroll = tmp_path / "kontroll"
    tmp = pathlib.Path(tempfile.gettempdir())
    for_ = set(tmp.glob("norsk-tale-*"))
    p = subprocess.Popen([sys.executable, "-I", str(LYTTER), "--kontroll", str(kontroll)],
                         env={**os.environ, "NORSK_TALE_TESTKILDE": kilde},
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    hendelser = []
    try:
        assert json.loads(p.stdout.readline())["type"] == "oppe"
        (kontroll / "1.cmd").write_text("start")
        frist = time.monotonic() + 600
        while time.monotonic() < frist:
            linje = p.stdout.readline()
            assert linje, p.stderr.read()
            h = json.loads(linje)
            hendelser.append(h)
            if h["type"] in ("tekst", "feil", "tom"):
                break
        (kontroll / "2.cmd").write_text("avslutt")
        p.wait(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
    typer = [h["type"] for h in hendelser]
    print("\nhendelser:", typer)
    assert "feil" not in typer, hendelser[-1]
    assert typer[-1] == "tekst" and "lytter" in typer and "tale" in typer
    ut = hendelser[-1]["resultat"]
    print("slutt:", hendelser[-1]["slutt"])
    assert hendelser[-1]["slutt"] == ("stillhet" if stillhet_etter else "kilden sluttet")
    print("verbatim:", ut["verbatim"])
    print("korrigert:", ut["korrigert"])
    assert ut["verbatim"].strip()
    etter = set(tmp.glob("norsk-tale-*"))
    assert etter <= for_, f"midlertidig lyd ble liggende igjen: {etter - for_}"
