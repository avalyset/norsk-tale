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
  gjenskap kjører n seedet tilfeldige fase-1-kjøringer på nytt med de samme
           frosne funksjonene, i en egen mappe, og sammenligner rå tekst byte
           for byte med det lagrede. Skriver bare id-er og SHA256-prefikser.

Gjenskape hele fase 1 fra ren checkout (tag v0.1.0), med data og modeller
på plass og SHA-er som i manifest.json:

  export NORSK_TALE_DATA=… NORSK_TALE_MODELLER=… NORSK_TALE_WHISPER_CLI=…
  export NORSK_TALE_ARBEID=<ny, tom mappe>
  python3 -I kalibrering/vakt.py --logg vakt.log -- python3 -I kalibrering/fase1.py kjor
  python3 -I kalibrering/fase1.py scor

Fase 2 (resten av matrisen) kjøres bare med `reproduser.py kjor` etter en
uttrykkelig beslutning.
"""
import argparse
import copy
import hashlib
import json
import os
import pathlib
import random
import statistics
import sys
import time

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


def gjenskap(m, arbeid, n=10, seed=None):
    """n seedet tilfeldige fase-1-kjøringer på nytt; rå tekst sammenlignes med den lagrede."""
    seed = m["seed"] if seed is None else seed
    poster = []
    for d in FASE1:
        ider = reproduser.les_idliste(reproduser.ROT / m["sett"][d["sett"]]["idliste"])
        for mv in d["modeller"]:
            for mf in d["malformer"]:
                for p in d["prompt"]:
                    poster += [(d["sett"], mv, mf, p, i) for i in ider]
    valgt = sorted(random.Random(f"{seed}/gjenskap").sample(sorted(poster), n))
    lagret = {}
    for s, mv in {(x[0], x[1]) for x in valgt}:
        for ln in reproduser.resultatfil(arbeid, s, mv).read_text(encoding="utf-8").splitlines():
            x = json.loads(ln)
            if x.get("status") == "ok":
                lagret[(s, mv, x["malform"], x["prompt"], x["id"])] = x["ra"]
    reproduser.kjerne.TIDSGRENSE_S = m["tidsgrense_s"]
    os.environ["NORSK_TALE_WHISPER_ARGS"] = m["whisper_cpp"]["ekstra_args"]
    ny_mappe = arbeid / "gjenskap" / time.strftime("%Y%m%dT%H%M%S")
    lyd, sha = {}, {}
    for s in sorted({x[0] for x in valgt}):
        lyd[s] = reproduser.sett.SETT[s][1](reproduser.sti_fra_miljo("NORSK_TALE_DATA"),
                                            sorted({x[4] for x in valgt if x[0] == s}), ny_mappe / "lyd" / s)
    h = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()
    rader = []
    for s, mv, mf, p, i in valgt:
        if mv not in sha:
            sha[mv] = reproduser.kjerne.verifiser_modell(
                reproduser.sti_fra_miljo("NORSK_TALE_MODELLER") / m["modeller"][mv]["fil"], m["modeller"][mv]["sha256"])
        r = reproduser.kjor_en(lyd[s][i], reproduser.oppsett_for(m, mv, mf, p), sha[mv], m["maks_gjentak"])
        gammel = lagret.get((s, mv, mf, p, i))
        rader.append({"sett": s, "modell": mv, "malform": mf, "prompt": p, "id": i, "status": r["status"],
                      "identisk": r.get("ra") is not None and r.get("ra") == gammel,
                      "sha256_lagret": h(gammel)[:16] if gammel is not None else None,
                      "sha256_ny": h(r["ra"])[:16] if r.get("ra") is not None else None})
    ut = {"seed": f"{seed}/gjenskap", "n": n, "identiske": sum(x["identisk"] for x in rader), "rader": rader}
    (arbeid / f"gjenskap-{ny_mappe.name}.json").write_text(json.dumps(ut, ensure_ascii=False, indent=1), encoding="utf-8")
    return ut


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("steg", choices=["estimat", "kjor", "scor", "gjenskap"])
    ap.add_argument("--n", type=int, default=10)
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
    if a.steg == "gjenskap":
        reproduser.verifiser(m)
        ut = gjenskap(m, arbeid, a.n)
        print(json.dumps(ut, ensure_ascii=False, indent=1))
        return 0 if ut["identiske"] == ut["n"] else 6
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
