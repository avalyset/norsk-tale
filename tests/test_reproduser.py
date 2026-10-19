"""reproduser.py og sett.py: utvalg, forbehandling, SHA-stopp, gjenopptak og scoring med falske data."""
import io
import json
import pathlib
import sys
import tarfile
import zipfile

import pytest

ROT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT / "kalibrering"))
import reproduser  # noqa: E402
import sett  # noqa: E402
from sett import Rad  # noqa: E402


# ------------------------------------------------------------ forbehandling
def test_nst_opplest_tegnsetting_blir_tegn():
    assert sett.nst_fasit("hei \\Komma dette er en test \\Punktum") == "hei , dette er en test ."


def test_samtale_skrastrek_noling_og_avbrudd():
    t = "%eee det er s£ genialt med N_R_K-appen\\NRK-appen, og eg kommer\\kjem \\ein gong %heh"
    assert sett.samtale_fasit(t).split() == ["det", "er", "genialt", "med", "NRK-appen,", "og", "eg", "kjem",
                                             "ein", "gong"]


def test_nbtale_trans_hopper_over_merker_og_fonemer():
    tekst = ('#!TRANSCRIPTION!#\n"part_1/group_01/p1_g01_f1_4_x-a0001"\n0\t10\t<start>\t<start>\n'
             '10\t20\th\tHar\n20\t30\t"A:\n30\t40\td`\tdu\n40\t50\t<inhale>\t<inhale>\n')
    assert sett._nbtale_trans(tekst) == [("part_1/group_01/p1_g01_f1_4_x-a0001", ["Har", "du"])]


def test_npsc_utelukker_qq_og_fjerner_noling(tmp_path):
    d = tmp_path / "npsc_test"
    d.mkdir()
    rader = [
        {"path": "audio/a_1", "sentence_language_code": "nb-NO", "normsentence_text": "<ee> det er 18 saker"},
        {"path": "audio/a_2", "sentence_language_code": "nn-NO", "normsentence_text": "det er <qq> ikkje"},
        {"path": "audio/a_3", "sentence_language_code": "nn-NO", "normsentence_text": "<mm>"},
        {"path": "audio/a_4", "sentence_language_code": "en-US", "normsentence_text": "hello"},
    ]
    (d / "x.json").write_text("\n".join(json.dumps(r) for r in rader) + "\n", encoding="utf-8")
    r, ute = sett.npsc_rader(tmp_path)
    assert [x.id for x in r] == ["a_1"] and r[0].fasit.split() == ["det", "er", "18", "saker"]
    assert ute == {"tom_fasit": 1, "qq_inaudible": 1, "annet_sprak": 1}


# ------------------------------------------------------------------ utvalg
def test_trekk_er_seedet_stratifisert_og_sortert():
    rader = [Rad(f"{s}{i:03d}", "x", s, s) for s in ("nb", "nn") for i in range(50)]
    a = reproduser.trekk(rader, {"n_per_stratum": {"nb": 10, "nn": "alle"}}, 20261019)
    assert a == reproduser.trekk(rader, {"n_per_stratum": {"nb": 10, "nn": "alle"}}, 20261019)
    assert a == sorted(a) and sum(i.startswith("nb") for i in a) == 10 and sum(i.startswith("nn") for i in a) == 50
    assert reproduser.trekk(rader, {"n_per_stratum": {"nb": 10, "nn": "alle"}}, 1) != a
    with pytest.raises(SystemExit):
        reproduser.trekk(rader, {"n": 500}, 1)


def test_idliste_inneholder_bare_ider(tmp_path):
    tekst = reproduser.idliste_tekst("x", {"utvalg": {"n": 2}}, ["a/1", "b/2"], {"tom_fasit": 0}, 7)
    f = tmp_path / "l.txt"
    f.write_text(tekst, encoding="utf-8")
    assert reproduser.les_idliste(f) == ["a/1", "b/2"] and "seed=7" in tekst


# -------------------------------------------------------------- verifiser
def test_verifiser_stopper_ved_endret_kode(tmp_path, monkeypatch):
    f = tmp_path / "k.py"
    f.write_text("a", encoding="utf-8")
    monkeypatch.setattr(reproduser, "ROT", tmp_path)
    m = {"kode_sha256": {"k.py": reproduser.sha256(f)}, "sett": {}, "modeller": {}}
    assert reproduser.verifiser(m, data=False, modeller=False)
    f.write_text("b", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        reproduser.verifiser(m, data=False, modeller=False)
    assert e.value.code == 2


# ------------------------------------------------------------ scoring
def test_markorer_erstattes_med_kildeformen():
    assert reproduser.uten_markorer("det er ⟦nav → NAV?⟧ som betaler") == "det er nav som betaler"
    assert len(reproduser.MARKOR.findall("⟦a → b?⟧ og ⟦c → d?⟧")) == 2


def test_nektelser_telles_per_type():
    r = reproduser.nektelser_per_type([("det er ikke sant", "det er aldri sant"), ("ja", "ja")])
    assert r["tapt"] == 1 and r["lagt_til"] == 1 and r["tapt_per_100"] == 50.0


def test_ki_er_prosentilgrenser():
    idx = reproduser.bootstrap_indekser(4, "x", 20261019, 2000)
    lo, hi = reproduser.ki([0, 1, 2, 3], [4, 4, 4, 4], idx, 50, 1949)
    assert 0 <= lo <= 6 / 16 <= hi <= 0.75
    assert idx == reproduser.bootstrap_indekser(4, "x", 20261019, 2000)


# ------------------------------------------------------- kjøring og scor
def _manifest(tmp_path, liste):
    return {"versjon": "test", "seed": 1, "tidsgrense_s": 5, "maks_gjentak": 1,
            "bootstrap": {"B": 50, "nedre_indeks": 1, "ovre_indeks": 48},
            "whisper_cpp": {"ekstra_args": "", "backend": "metal"},
            "modellrekkefolge": ["medium"], "modeller": {"medium": {"fil": "m.bin", "sha256": "0" * 64}},
            "sett": {"fleurs": {"idliste": str(liste), "malformer": ["nb", "nn"], "prompt": ["pa", "av"]}}}


def test_kjoring_gjenopptas_scores_og_stopper_ved_ollama(tmp_path, monkeypatch):
    liste = tmp_path / "fleurs.txt"
    liste.write_text("# x\na.wav\nb.wav\n", encoding="utf-8")
    m = _manifest(tmp_path, liste)
    monkeypatch.setenv("NORSK_TALE_ARBEID", str(tmp_path / "arbeid"))
    monkeypatch.setenv("NORSK_TALE_MODELLER", str(tmp_path))
    monkeypatch.setenv("NORSK_TALE_WHISPER_CLI", str(tmp_path / "cli"))
    monkeypatch.setenv("NORSK_TALE_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(reproduser.kjerne, "verifiser_modell", lambda sti, f: f)
    monkeypatch.setattr(reproduser, "oppsett_for", lambda m, mv, mf, p: (mv, mf, p))
    monkeypatch.setattr(reproduser, "lyd_for", lambda m, n, ider, a: {i: tmp_path / i for i in ider})
    monkeypatch.setattr(reproduser, "ollama_fri", lambda: True)
    kall = []

    def falsk(lyd, o, sha, gjentak):
        kall.append((lyd.name, o))
        tekst = "det er ikke sant" if lyd.name == "a.wav" else "⟦hei → Hei?⟧ der"
        return {"status": "ok", "ra": tekst, "korrigert": tekst, "vegg_s": 1.0, "forsok": 1}

    assert reproduser.kjor(m, kjor_en=falsk) == 0 and len(kall) == 8
    assert reproduser.kjor(m, kjor_en=falsk) == 0 and len(kall) == 8      # alt ferdig: ingenting kjøres på nytt
    monkeypatch.setattr(reproduser.sett, "SETT", {"fleurs": (lambda d: ([Rad("a.wav", "det er ikke sant", "nb", ""),
                                                                          Rad("b.wav", "hei der", "nb", "")], {}),
                                                              None)})
    r = reproduser.scor(m, tmp_path / "arbeid" / "test")
    c = r["sett"]["fleurs"]["celler"]["alle"]["medium/nb/pa"]
    assert c["ra"]["wer"] == round(2 / 6, 4) and c["korrigert"]["wer"] == 0.0 and c["markorer"] == 1
    assert r["sett"]["fleurs"]["n_analyse"] == 2
    assert "sant" not in json.dumps(r) and "hei" not in json.dumps(r)
    m2 = _manifest(tmp_path, liste)
    m2["versjon"] = "ny"
    monkeypatch.setattr(reproduser, "ollama_fri", lambda: False)
    assert reproduser.kjor(m2, kjor_en=falsk) == 7


def test_feilet_ytring_utelukkes_i_alle_celler(tmp_path, monkeypatch):
    liste = tmp_path / "fleurs.txt"
    liste.write_text("a.wav\nb.wav\n", encoding="utf-8")
    m = _manifest(tmp_path, liste)
    arbeid = tmp_path / "arbeid" / "test" / "resultater"
    arbeid.mkdir(parents=True)
    linjer = []
    for uid in ("a.wav", "b.wav"):
        for mf in ("nb", "nn"):
            for p in ("pa", "av"):
                st = "tidsavbrudd" if (uid, mf, p) == ("b.wav", "nn", "av") else "ok"
                linjer.append({"id": uid, "malform": mf, "prompt": p, "status": st, "ra": "x", "korrigert": "x",
                               "vegg_s": 1.0})
    (arbeid / "fleurs.medium.jsonl").write_text("\n".join(json.dumps(x) for x in linjer) + "\n", encoding="utf-8")
    monkeypatch.setenv("NORSK_TALE_DATA", str(tmp_path))
    monkeypatch.setattr(reproduser.sett, "SETT", {"fleurs": (lambda d: ([Rad("a.wav", "x", "nb", ""),
                                                                          Rad("b.wav", "x", "nb", "")], {}), None)})
    r = reproduser.scor(m, tmp_path / "arbeid" / "test")["sett"]["fleurs"]
    assert r["n_analyse"] == 1 and r["utelukket_ved_kjoring"]["medium/nn/av"] == {"tidsavbrudd": 1}


def test_sett_pakker_ut_bare_valgte_fra_tar(tmp_path):
    d = tmp_path / "fleurs_nb_no"
    d.mkdir()
    with tarfile.open(d / "test.tar.gz", "w:gz") as tf:
        for n in ("a.wav", "b.wav", "c.wav"):
            info = tarfile.TarInfo(f"test/{n}")
            info.size = 4
            tf.addfile(info, io.BytesIO(b"RIFF"))
    ut = sett.fleurs_pakk_ut(tmp_path, ["a.wav", "c.wav"], tmp_path / "lyd")
    assert sorted(ut) == ["a.wav", "c.wav"] and len(list((tmp_path / "lyd").iterdir())) == 2


def test_samtale_pakker_ut_fra_zip(tmp_path):
    d = tmp_path / "nb_samtale"
    d.mkdir()
    with zipfile.ZipFile(d / "nb_samtale.zip", "w") as z:
        z.writestr("nb_samtale/data/test/bm/x_1-2.wav", b"RIFF")
        z.writestr("nb_samtale/data/test/bm/y_1-2.wav", b"RIFF")
    ut = sett.nb_samtale_pakk_ut(tmp_path, ["data/test/bm/x_1-2.wav", "data/test/bm/mangler.wav"], tmp_path / "lyd")
    assert list(ut) == ["data/test/bm/x_1-2.wav"]
