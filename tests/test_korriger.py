"""§ 8f — tester for entitetskorrektoren."""
import sys, pathlib, pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "kjerne"))
import korriger  # noqa: E402

OFFENTLIG = pathlib.Path(__file__).resolve().parents[1] / "kjerne" / "vokabular" / "fasit_offentlig.tsv"


def skriv_fasit(tmp_path, rader, navn="fasit.tsv"):
    p = tmp_path / navn
    p.write_text("korrekt_form\tfeilform\tklasse\tfeilklasse\n"
                 + "\n".join("\t".join(r) for r in rader) + "\n", encoding="utf-8")
    return p


def kjor(tekst, rader):
    return korriger.korriger(tekst, rader)


# ---------------------------------------------------------------- containment
def test_containment_smart_innovasjon_norge():
    """Den lengre formen vinner. Interiøret røres ikke, og de to målformene
    limes aldri sammen."""
    rader = [
        {"korrekt_form": "Smart Innovation Norway", "feilform": "Smart Innovasjon Norge",
         "klasse": "kollisjon", "feilklasse": "usikker", "kilde": "test:1"},
        {"korrekt_form": "Innovasjon Norge", "feilform": "Inorsk Norge",
         "klasse": "ikkeord", "feilklasse": "garble", "kilde": "test:2"},
    ]
    ut, h, _ = kjor("Vi snakket med Smart Innovasjon Norge i går.", rader)
    assert "⟦Smart Innovasjon Norge → Smart Innovation Norway?⟧" in ut
    assert "Smart Innovation NorwayNorge" not in ut
    assert "Smart Innovation Norway Norge" not in ut
    # interiøret er uendret inne i markøren
    assert ut.count("Smart Innovasjon Norge") == 1
    assert len(h) == 1 and h[0]["handling"] == "flagget"


def test_containment_korrekt_form_inne_i_lengre_er_urort():
    """«Innovasjon Norge» som korrekt form skal aldri plukkes opp inne i den
    lengre feilformen."""
    rader = [
        {"korrekt_form": "Smart Innovation Norway", "feilform": "Smart Innovasjon Norge",
         "klasse": "kollisjon", "feilklasse": "usikker", "kilde": "test:1"},
    ]
    ut, h, _ = kjor("Smart Innovasjon Norge og Innovasjon Norge er ikke det samme.", rader)
    assert ut.count("Innovasjon Norge") == 2   # ett i markøren, ett fritt
    assert len(h) == 1


# -------------------------------------------------------------------- ikkeord
def test_ikkeord_substitueres_og_logges():
    rader = [{"korrekt_form": "Forskningsrådet", "feilform": "Horskningsrådet",
              "klasse": "ikkeord", "feilklasse": "garble", "kilde": "test:1"}]
    ut, h, tall = kjor("Han ringte Horskningsrådet på mandag.", rader)
    assert "Forskningsrådet" in ut and "Horskningsrådet" not in ut
    assert "⟦" not in ut
    assert tall["substituert"] == 1
    assert h[0]["fra"] == "Horskningsrådet" and h[0]["til"] == "Forskningsrådet"
    assert h[0]["linje"] == 1


def test_ikkeord_bevarer_case():
    rader = [{"korrekt_form": "Forskningsrådet", "feilform": "Horskningsrådet",
              "klasse": "ikkeord", "feilklasse": "garble", "kilde": "test:1"}]
    ut, _, _ = kjor("horskningsrådet og Horskningsrådet", rader)
    assert "forskningsrådet og Forskningsrådet" in ut


# --------------------------------------------------------------- sammensetning
def test_sammensetning_beholder_setningen_intakt():
    """Målformen er sammensetningen. «Tindå» alene ville ødelagt setningen."""
    rader = [
        {"korrekt_form": "Tindå-trådene", "feilform": "Tindetrådene",
         "klasse": "ikkeord", "feilklasse": "garble", "kilde": "test:1"},
        {"korrekt_form": "Tindå", "feilform": "Tinda",
         "klasse": "ikkeord", "feilklasse": "garble", "kilde": "test:2"},
    ]
    ut, h, _ = kjor("Vi må nøste opp Tindetrådene før møtet.", rader)
    assert ut == "Vi må nøste opp Tindå-trådene før møtet."
    assert "Tindåtrådene" not in ut          # ikke limt sammen
    assert not ut.endswith("Tindå før møtet.")  # ikke amputert
    assert h[0]["til"] == "Tindå-trådene"


# ------------------------------------------------------------------ kollisjon
def test_kollisjon_star_urort_med_markor():
    rader = [{"korrekt_form": "Lindqvist", "feilform": "Lindkvist",
              "klasse": "kollisjon", "feilklasse": "lyd-tvetydig", "kilde": "test:1"}]
    ut, h, tall = kjor("Vi solgte den hos Lindkvist i fjor.", rader)
    assert "⟦Lindkvist → Lindqvist?⟧" in ut
    assert tall["flagget"] == 1 and tall["substituert"] == 0
    assert h[0]["handling"] == "flagget" and h[0]["klasse"] == "kollisjon"


# ------------------------------------------------------------- avvisning (§ 8e)
def test_invariantbrudd_gir_ikke_null_exit(tmp_path, capsys):
    """feilklasse=usikker med klasse=ikkeord skal avvises."""
    f = skriv_fasit(tmp_path, [("Tindå", "tindaa", "ikkeord", "usikker")])
    trans = tmp_path / "t.txt"; trans.write_text("tindaa\n", encoding="utf-8")
    rc = korriger.main([str(trans), "--ut-katalog", str(tmp_path), "--fasit", str(f)])
    assert rc != 0
    err = capsys.readouterr().err
    assert "INVARIANTBRUDD" in err and "tindaa" in err


def test_duplikat_med_motstrid_gir_ikke_null_exit(tmp_path, capsys):
    f = skriv_fasit(tmp_path, [
        ("Innovasjon Norge", "Norsk Norge", "kollisjon", "garble"),
        ("Investinor", "Norsk Norge", "kollisjon", "garble"),   # motstridende korrekt_form
    ])
    trans = tmp_path / "t.txt"; trans.write_text("Norsk Norge\n", encoding="utf-8")
    rc = korriger.main([str(trans), "--ut-katalog", str(tmp_path), "--fasit", str(f)])
    assert rc != 0
    assert "duplikat" in capsys.readouterr().err


def test_ukjent_klasse_gir_ikke_null_exit(tmp_path, capsys):
    f = skriv_fasit(tmp_path, [("Tindå", "Tinda", "kanskje", "garble")])
    trans = tmp_path / "t.txt"; trans.write_text("Tinda\n", encoding="utf-8")
    rc = korriger.main([str(trans), "--ut-katalog", str(tmp_path), "--fasit", str(f)])
    assert rc != 0
    assert "ukjent klasse" in capsys.readouterr().err


def test_duplikat_uten_motstrid_er_lovlig(tmp_path):
    """Samme feilform to ganger med identisk korrekt_form og klasse er ikke feil."""
    f = skriv_fasit(tmp_path, [
        ("Tindå", "Tinda", "ikkeord", "garble"),
        ("Tindå", "Tinda", "ikkeord", "garble"),
    ])
    rader = korriger.les_fasit([f])
    assert len(rader) == 1


# --------------------------------------------------------- ekte fasit + utdata
def test_ekte_fasit_passerer_validering():
    rader = korriger.les_fasit([OFFENTLIG])
    assert len(rader) == 13
    for r in rader:
        if r["feilklasse"] == "usikker":
            assert r["klasse"] == "kollisjon", f"invariantbrudd i {r}"


def test_utdata_havner_i_ut_katalog_ikke_ved_siden_av(tmp_path):
    f = skriv_fasit(tmp_path, [("Forskningsrådet", "Horskningsrådet", "ikkeord", "garble")])
    inn = tmp_path / "inn"; inn.mkdir()
    trans = inn / "opptak.txt"; trans.write_text("Horskningsrådet ringte.\n", encoding="utf-8")
    ut = tmp_path / "ut"
    rc = korriger.main([str(trans), "--ut-katalog", str(ut), "--fasit", str(f)])
    assert rc == 0
    assert (ut / "opptak.korrigert.txt").exists()
    assert (ut / "opptak.verbatim.txt").read_text(encoding="utf-8") == "Horskningsrådet ringte.\n"
    assert (ut / "opptak.substitusjonslogg.tsv").exists()
    assert not list(inn.glob("*.korrigert.txt"))   # ingenting ved siden av inndata


# ---------------------------------------------------------------------------
# Matrisen klasse x feilklasse.
#
# `kollisjon + garble` er cellen der de to kolonnene peker motsatt vei.
#
# Disse testene sier det eksplisitt, celle for celle. En regresjon som bytter
# r["klasse"] mot r["feilklasse"] i handlingsgrenen skal nå felle suiten.
# ---------------------------------------------------------------------------

MATRISE = [
    # (klasse, feilklasse, forventet handling)
    ("ikkeord",   "garble",       "substituert"),
    ("ikkeord",   "lyd-tvetydig", "substituert"),
    ("kollisjon", "garble",       "flagget"),      # <- cellen som manglet assert
    ("kollisjon", "lyd-tvetydig", "flagget"),
    ("kollisjon", "usikker",      "flagget"),
]


@pytest.mark.parametrize("klasse,feilklasse,forventet", MATRISE)
def test_handling_folger_klasse_ikke_feilklasse(klasse, feilklasse, forventet):
    """Handlingen skal bestemmes av `klasse` alene, uansett hva `feilklasse` sier."""
    rader = [{"korrekt_form": "Målform", "feilform": "Kildeform",
              "klasse": klasse, "feilklasse": feilklasse, "kilde": "test:1"}]
    ut, h, tall = kjor("Han nevnte Kildeform i møtet.", rader)
    assert len(h) == 1
    assert h[0]["handling"] == forventet, (
        f"{klasse}+{feilklasse} ga {h[0]['handling']}, forventet {forventet}")
    if forventet == "substituert":
        assert "Målform" in ut and "Kildeform" not in ut
        assert "⟦" not in ut
        assert tall["substituert"] == 1 and tall["flagget"] == 0
    else:
        assert "⟦Kildeform → Målform?⟧" in ut
        assert tall["flagget"] == 1 and tall["substituert"] == 0


def test_kollisjon_garble_substitueres_aldri_stille():
    """Raden fra den offentlige fasiten: Nasjonalbanken er kollisjon+garble.

    garble sier «lyden bar formen, dekodingen bommet» — men Nasjonalbanken er
    selv et navn, og klassen er derfor kollisjon. Feilklassen skal ikke kunne
    overstyre det til en stille substitusjon.
    """
    rader = [{"korrekt_form": "Innovasjon Norge", "feilform": "Nasjonalbanken",
              "klasse": "kollisjon", "feilklasse": "garble", "kilde": "test:1"}]
    ut, h, tall = kjor("Han sa Nasjonalbanken, men mente noe annet.", rader)
    assert "⟦Nasjonalbanken → Innovasjon Norge?⟧" in ut
    assert tall["substituert"] == 0
    assert h[0]["handling"] == "flagget"


def test_hele_ekte_fasit_flagger_hver_kollisjonsrad():
    """Ingen rad med klasse=kollisjon i den ekte tabellen får substitueres."""
    rader = korriger.les_fasit([OFFENTLIG])
    kollisjoner = [r for r in rader if r["klasse"] == "kollisjon"]
    assert kollisjoner, "fasiten har ingen kollisjonsrader — testen måler ikke det den skal"
    for r in kollisjoner:
        ut, h, tall = kjor(f"Setning med {r['feilform']} midt i.", [r])
        assert tall["substituert"] == 0, f"{r['feilform']} ({r['feilklasse']}) ble substituert"
        assert h[0]["handling"] == "flagget"
