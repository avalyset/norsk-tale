"""mcp/start.py uten nett: venvet lages og flyttes på plass atomisk, samtidige
oppstarter ødelegger ikke for hverandre, og bare egne rester ryddes."""
import os
import pathlib
import subprocess
import sys

ROT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT / "mcp"))
import start  # noqa: E402


def falsk_installasjon(monkeypatch, kall, under=None):
    def lag(selv, mappe):
        (pathlib.Path(mappe) / "bin").mkdir(parents=True)
        (pathlib.Path(mappe) / "bin" / "python").write_text("#!/bin/sh\n")
    def kjor(argv, **k):
        kall.append(argv)
        if under:
            under()
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(start.venv.EnvBuilder, "create", lag)
    monkeypatch.setattr(start.subprocess, "run", kjor)


def test_installerer_med_hasher_og_flytter_paa_plass(tmp_path, monkeypatch):
    kall = []
    falsk_installasjon(monkeypatch, kall)
    py = start.sikre_venv(tmp_path)
    mappe = start.venv_mappe(tmp_path)
    assert py == mappe / "bin" / "python" and (mappe / ".installert").is_file()
    assert "--require-hashes" in kall[0] and "--only-binary" in kall[0] and str(start.KRAV) in kall[0]
    assert [p.name for p in tmp_path.iterdir()] == [mappe.name]          # ingen rester


def test_ferdig_venv_brukes_uten_installasjon(tmp_path, monkeypatch):
    kall = []
    falsk_installasjon(monkeypatch, kall)
    start.sikre_venv(tmp_path)
    start.sikre_venv(tmp_path)
    assert len(kall) == 1


def test_en_annen_prosess_som_kommer_forst_vinner(tmp_path, monkeypatch):
    mappe = start.venv_mappe(tmp_path)

    def annen_prosess_blir_ferdig():
        (mappe / "bin").mkdir(parents=True)
        (mappe / ".installert").write_text("ok\n")
        (mappe / "fra-den-andre").write_text("x")

    falsk_installasjon(monkeypatch, [], under=annen_prosess_blir_ferdig)
    start.sikre_venv(tmp_path)
    assert (mappe / "fra-den-andre").is_file()                          # den andres venv står
    assert [p.name for p in tmp_path.iterdir()] == [mappe.name]          # vår egen mappe er borte


def test_halvferdig_eldre_mappe_legges_til_side_og_ryddes(tmp_path, monkeypatch):
    mappe = start.venv_mappe(tmp_path)
    (mappe / "lib").mkdir(parents=True)                                 # avbrutt, uten .installert
    falsk_installasjon(monkeypatch, [])
    start.sikre_venv(tmp_path)
    assert (mappe / ".installert").is_file()
    assert [p.name for p in tmp_path.iterdir()] == [mappe.name]


def test_rydder_bare_egne_rester_fra_doede_prosesser(tmp_path, monkeypatch):
    mappe = start.venv_mappe(tmp_path)
    dod = subprocess.Popen([sys.executable, "-c", "pass"]); dod.wait()
    for navn in (f"{mappe.name}.ny-{dod.pid}", f"{mappe.name}.ny-{os.getppid()}", "noe-annet", f"{mappe.name}.ny-x"):
        (tmp_path / navn).mkdir()
    falsk_installasjon(monkeypatch, [])
    start.sikre_venv(tmp_path)
    igjen = sorted(p.name for p in tmp_path.iterdir())
    assert f"{mappe.name}.ny-{dod.pid}" not in igjen                     # død prosess: ryddet
    assert f"{mappe.name}.ny-{os.getppid()}" in igjen                     # levende prosess: urørt
    assert "noe-annet" in igjen and f"{mappe.name}.ny-x" in igjen        # fremmede navn: urørt


def test_rester_ryddes_ogsaa_naar_venvet_alt_er_ferdig(tmp_path, monkeypatch):
    falsk_installasjon(monkeypatch, [])
    start.sikre_venv(tmp_path)
    mappe = start.venv_mappe(tmp_path)
    dod = subprocess.Popen([sys.executable, "-c", "pass"]); dod.wait()
    (tmp_path / f"{mappe.name}.ny-{dod.pid}").mkdir()
    start.sikre_venv(tmp_path)
    assert [p.name for p in tmp_path.iterdir()] == [mappe.name]
