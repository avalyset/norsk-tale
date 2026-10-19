#!/usr/bin/env python3
"""Kryssjekk: norm.py (standardbibliotek-port) mot ekte jiwer.

Kjøres med en Python som har jiwer installert, for eksempel en egen venv:
  /Volumes/Vault/norsk-tale/venv-jiwer/bin/python kalibrering/kryssjekk_jiwer.py

`nostram_normalizer` under er NbAiLab/nostram utils/evaluate.py `normalizer`
(commit 448238e9, Apache-2.0) med standardvalgene extra_clean=False og
super_normalize=False, kopiert uten endring i transformkjeden.
"""
import json
import pathlib
import sys

import jiwer

HER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HER))
import norm  # noqa: E402
import score  # noqa: E402


def nostram_normalizer(text):
    transformation = jiwer.Compose([
        jiwer.ToLowerCase(),
        jiwer.RemoveMultipleSpaces(),
        jiwer.Strip(),
        jiwer.RemovePunctuation(),
        jiwer.RemoveWhiteSpace(replace_by_space=True)
    ])
    return transformation(text)


EKSTRA = [
    "  Nord-Norge, Skatteetaten!  ", "«Hei» – sa hun.", "3 450 kr", "3.450,- kroner", "25 %", "14. mars",
    "Det er 30 år siden… og det er jo 96?", "Ikke si det, men ...", "Han sa: \"nei\"; ikkje!", "a\tb\nc",
    "UDI/NAV (Helfo)", "e-post: post@nav.no", "50/50", "‘sitat’ og „sitat“", "Ørsted Æble Å", "",
    "   ", "<|nocaptions|> Det er", "kl. 09:30", "#merket @nevnt", "100 000 000", "Tindå-trådene",
]


def par():
    tekster = [s["setning"] for s in score.les_setninger(HER / "manus_v1.tsv")] + EKSTRA
    hyp = [t.replace("ikke", "").replace("Skatteetaten", "skatteetaten,").replace("3", "tre") for t in tekster]
    return tekster, hyp


def main():
    tekster, hyp = par()
    avvik_norm = [(t, nostram_normalizer(t), norm.normaliser(t)) for t in tekster + hyp
                  if nostram_normalizer(t) != norm.normaliser(t)]
    ikke_tomme = [(r, h) for r, h in zip(tekster, hyp) if nostram_normalizer(r).strip()]
    refs = [nostram_normalizer(r) for r, _ in ikke_tomme]
    hyps = [nostram_normalizer(h) for _, h in ikke_tomme]
    jw, jc = jiwer.wer(refs, hyps), jiwer.cer(refs, hyps)
    vw = norm.wer([r for r, _ in ikke_tomme], [h for _, h in ikke_tomme])
    vc = norm.cer([r for r, _ in ikke_tomme], [h for _, h in ikke_tomme])
    from importlib.metadata import version
    rapport = {"jiwer_versjon": version("jiwer"),
               "tekster": len(tekster) + len(hyp), "normaliseringsavvik": len(avvik_norm),
               "eksempler_avvik": avvik_norm[:10], "par": len(ikke_tomme),
               "wer_jiwer": jw, "wer_norm": vw, "cer_jiwer": jc, "cer_norm": vc,
               "wer_lik": abs(jw - vw) < 1e-12, "cer_lik": abs(jc - vc) < 1e-12}
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
    return 0 if not avvik_norm and rapport["wer_lik"] and rapport["cer_lik"] else 1


if __name__ == "__main__":
    sys.exit(main())
