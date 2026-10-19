#!/usr/bin/env python3
"""norsk-tale — fase 1 av prereg-v1 (AVVIK.md nr. 1).

Kjører og scorer en delmatrise med de frosne funksjonene i reproduser.py.
reproduser.py, manifest.json og METHOD.md er uendret, og hele manifestet
verifiseres før hver kjøring.

  Fase 1 = FLEURS × {medium, large} × nb × prompt {på, av}
         + NB Tale × large × nb × prompt på

  estimat  gjenstående kjøringer × målte medianer for veggklokke (bare tid)
  kjor     fase-1-cellene, i de samme resultatfilene som hele matrisen, så
           ferdige kjøringer gjenbrukes og fase 2 kan fortsette der fase 1
           slapp; stopper rolig med kode 7 når Ollama er opptatt
  scor     reproduser.scor på hver delmatrise; komplette tilfeller vurderes
           innen fase-1-cellene. Skriver rapport-fase1.json (bare tall)

Fase 2 (resten av matrisen) kjøres bare med `reproduser.py kjor` etter en
uttrykkelig beslutning.
"""
import argparse
import copy
import json
import pathlib
import statistics
import sys

HER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HER))
import reproduser  # noqa: E402

FASE1 = [
    {"sett": "fleurs", "modeller": ["medium", "large"], "malformer": ["nb"], "prompt": ["pa", "av"]},
    {"sett": "nb_tale", "modeller": ["large"], "malformer": ["nb"], "prompt": ["pa"]},
]


def delmanifest(m, d):
    m2 = copy.deepcopy(m)
    m2["modellrekkefolge"] = list(d["modeller"])
    m2["sett"] = {d["sett"]: {**m["sett"][d["sett"]], "malformer": list(d["malformer"]), "prompt": list(d["prompt"])}}
    return m2


def estimat(m, arbeid, reserve=None):
    """Gjenstående fase-1-kjøringer per modell og målt median veggklokke.
    Leser bare id, målform, prompt, status og vegg_s fra resultatfilene."""
    ferdig, tider = set(), {}
    for d in FASE1:
        for mv in d["modeller"]:
            fil = reproduser.resultatfil(arbeid, d["sett"], mv)
            if fil.exists():
                for ln in fil.read_text(encoding="utf-8").splitlines():
                    x = json.loads(ln)
                    ferdig.add((d["sett"], mv, x["id"], x["malform"], x["prompt"]))
                    if x.get("status") == "ok":
                        tider.setdefault(mv, []).append(x["vegg_s"])
    ut = {"per_modell": {}, "kilde_median": {}}
    for d in FASE1:
        ider = reproduser.les_idliste(reproduser.ROT / m["sett"][d["sett"]]["idliste"])
        for mv in d["modeller"]:
            igjen = sum((d["sett"], mv, i, mf, p) not in ferdig
                        for i in ider for mf in d["malformer"] for p in d["prompt"])
            ut["per_modell"].setdefault(mv, 0)
            ut["per_modell"][mv] += igjen
    total = 0.0
    for mv, n in ut["per_modell"].items():
        if tider.get(mv):
            med, kilde = statistics.median(tider[mv]), f"median av {len(tider[mv])} kjøringer i denne kalibreringen"
        else:
            med, kilde = (reserve or {}).get(mv), "median fra tidsproben (Metal, 6 ytringer)"
        ut["kilde_median"][mv] = {"median_s": med, "kilde": kilde}
        total += n * (med or 0)
    ut["timer"] = round(total / 3600, 2)
    return ut


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("steg", choices=["estimat", "kjor", "scor"])
    ap.add_argument("--reserve-median", default="", help="JSON {modell: sekunder} for modeller uten egne kjøringer")
    a = ap.parse_args(argv)
    m = reproduser.les_manifest()
    arbeid = reproduser.sti_fra_miljo("NORSK_TALE_ARBEID") / m["versjon"]
    if a.steg == "estimat":
        print(json.dumps(estimat(m, arbeid, json.loads(a.reserve_median or "{}")), ensure_ascii=False, indent=1))
        return 0
    if a.steg == "kjor":
        reproduser.verifiser(m)
        reproduser.utvalg(m, sjekk=True)
        arbeid.mkdir(parents=True, exist_ok=True)
        for d in FASE1:
            kode = reproduser.kjor(delmanifest(m, d))
            if kode:
                return kode
        print("fase 1 ferdig", flush=True)
        return 0
    if a.steg == "scor":
        reproduser.verifiser(m, data=False)
        rapport = {"versjon": m["versjon"], "fase": 1, "avvik": "AVVIK.md nr. 1", "delmatriser": FASE1, "sett": {}}
        for d in FASE1:
            rapport["sett"].update(reproduser.scor(delmanifest(m, d), arbeid)["sett"])
        ut = arbeid / "rapport-fase1.json"
        ut.write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"rapport: {ut}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
