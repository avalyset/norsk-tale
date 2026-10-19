#!/usr/bin/env python3
"""norsk-tale — deterministisk scoring av én transkribert setning mot fasit.

Ingen LLM, ingen nettverk, bare standardbiblioteket. Brukes av /norsk selvtest
og av kalibreringsriggen.

Fasit per setning: id, målform (nb/nn), setning og målelementer:
  {"type": "nektelse"|"tall"|"navn", "former": [akseptable skriveformer]}

  tall      formene skrives som sifre ("3450", "14"); utdata normaliseres først:
            tallord blir sifre ("tre tusen fire hundre og femti" → 3450,
            "tjuetjuefem" → 2025, "fjortende" → 14), tusenskille og mellomrom i
            sifergrupper fjernes ("3 450", "3.450" → 3450), "14." → 14
  nektelse  treff bare når en av formene står som eget ord. En tapt nektelse er
            alltid bom — det finnes ingen nærhetsregel som kan redde den
  navn      ordsekvensen må stå i utdata (store/små bokstaver likegyldig)

Målform rapporteres separat og feller aldri setningen.

CLI:  score.py --setninger FIL --id N   (utdata på stdin, JSON på stdout)
"""
import argparse
import csv
import json
import re
import sys
import unicodedata

# ------------------------------------------------------------------ tallord
ENER = {"null": 0, "en": 1, "ett": 1, "én": 1, "ein": 1, "eitt": 1, "ei": 1,
        "to": 2, "tre": 3, "fire": 4, "fem": 5, "seks": 6, "sju": 7, "syv": 7,
        "åtte": 8, "ni": 9, "ti": 10, "elleve": 11, "tolv": 12, "tretten": 13,
        "fjorten": 14, "femten": 15, "seksten": 16, "sytten": 17, "atten": 18,
        "nitten": 19}
TIERE = {"tjue": 20, "tjuge": 20, "tretti": 30, "førti": 40, "femti": 50,
         "seksti": 60, "sytti": 70, "søtti": 70, "åtti": 80, "nitti": 90}
GANGER = {"hundre": 100, "tusen": 1000}
ORDENS = {"tredje": 3, "fjerde": 4, "femte": 5, "sjette": 6, "sjuende": 7,
          "syvende": 7, "åttende": 8, "niende": 9, "tiende": 10, "ellevte": 11,
          "tolvte": 12, "trettende": 13, "fjortende": 14, "femtende": 15,
          "sekstende": 16, "syttende": 17, "attende": 18, "nittende": 19,
          "tjuende": 20, "tjugande": 20, "trettiende": 30,
          # nynorsk
          "sjuande": 7, "åttande": 8, "niande": 9, "tiande": 10, "trettande": 13,
          "fjortande": 14, "femtande": 15, "sekstande": 16, "syttande": 17,
          "attande": 18, "nittande": 19, "tjuande": 20, "trettiande": 30}
# Ord som også er vanlige ikke-tall, og som derfor bare telles inne i et
# lengre tallord: «en», «ei», «ett» (artikler), «første», «andre».
TVETYDIGE = {"en", "ett", "ein", "eitt", "ei", "ni", "to"}

_MORFEMER = sorted([*ENER, *TIERE, *GANGER, "og"], key=len, reverse=True)


def _splitt(ord_):
    """Deler et sammensatt tallord i morfemer, eller None hvis det ikke går.
    «tjuetjuefem» → [tjue, tjue, fem]; «femogtjue» → [fem, og, tjue]."""
    if ord_ in ORDENS:
        return [ord_]
    for tier, v in TIERE.items():           # «tjueførste» osv.
        for ordens, w in [("første", 1), ("andre", 2), *ORDENS.items()]:
            if ord_ == tier + ordens and w < 10:
                return [tier, ordens]
    ut, i = [], 0
    while i < len(ord_):
        for m in _MORFEMER:
            if ord_.startswith(m, i):
                ut.append(m)
                i += len(m)
                break
        else:
            return None
    return ut if ut and ut != ["og"] else None


def _verdi(morfemer):
    """Morfemliste → liste med tall. Årstallsformen «tjue tjuefem» gir [2025];
    to frittstående tall («tre fire») gir [3, 4], ikke 7."""
    if len(morfemer) == 1 and morfemer[0] in ORDENS:
        return [ORDENS[morfemer[0]]]
    if len(morfemer) == 2 and morfemer[0] in TIERE and morfemer[1] in ("første", "andre", *ORDENS):
        return [TIERE[morfemer[0]] + {"første": 1, "andre": 2}.get(morfemer[1], ORDENS.get(morfemer[1], 0))]
    # slå sammen tier + ener (tjuefem) og ener + og + tier (femogtjue) til grupper
    grupper, i, m = [], 0, [x for x in morfemer]
    while i < len(m):
        x = m[i]
        if x in TIERE and i + 1 < len(m) and m[i + 1] in ENER and ENER[m[i + 1]] < 10:
            grupper.append(TIERE[x] + ENER[m[i + 1]]); i += 2
        elif (x in ENER and ENER[x] < 10 and i + 2 < len(m) and m[i + 1] == "og"
              and m[i + 2] in TIERE):
            grupper.append(ENER[x] + TIERE[m[i + 2]]); i += 3
        elif x in ENER:
            grupper.append(ENER[x]); i += 1
        elif x in TIERE:
            grupper.append(TIERE[x]); i += 1
        elif x in GANGER:
            grupper.append(x); i += 1
        else:                                   # «og»
            i += 1
    if not any(isinstance(g, str) for g in grupper) and len(grupper) == 2 \
            and 11 <= grupper[0] <= 99 and grupper[1] < 100:
        return [grupper[0] * 100 + grupper[1]]  # årstall: nitten nittifem, tjue tjuefem
    tall, total, naa, forrige_plain = [], 0, 0, False
    for g in grupper:
        if g == "hundre":
            naa = (naa or 1) * 100
            forrige_plain = False
        elif g == "tusen":
            total += (naa or 1) * 1000
            naa = 0
            forrige_plain = False
        else:
            if forrige_plain:                    # to tall etter hverandre: nytt tall
                tall.append(total + naa)
                total, naa = 0, 0
            naa += g
            forrige_plain = True
    tall.append(total + naa)
    return tall


def _tallord(tok):
    return tok in ENER or tok in TIERE or tok in GANGER or tok in ORDENS or (
        _splitt(tok) is not None and len(tok) > 3)


def tall_til_sifre(tokens):
    """Erstatter sammenhengende tallord med sifre. Et tvetydig ord alene
    («en», «to», «ni») røres ikke, så artikler og verb ikke blir tall."""
    ut, i = [], 0
    while i < len(tokens):
        j, morf = i, []
        while j < len(tokens):
            t = tokens[j]
            if t == "og" and morf and j + 1 < len(tokens) and _tallord(tokens[j + 1]):
                neste = _splitt(tokens[j + 1]) or []
                etter_ganger = morf[-1] in GANGER
                ener_og_tier = (morf[-1] in ENER and ENER[morf[-1]] < 10
                                and neste[:1] and neste[0] in TIERE)
                if etter_ganger or ener_og_tier:
                    morf.append("og"); j += 1; continue
                break
            s = _splitt(t) if _tallord(t) else None
            if s is None:
                break
            morf.extend(s); j += 1
        if morf and not (j - i == 1 and tokens[i] in TVETYDIGE):
            ut.extend(str(v) for v in _verdi(morf))
            i = j
        else:
            ut.append(tokens[i]); i += 1
    return ut


# ------------------------------------------------------------- normalisering
def normaliser(tekst):
    """Små bokstaver, NFC, sifergrupper samlet, «%» → prosent, tegnsetting bort,
    tallord → sifre. Returnerer en liste med ord."""
    t = unicodedata.normalize("NFC", tekst).lower().replace(" ", " ").replace(" ", " ")
    t = re.sub(r"(?<!\d)(\d{1,3})(?:[ .](\d{3}))+(?!\d)",
               lambda m: re.sub(r"[ .]", "", m.group(0)), t)
    t = re.sub(r"(\d)\s*%", r"\1 prosent", t)
    t = re.sub(r"(\d+)\.(?=\s|$)", r"\1", t)          # ordenstall «14.»
    t = re.sub(r"[^\w\s]", " ", t)
    return tall_til_sifre(t.split())


def _inneholder(ord_, sekvens):
    n = len(sekvens)
    return any(ord_[i:i + n] == sekvens for i in range(len(ord_) - n + 1)) if n else False


# ---------------------------------------------------------------- målform
# Former som bare finnes i den ene målformen. Telles på råordene, før tallord
# blir sifre, så «femtande» og «femtende» fortsatt skiller.
NN = {"eg", "ikkje", "frå", "dei", "kva", "korleis", "berre", "ho", "ein", "eit",
      "kvifor", "noko", "nokon", "mykje", "korkje", "hjå", "heile", "meir", "vart",
      "kjem", "gjeld", "treng", "enno", "innan", "steig", "bad", "gav", "fekk",
      "måndag", "kostar", "krev", "ønskjer", "vore", "lese", "sendast", "betalast",
      "opna", "handsama", "godkjende", "kommunane", "skjemaa", "tala", "rundar",
      "tilskot", "rekninga", "framlegget", "førespurnadene", "millionar",
      "sjuande", "åttande", "niande", "tiande", "trettande", "fjortande",
      "femtande", "sekstande", "syttande", "attande", "nittande", "tjuande"}
NB = {"jeg", "ikke", "fra", "de", "hva", "hvordan", "bare", "hun", "et", "hvorfor",
      "noe", "noen", "mye", "verken", "hos", "hele", "mer", "ble", "kommer",
      "gjelder", "trenger", "ennå", "innen", "steg", "ba", "ga", "fikk", "mandag",
      "koster", "krever", "ønsker", "vært", "lest", "sendes", "betales", "åpnet",
      "behandlet", "godkjente", "kommunene", "skjemaene", "tallene", "runder",
      "tilskudd", "regningen", "forslaget", "henvendelsene", "millioner",
      "sjuende", "syvende", "åttende", "niende", "tiende", "trettende", "fjortende",
      "femtende", "sekstende", "syttende", "attende", "nittende", "tjuende"}


def raaord(tekst):
    t = unicodedata.normalize("NFC", tekst).lower()
    return re.sub(r"[^\w\s]", " ", t).split()


def malform(ord_):
    nn = sum(o in NN for o in ord_)
    nb = sum(o in NB for o in ord_)
    return "nn" if nn > nb else "nb" if nb > nn else "uklar"


# ------------------------------------------------------- første innholdsord
STOPP = {"jeg", "eg", "vi", "me", "du", "de", "dei", "det", "den", "har", "hadde", "er",
         "var", "og", "i", "på", "av", "til", "fra", "frå", "om", "en", "ei", "et", "ein",
         "eit", "ikke", "ikkje", "aldri", "ingen", "nei", "verken", "eller", "som", "at"}


def forste_innholdsord(setning):
    for o in normaliser(setning):
        if o not in STOPP and not o.isdigit():
            return o
    return None


# ---------------------------------------------------------------- WER/CER
def _lev(a, b):
    forrige = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        naa = [i]
        for j, y in enumerate(b, 1):
            naa.append(min(forrige[j] + 1, naa[j - 1] + 1, forrige[j - 1] + (x != y)))
        forrige = naa
    return forrige[-1]


def wer(fasit, utdata):
    f, u = normaliser(fasit), normaliser(utdata)
    return round(_lev(f, u) / max(1, len(f)), 4)


def cer(fasit, utdata):
    f, u = " ".join(normaliser(fasit)), " ".join(normaliser(utdata))
    return round(_lev(f, u) / max(1, len(f)), 4)


# ------------------------------------------------------------------ scoring
def score_setning(fasit, utdata):
    ord_ = normaliser(utdata)
    elementer, bom = [], []
    for el in fasit["elementer"]:
        treff = None
        for form in el["former"]:
            if _inneholder(ord_, normaliser(form)):
                treff = form
                break
        elementer.append({"type": el["type"], "former": el["former"], "treff": treff is not None,
                          "funnet": treff})
        if treff is None:
            bom.append({"type": el["type"], "fasit": el["former"][0], "utdata": utdata})
    forste = forste_innholdsord(fasit["setning"])
    forste_ok = forste is None or forste in ord_
    if not forste_ok:
        bom.append({"type": "første ord", "fasit": forste, "utdata": utdata})
    mf = malform(raaord(utdata))
    return {
        "id": fasit["id"],
        "setning": fasit["setning"],
        "utdata": utdata,
        "elementer": elementer,
        "forste_innholdsord": {"ord": forste, "treff": forste_ok},
        # «uklar» (ingen markører i utdata) er ikke et funn; motsatt målform er det.
        "malform": {"forventet": fasit["malform"], "utdata": mf,
                    "funn": mf not in (fasit["malform"], "uklar")},
        "bom": bom,
        "bestatt": not bom,
        "wer": wer(fasit["setning"], utdata),
        "cer": cer(fasit["setning"], utdata),
    }


def les_setninger(sti):
    """TSV med kolonnene id, malform, klasse, setning, elementer (JSON) og
    eventuelt dialektutvalg (ja/nei)."""
    ut = []
    with open(sti, encoding="utf-8", newline="") as fh:
        for rad in csv.DictReader((ln for ln in fh if not ln.startswith("#")), delimiter="\t"):
            ut.append({"id": rad["id"], "malform": rad["malform"], "klasse": rad.get("klasse", ""),
                       "setning": rad["setning"], "elementer": json.loads(rad["elementer"]),
                       "dialektutvalg": (rad.get("dialektutvalg") or "nei").strip() == "ja"})
    return ut


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scorer én transkribert setning mot fasit.")
    ap.add_argument("--setninger", required=True)
    ap.add_argument("--id", required=True)
    a = ap.parse_args(argv)
    fasit = next((s for s in les_setninger(a.setninger) if s["id"] == a.id), None)
    if fasit is None:
        print(f"Ukjent setnings-id: {a.id}", file=sys.stderr)
        return 2
    print(json.dumps(score_setning(fasit, sys.stdin.read().strip()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
