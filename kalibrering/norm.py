"""norsk-tale — WER/CER-normalisering etter NB-Whisper-prosjektet.

Kilde: NbAiLab/nostram, utils/evaluate.py, funksjonen `normalizer` (Apache-2.0),
commit 448238e9c8d87c7ce1a9d1db24612bed31b6f320 (04.02.2024), med
extra_clean=False og super_normalize=False (standardverdiene):

    jiwer.Compose([ToLowerCase(), RemoveMultipleSpaces(), Strip(),
                   RemovePunctuation(), RemoveWhiteSpace(replace_by_space=True)])

og deretter `jiwer.wer` med jiwers standard ordtransform (RemoveMultipleSpaces,
Strip, del på mellomrom). nostram beregner ikke CER; CER her følger `jiwer.cer`s
standard (Strip, tegn for tegn, mellomrom teller) på den samme normaliserte teksten.

NB-Whispers eget eval.py (NbAiLab/nb-whisper) har ingen normalisering; det er en
innpakning rundt treningsskriptet, som bruker OpenAIs BasicTextNormalizer.
arXiv 2402.01917 beskriver «JiWER, små bokstaver, tegnsetting fjernet», som
passer med nostram-varianten. At akkurat denne fila ga tallene i papiret, er
sannsynlig, ikke dokumentert.

Dette er en ren standardbibliotek-port av transformene (tegnsetting = Unicode-
kategori P, fjernes uten mellomrom). Kryssjekket 19.10.2026 mot jiwer 4.0.0 med
kalibrering/kryssjekk_jiwer.py: 0 normaliseringsavvik på 244 tekster, identisk
WER og CER på 120 par.
"""
import re
import sys
import unicodedata

_TEGNSETTING = "".join(chr(i) for i in range(sys.maxunicode + 1)
                       if unicodedata.category(chr(i)).startswith("P"))
_TEGNSETTING_RE = re.compile("[" + re.escape(_TEGNSETTING) + "]")


def normaliser(tekst):
    """nostram `normalizer(text)` med standardvalg, som jiwer.Compose-kjeden over."""
    t = tekst.lower()                      # ToLowerCase
    t = re.sub(r"\s\s+", " ", t)           # RemoveMultipleSpaces
    t = t.strip()                          # Strip
    t = _TEGNSETTING_RE.sub("", t)         # RemovePunctuation (jiwer 3.x)
    t = re.sub(r"\s", " ", t)              # RemoveWhiteSpace(replace_by_space=True)
    return t


def _ord(normalisert):
    """jiwer.wer sin standardtransform: RemoveMultipleSpaces, Strip, del på mellomrom."""
    t = re.sub(r"\s\s+", " ", normalisert).strip()
    return t.split(" ") if t else []


def _tegn(normalisert):
    """jiwer.cer sin standardtransform: Strip, deretter tegn for tegn."""
    return list(normalisert.strip())


def _levenshtein(a, b):
    forrige = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        naa = [i]
        for j, y in enumerate(b, 1):
            naa.append(min(forrige[j] + 1, naa[j - 1] + 1, forrige[j - 1] + (x != y)))
        forrige = naa
    return forrige[-1]


def ordfeil(referanse, hypotese):
    """(S+D+I, N) på ordnivå etter normalisering. WER over et sett = sum/sum."""
    r, h = _ord(normaliser(referanse)), _ord(normaliser(hypotese))
    return _levenshtein(r, h), len(r)


def tegnfeil(referanse, hypotese):
    r, h = _tegn(normaliser(referanse)), _tegn(normaliser(hypotese))
    return _levenshtein(r, h), len(r)


def wer(referanser, hypoteser):
    feil = n = 0
    for r, h in zip(referanser, hypoteser):
        f, k = ordfeil(r, h)
        feil, n = feil + f, n + k
    return feil / n if n else 0.0


def cer(referanser, hypoteser):
    feil = n = 0
    for r, h in zip(referanser, hypoteser):
        f, k = tegnfeil(r, h)
        feil, n = feil + f, n + k
    return feil / n if n else 0.0
