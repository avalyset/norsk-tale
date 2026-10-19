#!/usr/bin/env python3
"""norsk-tale — standardkalibrering mot etablerte testsett (foreløpig NST-test).

  utvalg   seedet tilfeldig utvalg av ytringer; id-listen (bare id-er) skrives
           til kalibrering/utvalg/ i repoet
  lyd      bare de valgte filene pakkes ut fra datasettets tar-arkiv, til en
           arbeidsmappe på Vault (aldri i repoet)
  kjør     én whisper-cli-prosess per ytring og målform (deterministisk), med
           kjernens oppsett; resultater skrives fortløpende som JSONL på Vault
           og kjøringen kan gjenopptas
  oppsummer WER/CER (norm.py, NB-Whisper-prosjektets normalisering) for rå og
           korrigert utdata, per målform whisper fikk; tapte og tillagte
           nektelser (feilanalyse.py). Oppsummeringen inneholder ingen tekst
           fra datasettet.

Stopper rolig (kan gjenopptas) hvis Ollama laster en modell eller en
`inspect eval --model ollama/` starter. Kjør hele skriptet under vakt.py.

  standard.py utvalg --sett nst --data DIR --n 1500 --seed 20261019
  standard.py kjor   --sett nst --data DIR --utvalg FIL --arbeid DIR --modellvalg medium --malform nb nn
  standard.py oppsummer --resultater FIL.jsonl
"""
import argparse
import json
import pathlib
import random
import subprocess
import sys
import tarfile

HER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HER))
sys.path.insert(0, str(HER.parent / "kjerne"))
import feilanalyse  # noqa: E402
import kjerne  # noqa: E402
import norm  # noqa: E402


# ------------------------------------------------------------------ NST
def nst_rader(data):
    """Ytringene i NbAiLab/NST-testen (nærmikrofon): id = <pid>/<file>."""
    rader = []
    for f in sorted(pathlib.Path(data).glob("nst_no_test_close-*.json")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                d = json.loads(ln)
                rader.append({"id": f"{d['pid']}/{d['file']}", "tekst": d["text"], "type": d.get("type", ""),
                              "region": d.get("Region_of_Birth", ""), "taler": f"{d['pid']}:{d.get('Speaker_ID', '')}"})
    return rader


def utvalg(rader, n, seed):
    ider = sorted({r["id"] for r in rader})
    if len(ider) != len(rader):
        raise SystemExit(f"id-ene er ikke unike ({len(rader)} rader, {len(ider)} id-er)")
    return sorted(random.Random(seed).sample(ider, n))


def pakk_ut(data, ider, mal):
    """Pakker ut bare de valgte wav-filene. Returnerer {id: sti}."""
    mal = pathlib.Path(mal)
    mal.mkdir(parents=True, exist_ok=True)
    onsket = set(ider)
    funnet = {}
    for t in sorted(pathlib.Path(data).glob("nst_no_test_close-*.tar.gz")):
        with tarfile.open(t, "r:gz") as tf:
            for m in tf:
                if not m.isfile():
                    continue
                deler = pathlib.PurePosixPath(m.name).parts
                if len(deler) < 2:
                    continue
                kandidat = f"{deler[-2]}/{deler[-1]}"
                if kandidat in onsket and kandidat not in funnet:
                    ut = mal / kandidat.replace("/", "__")
                    with tf.extractfile(m) as kilde, open(ut, "wb") as fh:
                        fh.write(kilde.read())
                    funnet[kandidat] = ut
    return funnet


# --------------------------------------------------------------- kjøring
def ollama_fri():
    try:
        ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=20).stdout.splitlines()[1:]
    except (OSError, subprocess.TimeoutExpired):
        ps = []
    insp = subprocess.run(["pgrep", "-f", "inspect eval.*--model ollama/"], capture_output=True).returncode == 0
    return not [l for l in ps if l.strip()] and not insp


def kjor(rader, ider, lyd, utfil, modellvalg, malformer, sjekk_hver=25, kjor_en=None):
    kjor_en = kjor_en or kjerne.transkriber
    tekst = {r["id"]: r for r in rader}
    utfil = pathlib.Path(utfil)
    ferdig = set()
    if utfil.exists():
        for ln in utfil.read_text(encoding="utf-8").splitlines():
            d = json.loads(ln)
            ferdig.add((d["id"], d["malform_valgt"]))
    grunn = kjerne.standard_oppsett(modellvalg=modellvalg)
    sha = kjerne.verifiser_modell(grunn.modell, grunn.sha256)
    nye = 0
    with utfil.open("a", encoding="utf-8") as fh:
        for i, uid in enumerate(ider):
            if i % sjekk_hver == 0 and not ollama_fri():
                print("Ollama har lastet en modell, eller ollama-inspect lever: stopper (kan gjenopptas)", flush=True)
                return 7
            for mf in malformer:
                if (uid, mf) in ferdig or uid not in lyd:
                    continue
                o = kjerne.dataclasses.replace(grunn, malform=mf)
                r = kjor_en(lyd[uid], o, sha=sha)
                fh.write(json.dumps({"id": uid, "malform_valgt": mf, "modellvalg": modellvalg,
                                     "fasit": tekst[uid]["tekst"], "type": tekst[uid]["type"],
                                     "verbatim": r["verbatim"], "korrigert": r["korrigert"]},
                                    ensure_ascii=False) + "\n")
                fh.flush()
                nye += 1
            if i % 50 == 0:
                print(f"{i + 1}/{len(ider)} ({nye} nye)", flush=True)
    return 0


# ------------------------------------------------------------- oppsummering
def oppsummer(utfil):
    """Bare tall: per (modellvalg, målform whisper fikk) og tekst (rå/korrigert)."""
    grupper = {}
    for ln in pathlib.Path(utfil).read_text(encoding="utf-8").splitlines():
        d = json.loads(ln)
        grupper.setdefault((d["modellvalg"], d["malform_valgt"]), []).append(d)
    ut = []
    for (mv, mf), rader in sorted(grupper.items()):
        rad = {"modellvalg": mv, "malform_valgt": mf, "n": len(rader)}
        for felt, navn in (("verbatim", "ra"), ("korrigert", "korrigert")):
            par = [(d["fasit"], d[felt]) for d in rader]
            rad[navn] = {"wer": round(norm.wer(*zip(*par)), 4), "cer": round(norm.cer(*zip(*par)), 4),
                         "nektelser": feilanalyse.sum_tapte(par)}
        ut.append(rad)
    return ut


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="steg", required=True)
    u = sub.add_parser("utvalg")
    u.add_argument("--sett", choices=["nst"], required=True)
    u.add_argument("--data", required=True)
    u.add_argument("--n", type=int, required=True)
    u.add_argument("--seed", type=int, required=True)
    u.add_argument("--ut", required=True, help="id-liste (bare id-er) i repoet")
    k = sub.add_parser("kjor")
    k.add_argument("--sett", choices=["nst"], required=True)
    k.add_argument("--data", required=True)
    k.add_argument("--utvalg", required=True)
    k.add_argument("--arbeid", required=True, help="arbeidsmappe på Vault (lyd og resultater)")
    k.add_argument("--modellvalg", required=True)
    k.add_argument("--malform", nargs="+", default=["nb", "nn"])
    o = sub.add_parser("oppsummer")
    o.add_argument("--resultater", required=True)
    a = ap.parse_args(argv)

    if a.steg == "utvalg":
        ider = utvalg(nst_rader(a.data), a.n, a.seed)
        p = pathlib.Path(a.ut)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# NbAiLab/NST test, nærmikrofon (no-close). Seedet utvalg: seed={a.seed}, n={a.n}.\n"
                     f"# id = <pid>/<file>. Bare id-er; ingen lyd eller tekst fra datasettet.\n"
                     + "\n".join(ider) + "\n", encoding="utf-8")
        print(f"{len(ider)} id-er skrevet til {p}")
        return 0
    if a.steg == "kjor":
        arbeid = kjerne.krev_montert(a.arbeid)
        ider = [l.strip() for l in pathlib.Path(a.utvalg).read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")]
        rader = nst_rader(a.data)
        lydmappe = arbeid / "lyd"
        lyd = {}
        if lydmappe.is_dir():
            lyd = {p.name.replace("__", "/"): p for p in lydmappe.iterdir() if p.suffix == ".wav"}
        if set(ider) - set(lyd):
            lyd.update(pakk_ut(a.data, sorted(set(ider) - set(lyd)), lydmappe))
        mangler = set(ider) - set(lyd)
        print(f"lyd: {len(lyd)} av {len(ider)} funnet" + (f", {len(mangler)} mangler" if mangler else ""), flush=True)
        return kjor(rader, ider, lyd, arbeid / f"resultater_{a.modellvalg}.jsonl", a.modellvalg, a.malform)
    if a.steg == "oppsummer":
        print(json.dumps(oppsummer(a.resultater), ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    sys.exit(main())
