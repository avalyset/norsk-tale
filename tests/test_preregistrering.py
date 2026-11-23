"""Preregistreringen (prereg-v1) skal holde: kjernen er byte-identisk med SHA256-ene i
manifestet til standardkalibreringen. Manifestet og riggen ligger fra 0.3.1 i
https://github.com/avalyset/norsk-tale-kalibrering (kalibrering/manifest.json, «kode_sha256»);
verdiene under er kopiert derfra. Feiler denne testen, gjelder fase-1-resultatene ikke
lenger koden: stopp og før avvik i kalibreringsrepoet før noe annet gjøres."""
import hashlib
import pathlib

import pytest

ROT = pathlib.Path(__file__).resolve().parents[1]
PREREG_V1 = {
    "kjerne/kjerne.py": "962e691c47824a4160bbd8fd208330abac5a7d4fd85ab803bedfaa17fb528a24",
    "kjerne/korriger.py": "335bc6ac2454ee1744556f411c2f7cf6a44fcd02579b07ba9d201e863752cc68",
    "kjerne/modeller.json": "72a0de5543db4b1f12917b87aaa1fc151bf1d517972239d0f14c21de60b27289",
    "kjerne/vokabular/fasit_offentlig.tsv": "fb61815f42d71323fce6680dec388eccf78de68c5d0062c922c07389e4c63ce6",
    "kjerne/vokabular/offentlig_no.txt": "c6ddfd764ce1b0bb113e94df172e307414990067f3d7f67102ef4236036cb341",
}


@pytest.mark.parametrize("rel", sorted(PREREG_V1))
def test_kjernen_er_uendret_siden_prereg_v1(rel):
    assert hashlib.sha256((ROT / rel).read_bytes()).hexdigest() == PREREG_V1[rel], f"{rel} avviker fra prereg-v1"
