"""standard.py: utvalg, utpakking, gjenopptak og oppsummering med falske data."""
import io, json, pathlib, sys, tarfile

ROT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT / "kalibrering"))
import standard  # noqa: E402


def lag_data(tmp_path, n=40):
    data = tmp_path / "data"
    data.mkdir()
    linjer = []
    with tarfile.open(data / "nst_no_test_close-0001-of-0001.tar.gz", "w:gz") as tf:
        for i in range(n):
            pid, fil = f"no{i % 4:02d}x-sesjon", f"u{i:07d}.wav"
            linjer.append(json.dumps({"pid": pid, "file": fil, "text": f"setning nummer {i} ikke",
                                      "type": "R", "Speaker_ID": str(i % 4), "Region_of_Birth": "Oslo"}))
            innhold = f"RIFF{i}".encode()
            info = tarfile.TarInfo(f"nst/test/{pid}/{fil}")
            info.size = len(innhold)
            tf.addfile(info, io.BytesIO(innhold))
    (data / "nst_no_test_close-0001-of-0001.json").write_text("\n".join(linjer) + "\n", encoding="utf-8")
    return data


def test_utvalg_er_seedet_og_bare_ider(tmp_path):
    rader = standard.nst_rader(lag_data(tmp_path))
    a, b = standard.utvalg(rader, 10, 20261019), standard.utvalg(rader, 10, 20261019)
    assert a == b and len(a) == 10 and a == sorted(a)
    assert standard.utvalg(rader, 10, 1) != a
    ut = tmp_path / "ider.txt"
    standard.main(["utvalg", "--sett", "nst", "--data", str(tmp_path / "data"), "--n", "10",
                   "--seed", "20261019", "--ut", str(ut)])
    innhold = ut.read_text(encoding="utf-8")
    assert "seed=20261019" in innhold and "setning nummer" not in innhold and "RIFF" not in innhold
    assert [l for l in innhold.splitlines() if not l.startswith("#")] == a


def test_pakker_ut_bare_valgte_filer(tmp_path):
    data = lag_data(tmp_path)
    ider = standard.utvalg(standard.nst_rader(data), 5, 7)
    lyd = standard.pakk_ut(data, ider, tmp_path / "lyd")
    assert sorted(lyd) == ider and len(list((tmp_path / "lyd").iterdir())) == 5


def test_kjoring_gjenopptas_og_stopper_ved_ollama(tmp_path, monkeypatch):
    data = lag_data(tmp_path)
    rader = standard.nst_rader(data)
    ider = standard.utvalg(rader, 6, 3)
    lyd = standard.pakk_ut(data, ider, tmp_path / "lyd")
    monkeypatch.setattr(standard.kjerne, "verifiser_modell", lambda sti, f: f)
    monkeypatch.setattr(standard.kjerne, "standard_oppsett",
                        lambda **k: standard.kjerne.Oppsett("medium", tmp_path / "m.bin", "0" * 64, 1, "x",
                                                            None, None, (), ()))
    kall = []

    def falsk(wav, o, sha=None):
        kall.append((wav.name, o.malform))
        return {"verbatim": "setning nummer ikke", "korrigert": "setning nummer ikke"}

    monkeypatch.setattr(standard, "ollama_fri", lambda: True)
    utfil = tmp_path / "res.jsonl"
    assert standard.kjor(rader, ider, lyd, utfil, "medium", ["nb", "nn"], kjor_en=falsk) == 0
    assert len(kall) == 12
    assert standard.kjor(rader, ider, lyd, utfil, "medium", ["nb", "nn"], kjor_en=falsk) == 0
    assert len(kall) == 12                                # alt var ferdig: ingenting kjøres på nytt
    monkeypatch.setattr(standard, "ollama_fri", lambda: False)
    assert standard.kjor(rader, ider, lyd, tmp_path / "ny.jsonl", "medium", ["nb"], kjor_en=falsk) == 7


def test_oppsummering_er_bare_tall(tmp_path):
    utfil = tmp_path / "res.jsonl"
    rader = [{"id": "a/1", "malform_valgt": "nb", "modellvalg": "medium", "fasit": "det er ikke sant",
              "type": "R", "verbatim": "det er sant", "korrigert": "det er ikke sant"},
             {"id": "a/2", "malform_valgt": "nn", "modellvalg": "medium", "fasit": "aldri igjen",
              "type": "R", "verbatim": "aldri igjen", "korrigert": "aldri igjen"}]
    utfil.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rader) + "\n", encoding="utf-8")
    o = standard.oppsummer(utfil)
    nb = next(x for x in o if x["malform_valgt"] == "nb")
    assert nb["ra"]["wer"] == 0.25 and nb["korrigert"]["wer"] == 0.0
    assert nb["ra"]["nektelser"] == {"referanse": 1, "tapt": 1, "lagt_til": 0, "andel_tapt": 1.0}
    tekst = json.dumps(o, ensure_ascii=False)
    assert "sant" not in tekst and "igjen" not in tekst
