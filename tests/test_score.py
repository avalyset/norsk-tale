"""Scoring (kalibrering/score.py): håndlagde eksempler, ingen modell og ingen lyd."""
import json, pathlib, subprocess, sys
import pytest

ROT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT / "kalibrering"))
import score  # noqa: E402

SETNINGER = score.les_setninger(ROT / "selvtest" / "setninger.tsv")
FASIT = {s["id"]: s for s in SETNINGER}


# ------------------------------------------------------------ tallnormalisering
@pytest.mark.parametrize("tekst,forventet", [
    ("tre tusen fire hundre og femti kroner", ["3450", "kroner"]),
    ("3 450 kroner", ["3450", "kroner"]),
    ("3.450 kroner", ["3450", "kroner"]),
    ("3450,- kroner", ["3450", "kroner"]),
    ("tjuefem prosent", ["25", "prosent"]),
    ("25 %", ["25", "prosent"]),
    ("25%", ["25", "prosent"]),
    ("hundre og tjue", ["120"]),
    ("tjuetjuefem", ["2025"]),
    ("tjue tjuefem", ["2025"]),
    ("nitten nittifem", ["1995"]),
    ("femogtjue", ["25"]),
    ("fjortende", ["14"]),
    ("14.", ["14"]),
    ("sju saker", ["7", "saker"]),
    ("syv saker", ["7", "saker"]),
    ("tre eller fire", ["3", "eller", "4"]),
    ("tre og fire", ["3", "og", "4"]),            # «og» binder ikke to småtall
    ("tre fire", ["3", "4"]),                     # to tall, ikke 7
])
def test_tall_normaliseres(tekst, forventet):
    assert score.normaliser(tekst) == forventet


@pytest.mark.parametrize("tekst", ["en øl", "ei bok", "ett hus", "to av dem", "trenger",
                                   "tiden", "toget", "seksjonen"])
def test_tvetydige_ord_blir_ikke_tall(tekst):
    assert not any(o.isdigit() for o in score.normaliser(tekst))


# --------------------------------------------------------------------- nektelse
def test_tapt_nektelse_er_alltid_bom():
    r = score.score_setning(FASIT["1"], "Jeg har betalt de 3450 kronene til Skatteetaten ennå.")
    nekt = [e for e in r["elementer"] if e["type"] == "nektelse"]
    assert nekt and not nekt[0]["treff"]
    assert not r["bestatt"]
    assert {"type": "nektelse", "fasit": "ikke",
            "utdata": "Jeg har betalt de 3450 kronene til Skatteetaten ennå."} in r["bom"]


def test_nektelse_maa_vaere_eget_ord():
    """«ikkebetalt» eller «ikkeh» skal ikke regnes som nektelsen «ikke»."""
    r = score.score_setning(FASIT["1"], "Jeg har ikkebetalt de 3450 kronene til Skatteetaten.")
    assert not r["elementer"][0]["treff"]


def test_ikke_onsdag_maa_staa_samlet():
    r = score.score_setning(FASIT["2"], "Møtet er flyttet fra tirsdag 14. til onsdag 16. oktober, ikke torsdag.")
    nekt = [e for e in r["elementer"] if e["type"] == "nektelse"][0]
    assert not nekt["treff"], "byttet dag i nektelsen skal være bom"


# ------------------------------------------------------------------ navn og tall
def test_alle_fasitsetninger_bestaar_mot_seg_selv():
    for s in SETNINGER:
        r = score.score_setning(s, s["setning"])
        assert r["bestatt"], (s["id"], r["bom"])
        assert r["wer"] == 0 and r["cer"] == 0


def test_sifre_og_ord_er_likeverdige():
    r = score.score_setning(FASIT["3"], "Vi trenger 25 % flere søknader, men aldri flere enn 120 i året.")
    assert r["bestatt"], r["bom"]


def test_feil_tall_er_bom_og_vises_ordrett():
    ut = "Ingen av de seks sakene hos NAV ble avvist i 2025."
    r = score.score_setning(FASIT["4"], ut)
    assert not r["bestatt"]
    assert {"type": "tall", "fasit": "7", "utdata": ut} in r["bom"]


def test_feilstavet_etat_er_bom():
    r = score.score_setning(FASIT["5"], "Innovasjon Norge sa nei, og Horskningsrådet har ikke svart på søknaden fra mars.")
    assert [b["fasit"] for b in r["bom"]] == ["Forskningsrådet"]


def test_navn_uavhengig_av_store_bokstaver():
    r = score.score_setning(FASIT["4"], "ingen av de 7 sakene hos nav ble avvist i 2025")
    assert r["bestatt"], r["bom"]


# ---------------------------------------------------------------------- målform
def test_nynorsk_gjenkjennes():
    r = score.score_setning(FASIT["6"], "Eg har ikkje fått svar frå Statsforvaltaren om dei tre søknadene.")
    assert r["malform"] == {"forventet": "nn", "utdata": "nn", "funn": False}


def test_bokmaal_for_nynorsk_er_funn_ikke_bom():
    ut = "Jeg har ikke fått svar fra Statsforvalteren om de tre søknadene."
    r = score.score_setning(FASIT["6"], ut)
    assert r["malform"]["utdata"] == "nb" and r["malform"]["funn"] is True
    assert r["bestatt"], r["bom"]      # målform feller aldri setningen


# ---------------------------------------------------------- første innholdsord
def test_forste_innholdsord_hopper_over_funksjonsord():
    assert score.forste_innholdsord(FASIT["1"]["setning"]) == "betalt"
    assert score.forste_innholdsord(FASIT["4"]["setning"]) == "sakene"
    assert score.forste_innholdsord(FASIT["6"]["setning"]) == "fått"


def test_klippet_start_gir_bom():
    ut = "Et er flyttet fra tirsdag 14. til torsdag 16. oktober, ikke onsdag."
    r = score.score_setning(FASIT["2"], ut)
    assert r["forste_innholdsord"] == {"ord": "møtet", "treff": False}
    assert {"type": "første ord", "fasit": "møtet", "utdata": ut} in r["bom"]


# ------------------------------------------------------------------------ WER
def test_wer_og_cer():
    assert score.wer("a b c d", "a x c d") == 0.25
    assert score.cer("abcd", "abce") == 0.25


# ------------------------------------------------------------------------ CLI
def test_cli_leser_stdin_og_gir_json():
    r = subprocess.run([sys.executable, "-I", str(ROT / "kalibrering" / "score.py"),
                        "--setninger", str(ROT / "selvtest" / "setninger.tsv"), "--id", "4"],
                       input="Ingen av de syv sakene hos NAV ble avvist i 2025.",
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    ut = json.loads(r.stdout)
    assert ut["id"] == "4" and ut["bestatt"] is True


def test_cli_ukjent_id():
    r = subprocess.run([sys.executable, "-I", str(ROT / "kalibrering" / "score.py"),
                        "--setninger", str(ROT / "selvtest" / "setninger.tsv"), "--id", "99"],
                       input="x", capture_output=True, text=True)
    assert r.returncode == 2
