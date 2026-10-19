"""feilanalyse.py: tapte nektelser, med målformkryss. Håndlagde eksempler."""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "kalibrering"))
import feilanalyse as fa  # noqa: E402


def test_det_observerte_klippet_teller_en_tapt_nektelse():
    """Mønsteret fra 19.10: bokmål med nb mot samme tale med nn (forkortet)."""
    nb = "Det er ikke sikkert det det er mulig. Ikke si det, men ..."
    nn = "Det er sikkert det det er mogleg. Ikkje si det, men ..."
    t = fa.tapte_nektelser(nb, nn)
    assert t["referanse"] == 2 and t["utdata"] == 1 and t["tapt"] == 1 and t["lagt_til"] == 0


def test_malformbytte_er_ikke_tap():
    assert fa.tapte_nektelser("Han ville verken betale eller svare, ikke nei.",
                              "Han ville korkje betale eller svare, ikkje nei.")["tapt"] == 0
    assert fa.tapte_nektelser("Ingen kom.", "Inga kom.")["tapt"] == 0


def test_lagt_til_nektelse_telles_for_seg():
    t = fa.tapte_nektelser("Det stemmer.", "Det stemmer ikke.")
    assert t["tapt"] == 0 and t["lagt_til"] == 1


def test_ingen_nektelser():
    t = fa.tapte_nektelser("Skatteetaten svarte i går.", "Skatteetaten svarte i går.")
    assert t == {"referanse": 0, "utdata": 0, "tapt": 0, "lagt_til": 0, "per_type": {}}


def test_ord_som_inneholder_nektelse_teller_ikke():
    assert fa.nektelser("ingeniøren neida aldriges") == {}


def test_sum_over_sett():
    s = fa.sum_tapte([("ikke nei", "nei"), ("aldri", "aldri"), ("ingen", "")])
    assert s == {"referanse": 4, "tapt": 2, "lagt_til": 0, "andel_tapt": 0.5}
