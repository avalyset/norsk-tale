"""Preregistreringen (prereg-v1) skal holde: kjernen og de frosne filene er
byte-identiske med SHA256-ene i kalibrering/manifest.json, FROZEN.txt og AVVIK
nr. 2. MCP-serveren (v0.2.0) pakker inn kjernen; den endrer den ikke
(docs/decisions/NTA-0007). Feiler denne testen, gjelder fase-1-resultatene ikke
lenger koden: stopp og før AVVIK før noe annet gjøres."""
import hashlib
import json
import pathlib
import re

import pytest

ROT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROT / "kalibrering" / "manifest.json").read_text(encoding="utf-8"))
KJERNEN = ["kjerne/kjerne.py", "kjerne/korriger.py", "kjerne/vokabular/fasit_offentlig.tsv",
           "kjerne/vokabular/offentlig_no.txt"]


def sha(rel):
    return hashlib.sha256((ROT / rel).read_bytes()).hexdigest()


@pytest.mark.parametrize("rel", KJERNEN)
def test_kjernen_er_uendret_siden_prereg_v1(rel):
    assert sha(rel) == MANIFEST["kode_sha256"][rel], f"{rel} avviker fra prereg-v1"


@pytest.mark.parametrize("rel", sorted(MANIFEST["kode_sha256"]))
def test_all_frosset_kode_er_uendret(rel):
    assert sha(rel) == MANIFEST["kode_sha256"][rel], f"{rel} avviker fra manifest.json"


def test_metode_og_manifest_er_uendret_siden_frysen():
    frosset = (ROT / "kalibrering" / "FROZEN.txt").read_text(encoding="utf-8")
    for navn, rel in (("METHOD.md", "kalibrering/METHOD.md"), ("manifest.json", "kalibrering/manifest.json"),
                      ("reproduser.py", "kalibrering/reproduser.py")):
        m = re.search(rf"^{re.escape(navn)}\s+([0-9a-f]{{64}})$", frosset, re.M)
        assert m and sha(rel) == m.group(1), f"{rel} avviker fra FROZEN.txt"


def test_fase1_er_uendret_siden_avvik_2():
    avvik = (ROT / "kalibrering" / "AVVIK.md").read_text(encoding="utf-8")
    assert sha("kalibrering/fase1.py") in avvik, "fase1.py avviker fra SHA-en i AVVIK nr. 2"
