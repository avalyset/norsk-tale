"""scripts/avvis-opptak: PreToolUse-kroken som nekter modellen å starte mikrofonen.

Kroken nekter Bash-kall som kjører scripts/dikter uten --fil (mikrofonmodus). Filmodus
(--fil, brukt av skillen transkriber) og --help slippes gjennom, og kall som bare leser eller
nevner skriptet også. Brukerens egen start via skillen passerer ikke kroken (målt i Claude
Code 2.1.303), så den påvirkes ikke."""
import importlib.machinery
import importlib.util
import json
import pathlib
import subprocess

import pytest

ROT = pathlib.Path(__file__).resolve().parents[1]
SKRIPT = ROT / "scripts" / "avvis-opptak"
_l = importlib.machinery.SourceFileLoader("avvis_opptak", str(SKRIPT))
_s = importlib.util.spec_from_loader("avvis_opptak", _l)
avvis = importlib.util.module_from_spec(_s)
_l.exec_module(avvis)

K = "/hjem/x/dev/norsk-tale/scripts/dikter"
NEKTES = [
    K, K + " --modellvalg large", "./dikter", "cd scripts && ./dikter", "python3 scripts/dikter", "bash scripts/dikter",
    f"bash -c '{K}'", 'sh -c "cd /x && ./dikter"', f"env FOO=1 {K}", f"time {K}", f"nohup {K} &", f"echo hei; {K}",
    f"x | {K}", f"$({K})", f"`{K}`", f"FOO=1 {K}", "~/dev/norsk-tale/scripts/dikter", f"'{K}'", f'"{K}" --malform nn',
    f"exec {K}", f"sudo {K}", f"{K} --maks-s 5", f"{K} --ingen-tale-s 3",
]
SLIPPES = [
    K + " --fil /tmp/a.wav", K + " --fil=/tmp/a.wav --malform nn", K + " --help", K + " -h",
    "cat skills/dikter/SKILL.md", "ls -la scripts; head -60 dikter", "cd scripts && ls", "echo dikter",
    "grep -n dikter README.md", "git log -- scripts/dikter", f"ls {K}", f"cat {K}", f"sed -n 1,80p {K}", "echo hei",
    "python3 -m pytest tests/test_dikter.py", "mkdir dikter", "bash -c 'echo hei'", "ffmpeg -i a.wav b.wav",
]


@pytest.mark.parametrize("kommando", NEKTES)
def test_mikrofonkall_nektes(kommando):
    assert avvis.starter_mikrofonen(kommando), kommando


@pytest.mark.parametrize("kommando", SLIPPES)
def test_filmodus_og_lesing_slippes_gjennom(kommando):
    assert not avvis.starter_mikrofonen(kommando), kommando


def kjor(inn):
    return subprocess.run([str(SKRIPT)], input=inn if isinstance(inn, str) else json.dumps(inn),
                          capture_output=True, text=True, timeout=30)


def test_deny_gis_som_hook_json_med_kode_0():
    r = kjor({"tool_name": "Bash", "tool_input": {"command": K}, "hook_event_name": "PreToolUse"})
    assert r.returncode == 0 and r.stderr == ""
    ut = json.loads(r.stdout)["hookSpecificOutput"]
    assert ut["hookEventName"] == "PreToolUse" and ut["permissionDecision"] == "deny"
    assert "Claude kan ikke starte mikrofonen" in ut["permissionDecisionReason"]


def test_tillatt_kall_gir_ingen_utdata():
    r = kjor({"tool_name": "Bash", "tool_input": {"command": K + " --fil /tmp/a.wav"}})
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_andre_verktoy_og_ugyldig_inndata_roeres_ikke():
    assert kjor({"tool_name": "Read", "tool_input": {"file_path": K}}).stdout == ""
    assert kjor({"tool_name": "Bash"}).stdout == ""
    r = kjor("ikke json")
    assert (r.returncode, r.stdout) == (0, "")


def test_kroken_skriver_og_logger_ingenting():
    kilde = SKRIPT.read_text(encoding="utf-8")
    assert "open(" not in kilde and "write(" not in kilde and "HOOKLOGG" not in kilde
