"""norm.py: NB-Whisper-prosjektets WER/CER-normalisering (nostram utils/evaluate.py),
portert til standardbiblioteket. Forventningene er utledet av jiwer 3.x-transformene
slik de er beskrevet i norm.py; en kryssjekk mot ekte jiwer står igjen."""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "kalibrering"))
import norm  # noqa: E402


def test_smaa_bokstaver_og_tegnsetting_fjernes_uten_mellomrom():
    assert norm.normaliser("  Nord-Norge, Skatteetaten!  ") == "nordnorge skatteetaten"
    assert norm.normaliser("«Hei» – sa hun.") == "hei  sa hun"   # tankestrek fjernet, mellomrom står


def test_tall_normaliseres_ikke():
    assert norm.normaliser("3 450 kr") == "3 450 kr"
    assert norm.normaliser("3.450 kr") == "3450 kr"            # punktum er tegnsetting
    assert norm.ordfeil("tre tusen", "3000") == (2, 2)


def test_ordfeil_er_levenshtein_paa_ord():
    assert norm.ordfeil("Jeg har ikke betalt.", "jeg har betalt") == (1, 4)
    assert norm.ordfeil("a b c d", "a x c d") == (1, 4)
    assert norm.ordfeil("a b", "a b c") == (1, 2)


def test_wer_over_sett_er_sum_over_sum():
    assert norm.wer(["a b", "c d e f"], ["a x", "c d e f"]) == 1 / 6


def test_cer_teller_mellomrom_som_tegn():
    assert norm.tegnfeil("ab cd", "abcd") == (1, 5)
    assert norm.cer(["abcd"], ["abce"]) == 0.25


def test_tom_referanse():
    assert norm.ordfeil("", "") == (0, 0)
    assert norm.wer([""], [""]) == 0.0
