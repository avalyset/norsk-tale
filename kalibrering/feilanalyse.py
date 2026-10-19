"""norsk-tale — feilanalyse som ikke er en score: nektelser som forsvinner.

Teller nektelser i referansen og i utdata etter samme normalisering som WER
(norm.py), og rapporterer hvor mange som mangler og hvor mange som er kommet til.
Bokmåls- og nynorskformer av samme nektelse regnes som like (ikke = ikkje,
verken = korkje, ingen = inga), så et målformbytte telles ikke som tapt nektelse.
«eller» i verken–eller telles ikke for seg.
"""
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import norm  # noqa: E402

NEKTELSE = {
    "ikke": "ikke", "ikkje": "ikke",
    "aldri": "aldri",
    "ingen": "ingen", "inga": "ingen", "intet": "ingen",
    "ingenting": "ingenting",
    "verken": "verken", "korkje": "verken",
    "nei": "nei",
}


def nektelser(tekst):
    return Counter(NEKTELSE[o] for o in norm.normaliser(tekst).split() if o in NEKTELSE)


def tapte_nektelser(referanse, hypotese):
    """{referanse, utdata, tapt, lagt_til, per_type: {type: {ref, ut, tapt, lagt_til}}}"""
    r, h = nektelser(referanse), nektelser(hypotese)
    per = {}
    for t in sorted(set(r) | set(h)):
        per[t] = {"ref": r[t], "ut": h[t], "tapt": max(0, r[t] - h[t]), "lagt_til": max(0, h[t] - r[t])}
    return {"referanse": sum(r.values()), "utdata": sum(h.values()),
            "tapt": sum(v["tapt"] for v in per.values()),
            "lagt_til": sum(v["lagt_til"] for v in per.values()), "per_type": per}


def sum_tapte(par):
    """Over et sett: par = [(referanse, hypotese), ...]. Andel tapt av referansens nektelser."""
    ref = tapt = lagt = 0
    for r, h in par:
        t = tapte_nektelser(r, h)
        ref, tapt, lagt = ref + t["referanse"], tapt + t["tapt"], lagt + t["lagt_til"]
    return {"referanse": ref, "tapt": tapt, "lagt_til": lagt,
            "andel_tapt": round(tapt / ref, 4) if ref else None}
