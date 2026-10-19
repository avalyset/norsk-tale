"""aggreger.py: tallbidrag, opprulling og dialektkilde. Ingen lyd, ingen tekst."""
import json, pathlib, subprocess, sys

ROT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT / "kalibrering"))
import aggreger, score  # noqa: E402

MANUS = score.les_setninger(ROT / "kalibrering" / "manus_v1.tsv")
FASIT = {s["id"]: s for s in MANUS}
RIKTIG = "Helfo har ikke utbetalt de 2000 kronene ennå."
TAPT = "Helfo har utbetalt de 2000 kronene ennå."
MODELL = {"modellvalg": "large", "modell_sha256": "f" * 64, "kjerne_versjon": "0.1.0", "norsk_tale_versjon": "0.1.0"}


def resultat(utdata):
    sc = score.score_setning(FASIT["nb31"], utdata)
    return {"rader": [{"manus_id": "nb31", "fasit": FASIT["nb31"]["setning"],
                       "varianter": {"nb/med": {"korrigert": {"utdata": utdata, "scoring": sc},
                                                "ra": {"utdata": utdata, "scoring": sc}}}}]}


def bidrag(region, kilde, utdata, malepunkt=None, n_talere=1):
    celler = aggreger.celler_for_runde(resultat(utdata), FASIT)
    return aggreger.lag_bidrag(celler, MODELL, region, kilde, "nb", malepunkt=malepunkt, n_talere=n_talere)


def alle(bs):
    return [(f"t{i}", b) for i, b in enumerate(bs)]


# ----------------------------------------------------------------- formatet
def _strenger(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from _strenger(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strenger(v)
    elif isinstance(x, str):
        yield x


def test_bidrag_inneholder_bare_tall_og_etiketter():
    b = bidrag("Vestlandet", "morsmål", TAPT)
    tekst = json.dumps(b, ensure_ascii=False)
    for forbudt in ("Helfo har", "utbetalt", "kronene", ".wav", "RIFF", "utdata", "fasit"):
        assert forbudt not in tekst, forbudt
    lovlige = {"nb", "nn", "med", "uten", "korrigert", "ra", "kombinert", "Vestlandet", "morsmål",
               "manus_v1", "large", "0.1.0", "f" * 64, "region"}
    nokler = {"norsk_tale_bidrag", "manus", "modell", "modellvalg", "modell_sha256", "kjerne_versjon",
              "norsk_tale_versjon", "dialektregion", "dialektkilde", "malepunkt", "malform", "n_talere",
              "celler", "klasse", "malform_valgt", "vokabular", "tekst", "n_setninger", "ord_feil",
              "ord_ref", "tegn_feil", "tegn_ref", "feil", "nektelse", "tall", "navn", "første ord",
              "målform", "bom", "av", "rullet_opp"}
    assert set(_strenger(b)) <= lovlige | nokler, set(_strenger(b)) - lovlige - nokler
    c = next(c for c in b["celler"] if c["tekst"] == "korrigert")
    # NB-Whisper-normen normaliserer ikke tall: «to tusen» mot «2000» er to ordfeil,
    # pluss den tapte nektelsen.
    assert c["feil"]["nektelse"] == {"bom": 1, "av": 1} and c["ord_ref"] == 9 and c["ord_feil"] == 3


def test_under_tre_talere_rulles_malepunktet_opp_til_region():
    b = bidrag("Vestlandet", "morsmål", RIKTIG, malepunkt="Voss")
    assert b["malepunkt"] is None and b["rullet_opp"] == "region" and b["dialektregion"] == "Vestlandet"
    b3 = bidrag("Vestlandet", "morsmål", RIKTIG, malepunkt="Voss", n_talere=3)
    assert b3["malepunkt"] == "Voss"


def test_kilde_uten_region_fjernes():
    assert bidrag(None, "morsmål", RIKTIG)["dialektkilde"] is None


# --------------------------------------------------------------- aggregering
def test_morsmaal_og_imitert_slaas_aldri_sammen():
    bs = [bidrag("Vestlandet", "morsmål", RIKTIG), bidrag("Vestlandet", "morsmål", TAPT),
          bidrag("Vestlandet", "morsmål", RIKTIG), bidrag("Vestlandet", "imitert", TAPT)]
    rader = aggreger.aggreger(alle(bs))
    assert len(rader) == 1
    k = rader[0]["kilder"]
    assert set(k) == {"morsmål", "imitert"}
    assert k["morsmål"]["talere"] == 3 and k["morsmål"]["feil"]["nektelse"] == {"bom": 1, "av": 3}
    assert k["imitert"]["talere"] == 1 and k["imitert"]["feil"]["nektelse"] == {"bom": 1, "av": 1}
    assert k["morsmål"]["wer"] == round((2 + 3 + 2) / 27, 4)  # sammenslått: sum feil / sum ord


def test_celler_under_tre_talere_er_for_faa():
    bs = [bidrag("Trøndelag", "morsmål", RIKTIG), bidrag("Trøndelag", "morsmål", RIKTIG)]
    assert aggreger.aggreger(alle(bs))[0]["kilder"]["morsmål"]["for_faa"] is True
    bs.append(bidrag("Trøndelag", "morsmål", RIKTIG))
    assert aggreger.aggreger(alle(bs))[0]["kilder"]["morsmål"]["for_faa"] is False


def test_malepunkt_vises_bare_med_minst_tre_talere():
    voss = [bidrag("Vestlandet", "morsmål", RIKTIG, malepunkt="Voss", n_talere=3) for _ in range(2)]
    rader = aggreger.aggreger(alle(voss))
    assert [r["malepunkt"] for r in rader] == [None]       # 2 talere på Voss: bare regionsraden
    voss.append(bidrag("Vestlandet", "morsmål", RIKTIG, malepunkt="Voss", n_talere=3))
    rader = aggreger.aggreger(alle(voss))
    assert sorted(str(r["malepunkt"]) for r in rader) == ["None", "Voss"]


def test_samme_bidrag_to_ganger_er_en_taler():
    b = bidrag("Nord-Norge", "morsmål", RIKTIG)
    par = [(aggreger.taler_id(b), b), (aggreger.taler_id(json.loads(json.dumps(b))), b)]
    c = aggreger.aggreger(par)[0]["kilder"]["morsmål"]
    assert c["talere"] == 1 and c["n_setninger"] == 2


def test_cli(tmp_path):
    filer = []
    for i, k in enumerate(["morsmål", "imitert"]):
        f = tmp_path / f"b{i}.json"
        f.write_text(json.dumps(bidrag("Sørlandet", k, RIKTIG), ensure_ascii=False), encoding="utf-8")
        filer.append(str(f))
    r = subprocess.run([sys.executable, "-I", str(ROT / "kalibrering" / "aggreger.py"), *filer],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "morsmål: 1 talere (for få)" in r.stdout and "imitert: 1 talere (for få)" in r.stdout
