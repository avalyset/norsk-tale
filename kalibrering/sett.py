"""norsk-tale — testsettene i standardkalibreringen (METHOD.md § 3).

Hvert sett har to funksjoner:

  rader(data)            kvalifiserte ytringer etter forbehandlingen, og antall
                         utelukket før utvalget per grunn:
                         ([Rad, ...], {grunn: antall})
  pakk_ut(data, ider, mal) pakker ut bare lyden til de valgte id-ene til `mal`
                         og returnerer {id: sti}

`data` er roten for datasettene ($NORSK_TALE_DATA). Ingenting her skriver tekst
fra datasettene noe annet sted enn til lydfiler under `mal`.
"""
import csv
import dataclasses
import glob
import json
import pathlib
import re
import sys
import tarfile
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import norm  # noqa: E402


@dataclasses.dataclass(frozen=True)
class Rad:
    id: str
    fasit: str
    malform: str        # fasitens målform: nb | nn
    stratum: str        # utvalgsstratum ("" = ingen)
    gruppe: str = ""    # rapporteringsgruppe (dialektgruppe o.l.)


def _tom(tekst):
    return not norm.normaliser(tekst).split()


VINKEL = re.compile(r"<[^<>]*>")


# ------------------------------------------------------------------ FLEURS
def fleurs_rader(data):
    p = pathlib.Path(data) / "fleurs_nb_no" / "test.tsv"
    rader, ute = [], {"tom_fasit": 0}
    with p.open(encoding="utf-8", newline="") as fh:
        for x in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            if _tom(x[2]):
                ute["tom_fasit"] += 1
                continue
            rader.append(Rad(x[1], x[2], "nb", ""))
    return rader, ute


def fleurs_pakk_ut(data, ider, mal):
    return _pakk_tar(sorted(pathlib.Path(data, "fleurs_nb_no").glob("test.tar.gz")), ider, mal,
                     lambda navn: pathlib.PurePosixPath(navn).name)


# --------------------------------------------------------------------- NST
# Opplest tegnsetting i NST-manuset; byttes med tegnet, som normaliseringen fjerner.
NST_TEGN = {"Punktum": ".", "Komma": ",", "Spørsmålstegn": "?", "Utropstegn": "!"}
NST_TEGN_RE = re.compile(r"\\(" + "|".join(NST_TEGN) + r")\b")


def nst_fasit(tekst):
    return VINKEL.sub(" ", NST_TEGN_RE.sub(lambda m: NST_TEGN[m.group(1)], tekst))


def nst_rader(data):
    rader, ute = [], {"tom_fasit": 0}
    for f in sorted(pathlib.Path(data, "nst_test").glob("nst_no_test_close-*.json")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            d = json.loads(ln)
            tekst = nst_fasit(d["text"])
            if _tom(tekst):
                ute["tom_fasit"] += 1
                continue
            rader.append(Rad(f"{d['pid']}/{d['file']}", tekst, "nb", ""))
    return rader, ute


def nst_pakk_ut(data, ider, mal):
    def nokkel(navn):
        deler = pathlib.PurePosixPath(navn).parts
        return f"{deler[-2]}/{deler[-1]}" if len(deler) >= 2 else None
    return _pakk_tar(sorted(pathlib.Path(data, "nst_test").glob("nst_no_test_close-*.tar.gz")), ider, mal, nokkel)


# -------------------------------------------------------------------- NPSC
NPSC_NOLING = re.compile(r"<(ee|mm)>")
NPSC_UFULLSTENDIG = ("<qq>", "<INAUDIBLE>")


def npsc_rader(data):
    rader, ute = [], {"tom_fasit": 0, "qq_inaudible": 0, "annet_sprak": 0}
    for f in sorted(glob.glob(str(pathlib.Path(data, "npsc_test", "*.json")))):
        for ln in open(f, encoding="utf-8"):
            if not ln.strip():
                continue
            d = json.loads(ln)
            kode = {"nb-NO": "nb", "nn-NO": "nn"}.get(d["sentence_language_code"])
            if kode is None:
                ute["annet_sprak"] += 1
                continue
            tekst = d["normsentence_text"]
            if any(m in tekst for m in NPSC_UFULLSTENDIG):
                ute["qq_inaudible"] += 1
                continue
            tekst = NPSC_NOLING.sub(" ", tekst)
            if _tom(tekst):
                ute["tom_fasit"] += 1
                continue
            rader.append(Rad(d["path"].removeprefix("audio/"), tekst, kode, kode))
    return rader, ute


def npsc_pakk_ut(data, ider, mal):
    return _pakk_tar(sorted(pathlib.Path(data, "npsc_test").glob("*_16K_mp3.tar.gz")), ider, mal,
                     lambda navn: pathlib.PurePosixPath(navn).name.removesuffix(".mp3"), suffiks=".mp3")


# ----------------------------------------------------------------- NB Tale
def _nbtale_trans(tekst):
    """part_1.trans: «"sti"» åpner en ytring; linjer med fire felt har ordet i felt 4."""
    ytringer, cur, ordliste = [], None, []
    for ln in tekst.splitlines():
        if ln.startswith('"'):
            if cur:
                ytringer.append((cur, ordliste))
            cur, ordliste = ln.strip().strip('"'), []
        elif cur:
            p = ln.split("\t")
            if len(p) >= 4 and p[3] and not (p[3].startswith("<") and p[3].endswith(">")):
                ordliste.append(p[3])
    if cur:
        ytringer.append((cur, ordliste))
    return ytringer


def nb_tale_rader(data):
    with zipfile.ZipFile(pathlib.Path(data, "nb_tale", "Annotation.zip")) as z:
        tekst = z.read("Annotation/part_1.trans").decode("utf-8")
    rader, ute = [], {"tom_fasit": 0}
    for sti, ordliste in _nbtale_trans(tekst):
        navn = sti.split("/")[-1]
        if "_x-" not in navn:
            continue
        fasit = " ".join(ordliste)
        if _tom(fasit):
            ute["tom_fasit"] += 1
            continue
        g = re.search(r"_(g\d\d)_", navn).group(1)
        rader.append(Rad(navn, fasit, "nb", g, g))
    return rader, ute


def nb_tale_pakk_ut(data, ider, mal):
    return _pakk_tar([pathlib.Path(data, "nb_tale", "sennheiser_1.tar.gz")], ider, mal,
                     lambda navn: pathlib.PurePosixPath(navn).name.removesuffix(".wav"), suffiks=".wav")


# -------------------------------------------------------------- NB Samtale
SAMTALE_LYD = re.compile(r"%(eee|mmm|emm|heh|qqq|ttt|hhh|music|noise)\b")
SAMTALE_UFULLSTENDIG = re.compile(r"%(unint|overlapping|unk|foreign)\b")
SAMTALE_SKRASTREK = re.compile(r"\S*\\(\S+)")      # uttalenær\ordbokform → ordbokform
SAMTALE_AVBRUTT = re.compile(r"\S*£")             # avbrutt ord → fjernes


def samtale_fasit(tekst):
    t = SAMTALE_SKRASTREK.sub(r"\1", tekst)
    t = SAMTALE_LYD.sub(" ", t)
    return SAMTALE_AVBRUTT.sub(" ", t)


def nb_samtale_rader(data):
    with zipfile.ZipFile(pathlib.Path(data, "nb_samtale", "nb_samtale.zip")) as z:
        linjer = z.read("nb_samtale/metadata.jsonl").decode("utf-8").splitlines()
    rader, ute = [], {"tom_fasit": 0, "unint_overlapping_unk_foreign": 0}
    for ln in linjer:
        if not ln.strip():
            continue
        d = json.loads(ln)
        if "/test/" not in d["file_name"]:
            continue
        if SAMTALE_UFULLSTENDIG.search(d["transcription"]):
            ute["unint_overlapping_unk_foreign"] += 1
            continue
        fasit = samtale_fasit(d["transcription"])
        if _tom(fasit):
            ute["tom_fasit"] += 1
            continue
        mf = {"bm": "nb", "nn": "nn"}[d["orthography"]]
        rader.append(Rad(d["file_name"], fasit, mf, "", d.get("dialect", "")))
    return rader, ute


def nb_samtale_pakk_ut(data, ider, mal):
    mal = pathlib.Path(mal)
    mal.mkdir(parents=True, exist_ok=True)
    funnet = {}
    with zipfile.ZipFile(pathlib.Path(data, "nb_samtale", "nb_samtale.zip")) as z:
        for uid in ider:
            try:
                innhold = z.read(f"nb_samtale/{uid}")
            except KeyError:
                continue
            ut = mal / _filnavn(uid)
            ut.write_bytes(innhold)
            funnet[uid] = ut
    return funnet


# ------------------------------------------------------------------ felles
def _filnavn(uid, suffiks=""):
    return uid.replace("/", "__") + suffiks


def _pakk_tar(arkiver, ider, mal, nokkel, suffiks=""):
    """Leser arkivene sekvensielt og skriver bare medlemmer hvis nøkkel er valgt."""
    mal = pathlib.Path(mal)
    mal.mkdir(parents=True, exist_ok=True)
    onsket, funnet = set(ider), {}
    for a in arkiver:
        with tarfile.open(a, "r:*") as tf:
            for m in tf:
                if not m.isfile():
                    continue
                k = nokkel(m.name)
                if k in onsket and k not in funnet:
                    ut = mal / _filnavn(k, suffiks)
                    with tf.extractfile(m) as kilde, open(ut, "wb") as fh:
                        fh.write(kilde.read())
                    funnet[k] = ut
    return funnet


SETT = {
    "fleurs": (fleurs_rader, fleurs_pakk_ut),
    "nst": (nst_rader, nst_pakk_ut),
    "npsc": (npsc_rader, npsc_pakk_ut),
    "nb_tale": (nb_tale_rader, nb_tale_pakk_ut),
    "nb_samtale": (nb_samtale_rader, nb_samtale_pakk_ut),
}
