#!/usr/bin/env python3
"""norsk-tale — entitetskorrektor (fra NORSKRIBER).

Leser fasitfilene, korrigerer en transkripsjon og skriver alltid til en
oppgitt utdatakatalog — aldri ved siden av inndata, som kan være persondata.

  ikkeord    substitueres, ordgrensebevisst og case-bevarende
  kollisjon  substitueres aldri stille; kildeformen står med markør
             ⟦kildeform → korrekt_form?⟧ og mennesket avgjør per forekomst

INVARIANT: feilklasse=usikker => klasse=kollisjon. Brudd gir ikke-null exit.
"""
import re, sys, csv, argparse, pathlib, unicodedata
from collections import Counter, defaultdict

KLASSER = {"ikkeord", "kollisjon"}
FEILKLASSER = {"garble", "lyd-tvetydig", "usikker"}


class Avvisning(Exception):
    pass


def les_fasit(stier):
    """Leser fasitfiler og håndhever § 8e. Returnerer liste av rader."""
    rader, feil = [], []
    sett = {}                       # feilform.lower() -> (korrekt_form, klasse, fil, lnr)
    for sti in stier:
        if not sti.exists():
            raise Avvisning(f"fasitfil finnes ikke: {sti}")
        for lnr, ln in enumerate(sti.read_text(encoding="utf-8").splitlines(), 1):
            if ln.startswith("#") or not ln.strip():
                continue
            f = ln.split("\t")
            if f[0] == "korrekt_form":
                continue
            if len(f) != 4:
                feil.append(f"{sti.name}:{lnr}: forventet 4 kolonner, fikk {len(f)}")
                continue
            kf, ff, kl, fk = (x.strip() for x in f)

            # (1) rad uten klasse, eller klasse utenfor {ikkeord, kollisjon}
            if not kl:
                feil.append(f"{sti.name}:{lnr}: rad uten klasse ({ff!r})")
                continue
            if kl not in KLASSER:
                feil.append(f"{sti.name}:{lnr}: ukjent klasse {kl!r} ({ff!r}) "
                            f"— tillatt: {sorted(KLASSER)}")
                continue
            if fk not in FEILKLASSER:
                feil.append(f"{sti.name}:{lnr}: ukjent feilklasse {fk!r} ({ff!r}) "
                            f"— tillatt: {sorted(FEILKLASSER)}")
                continue

            # (2) INVARIANTBRUDD
            if fk == "usikker" and kl == "ikkeord":
                feil.append(f"{sti.name}:{lnr}: INVARIANTBRUDD — feilklasse=usikker "
                            f"med klasse=ikkeord ({ff!r}). En form vi ikke vet om er "
                            f"feil, substitueres aldri stille.")
                continue

            # (3) duplikat feilform med motstridende korrekt_form eller klasse
            n = ff.lower()
            if n in sett:
                pkf, pkl, pfil, plnr = sett[n]
                if pkf != kf or pkl != kl:
                    feil.append(f"{sti.name}:{lnr}: duplikat feilform {ff!r} strider "
                                f"mot {pfil}:{plnr} ({pkf!r}/{pkl} vs {kf!r}/{kl})")
                # Identisk duplikat er lovlig, men bærer ingen ny informasjon —
                # det slippes gjennom uten å telles to ganger.
                continue
            sett[n] = (kf, kl, sti.name, lnr)
            rader.append({"korrekt_form": kf, "feilform": ff,
                          "klasse": kl, "feilklasse": fk, "kilde": f"{sti.name}:{lnr}"})
    if feil:
        raise Avvisning("fasittabellen avvises:\n  " + "\n  ".join(feil))
    if not rader:
        raise Avvisning("fasittabellen er tom")
    return rader


def bevar_case(kilde, mal):
    """Overfører kildeformens case-mønster til målformen der det gir mening."""
    if kilde.isupper() and len(kilde) > 1:
        return mal.upper()
    if kilde.islower():
        return mal.lower()
    if kilde[:1].isupper() and kilde[1:].islower():
        return mal[:1].upper() + mal[1:]
    return mal


def korriger(tekst, rader):
    """Lengste form først. Returnerer (ny_tekst, hendelser, tellinger)."""
    # § 3/§ 8a: lengste form først, konsumerte spenn er urørlige
    ordnet = sorted(rader, key=lambda r: len(r["feilform"]), reverse=True)
    treff = []                                   # (start, slutt, rad, funnet_streng)
    konsumert = []

    def overlapper(a, b):
        return any(not (b <= s or a >= e) for s, e in konsumert)

    for r in ordnet:
        pat = re.compile(r"(?<!\w)" + re.escape(r["feilform"]) + r"(?!\w)",
                         re.IGNORECASE | re.UNICODE)
        for m in pat.finditer(tekst):
            if overlapper(m.start(), m.end()):
                continue
            konsumert.append((m.start(), m.end()))
            treff.append((m.start(), m.end(), r, m.group()))

    treff.sort(key=lambda x: x[0])
    linjestart = [0]
    for i, ch in enumerate(tekst):
        if ch == "\n":
            linjestart.append(i + 1)

    def linjenr(pos):
        lo, hi = 0, len(linjestart) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if linjestart[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    ut, sist, hendelser = [], 0, []
    tall = Counter()
    for s, e, r, funnet in treff:
        ut.append(tekst[sist:s])
        if r["klasse"] == "ikkeord":
            erstatning = bevar_case(funnet, r["korrekt_form"])
            tall["substituert"] += 1
            handling = "substituert"
        else:
            erstatning = f"⟦{funnet} → {r['korrekt_form']}?⟧"
            tall["flagget"] += 1
            handling = "flagget"
        ut.append(erstatning)
        hendelser.append({"linje": linjenr(s), "fra": funnet, "til": erstatning,
                          "klasse": r["klasse"], "feilklasse": r["feilklasse"],
                          "handling": handling, "kilde": r["kilde"]})
        sist = e
    ut.append(tekst[sist:])
    return "".join(ut), hendelser, tall


def main(argv=None):
    ap = argparse.ArgumentParser(description="norsk-tale entitetskorrektor")
    ap.add_argument("transkripsjon", type=pathlib.Path)
    ap.add_argument("--ut-katalog", required=True, type=pathlib.Path,
                    help="Alle utdata hit. Skal være gitignored — utdata er persondata.")
    ap.add_argument("--fasit", action="append", type=pathlib.Path, default=None,
                    help="Fasitfil; gjenta for flere. Standard: vokabular/fasit_offentlig.tsv.")
    a = ap.parse_args(argv)

    stier = a.fasit or [
        pathlib.Path(__file__).resolve().parent / "vokabular" / "fasit_offentlig.tsv",
    ]
    try:
        rader = les_fasit([pathlib.Path(s) for s in stier])
    except Avvisning as e:
        print(f"AVVIST: {e}", file=sys.stderr)
        return 2

    tekst = a.transkripsjon.read_text(encoding="utf-8")
    ny, hendelser, tall = korriger(tekst, rader)

    a.ut_katalog.mkdir(parents=True, exist_ok=True)
    navn = a.transkripsjon.stem
    (a.ut_katalog / f"{navn}.verbatim.txt").write_text(tekst, encoding="utf-8")
    (a.ut_katalog / f"{navn}.korrigert.txt").write_text(ny, encoding="utf-8")
    logg = a.ut_katalog / f"{navn}.substitusjonslogg.tsv"
    with logg.open("w", encoding="utf-8") as fh:
        fh.write("# Substitusjonslogg. PERSONDATA — inneholder tekstformer fra opptaket.\n")
        fh.write("linje\thandling\tfra\ttil\tklasse\tfeilklasse\tfasitkilde\n")
        for h in hendelser:
            fh.write(f"{h['linje']}\t{h['handling']}\t{h['fra']}\t{h['til']}\t"
                     f"{h['klasse']}\t{h['feilklasse']}\t{h['kilde']}\n")

    traff = {h["fra"].lower() for h in hendelser}
    urort = [r for r in rader if r["feilform"].lower() not in traff]
    print(f"fasitrader:   {len(rader)}")
    print(f"substituert:  {tall['substituert']}   (forekomster, klasse=ikkeord)")
    print(f"flagget:      {tall['flagget']}   (forekomster, klasse=kollisjon)")
    print(f"urørt:        {len(urort)}   (fasitrader uten treff i denne fila)")
    print(f"utdata:       {a.ut_katalog}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
