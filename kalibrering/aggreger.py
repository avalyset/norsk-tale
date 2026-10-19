#!/usr/bin/env python3
"""norsk-tale — tallene fra kalibreringen: én runde lokalt, eller mange bidrag.

Et bidrag inneholder KUN tall og etiketter: per celle antall setninger, ordfeil og
referanseord, tegnfeil og referansetegn (så WER/CER kan slås sammen over talere),
feiltelling per klasse, antall talere, region (og eventuelt målepunkt), dialektkilde,
målform og modell/versjon. Ingen lyd og ingen tekst fra opptakene.

Celle:     klasse × målform i manus × målform whisper fikk × vokabular × tekst
Rader:     dialektregion, og målepunkt der det finnes
Kolonner:  dialektkilde — morsmål og imitert slås aldri sammen
Celler med færre enn 3 talere rulles opp til region før eksport (målepunkt fjernes)
og merkes «for få» i oppsummeringen.

CLI:  aggreger.py BIDRAG.json ... [--vokabular med|uten] [--tekst korrigert|ra] [--json]
"""
import argparse
import hashlib
import json
import pathlib
import sys

HER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HER))
import norm  # noqa: E402

MIN_TALERE = 3
KILDER = ("morsmål", "imitert", "ikke oppgitt")
FEILTYPER = ("nektelse", "tall", "navn", "første ord")


# ----------------------------------------------------------- én runde → tall
def celler_for_runde(resultater, fasit):
    """Fra rigg-resultater (med tekst, lokalt) til tallceller (uten tekst)."""
    celler = {}
    for rad in resultater["rader"]:
        s = fasit.get(rad["manus_id"])
        if s is None:
            continue
        for nokkel, v in rad["varianter"].items():
            mf_valgt, vok = nokkel.split("/")
            for tekst in ("korrigert", "ra"):
                if tekst not in v:
                    continue
                c = celler.setdefault((s["klasse"], s["malform"], mf_valgt, vok, tekst), tom_celle())
                legg_til(c, s["setning"], v[tekst]["utdata"], v[tekst]["scoring"])
    ut = []
    for (klasse, mf, mf_valgt, vok, tekst), c in sorted(celler.items()):
        ut.append({"klasse": klasse, "malform": mf, "malform_valgt": mf_valgt, "vokabular": vok,
                   "tekst": tekst, **c})
    return ut


def tom_celle():
    return {"n_setninger": 0, "ord_feil": 0, "ord_ref": 0, "tegn_feil": 0, "tegn_ref": 0,
            "feil": {t: {"bom": 0, "av": 0} for t in FEILTYPER} | {"målform": 0}}


def legg_til(c, fasit_tekst, utdata, scoring):
    c["n_setninger"] += 1
    f, n = norm.ordfeil(fasit_tekst, utdata)
    c["ord_feil"] += f
    c["ord_ref"] += n
    f, n = norm.tegnfeil(fasit_tekst, utdata)
    c["tegn_feil"] += f
    c["tegn_ref"] += n
    for el in scoring["elementer"]:
        if el["type"] in c["feil"]:
            c["feil"][el["type"]]["av"] += 1
            c["feil"][el["type"]]["bom"] += 0 if el["treff"] else 1
    c["feil"]["første ord"]["av"] += 1
    c["feil"]["første ord"]["bom"] += 0 if scoring["forste_innholdsord"]["treff"] else 1
    c["feil"]["målform"] += 1 if scoring["malform"]["funn"] else 0


def lag_bidrag(celler, modell, region, kilde, malform, malepunkt=None, n_talere=1, manus="manus_v1"):
    """Det eneste som kan deles. Rulles opp før det vises."""
    return rull_opp({"norsk_tale_bidrag": 2, "manus": manus, "modell": modell,
                     "dialektregion": region, "dialektkilde": kilde if region else None,
                     "malepunkt": malepunkt, "malform": malform, "n_talere": n_talere,
                     "celler": celler})


def rull_opp(bidrag, min_talere=MIN_TALERE):
    """Under `min_talere` talere: målepunktet fjernes, bare regionen står igjen."""
    if bidrag.get("malepunkt") and bidrag.get("n_talere", 0) < min_talere:
        bidrag = {**bidrag, "malepunkt": None, "rullet_opp": "region"}
    return bidrag


# ------------------------------------------------------- mange bidrag → rader
def aggreger(bidrag, vokabular="med", tekst="korrigert", min_talere=MIN_TALERE):
    """bidrag: liste av (taler-id, bidrag). Returnerer rader per celle og sted,
    med én kolonne per dialektkilde. Målepunkt-rader under `min_talere` talere
    vises ikke; de inngår i regionsraden."""
    tabell = {}
    for taler, b in bidrag:
        region = b.get("dialektregion") or "ikke oppgitt"
        kilde = b.get("dialektkilde") if b.get("dialektkilde") in KILDER else "ikke oppgitt"
        steder = [(region, None)]
        if b.get("malepunkt"):
            steder.append((region, b["malepunkt"]))
        for c in b.get("celler", []):
            if c["vokabular"] != vokabular or c["tekst"] != tekst:
                continue
            for region_, punkt in steder:
                nokkel = (c["klasse"], c["malform"], c["malform_valgt"], region_, punkt or "")
                sum_ = tabell.setdefault(nokkel, {}).setdefault(kilde, {"talere": set(), **tom_celle()})
                sum_["talere"].add(taler)
                for k in ("n_setninger", "ord_feil", "ord_ref", "tegn_feil", "tegn_ref"):
                    sum_[k] += c[k]
                for t in FEILTYPER:
                    sum_["feil"][t]["bom"] += c["feil"][t]["bom"]
                    sum_["feil"][t]["av"] += c["feil"][t]["av"]
                sum_["feil"]["målform"] += c["feil"]["målform"]
    ut = []
    for (klasse, mf, mf_valgt, region, punkt), kilder in sorted(tabell.items()):
        kol = {}
        for kilde, s in kilder.items():
            t = len(s["talere"])
            if punkt and t < min_talere:
                continue          # rullet opp: telles bare i regionsraden
            kol[kilde] = {"talere": t, "for_faa": t < min_talere, "n_setninger": s["n_setninger"],
                          "wer": round(s["ord_feil"] / s["ord_ref"], 4) if s["ord_ref"] else None,
                          "cer": round(s["tegn_feil"] / s["tegn_ref"], 4) if s["tegn_ref"] else None,
                          "feil": s["feil"]}
        if kol:
            ut.append({"klasse": klasse, "malform": mf, "malform_valgt": mf_valgt,
                       "dialektregion": region, "malepunkt": punkt or None, "kilder": kol})
    return ut


def taler_id(innhold):
    """Ett bidrag = én runde. Samme fil to ganger telles én gang."""
    return hashlib.sha256(json.dumps(innhold, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def tekst_tabell(rader):
    linjer = []
    for r in rader:
        sted = r["dialektregion"] + (f"/{r['malepunkt']}" if r["malepunkt"] else "")
        hode = f"{r['klasse']:<10} {r['malform']}→whisper {r['malform_valgt']:<3} {sted:<20}"
        deler = []
        for kilde in KILDER:
            c = r["kilder"].get(kilde)
            if not c:
                continue
            f = c["feil"]
            deler.append(f"{kilde}: {c['talere']} talere{' (for få)' if c['for_faa'] else ''}, "
                         f"n={c['n_setninger']}, WER {c['wer']}, CER {c['cer']}, "
                         f"nekt {f['nektelse']['bom']}/{f['nektelse']['av']}, tall {f['tall']['bom']}/{f['tall']['av']}, "
                         f"navn {f['navn']['bom']}/{f['navn']['av']}, målform {f['målform']}")
        linjer.append(hode + " | " + " | ".join(deler))
    return "\n".join(linjer)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Slår sammen tallbidrag fra kalibreringsriggen.")
    ap.add_argument("bidrag", nargs="+", type=pathlib.Path)
    ap.add_argument("--vokabular", choices=("med", "uten"), default="med")
    ap.add_argument("--tekst", choices=("korrigert", "ra"), default="korrigert")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    bidrag = []
    for sti in a.bidrag:
        innhold = json.loads(sti.read_text(encoding="utf-8"))
        bidrag.append((taler_id(innhold), innhold))
    rader = aggreger(bidrag, a.vokabular, a.tekst)
    print(json.dumps(rader, ensure_ascii=False, indent=2) if a.json else tekst_tabell(rader))
    return 0


if __name__ == "__main__":
    sys.exit(main())
