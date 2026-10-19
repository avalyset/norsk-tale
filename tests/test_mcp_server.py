"""MCP-serveren (mcp/server.py) gjennom den offisielle klienten og mcp/start.py.

Krever et venv med MCP-SDK-en, laget av start.py (NORSK_TALE_MCP_DATA peker på
datamappa). Uten det hoppes testene over med begrunnelse; de laster aldri ned noe.
Ingen whisper-kjøring her."""
import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

ROT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROT / "mcp"))
import start  # noqa: E402

DATA = os.environ.get("NORSK_TALE_MCP_DATA", "")
VENV_PY = start.python_i(start.venv_mappe(DATA)) if DATA else None
KLAR = bool(DATA) and VENV_PY.is_file() and (start.venv_mappe(DATA) / ".installert").is_file()
pytestmark = pytest.mark.skipif(not KLAR, reason="krever NORSK_TALE_MCP_DATA med et venv laget av mcp/start.py")
SANDBOX = shutil.which("sandbox-exec") if sys.platform == "darwin" else None
NETTFORBUD = '(version 1)(allow default)(deny network-outbound (remote ip))(deny network-inbound (remote ip))'


def kjor(kall, prefiks=(), env=None):
    server = [*prefiks, sys.executable, "-I", str(ROT / "mcp" / "start.py"), "--data", DATA]
    miljo = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""), **(env or {})}
    spes = {"server": server, "env": miljo, "kall": kall}
    r = subprocess.run([str(VENV_PY), "-I", str(ROT / "tests" / "mcp_klient.py"), json.dumps(spes)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-1500:]
    return json.loads(r.stdout)


def test_serveren_lister_verktoyene_og_svarer():
    ut = kjor([["status", {"etter": 0}], ["sjekk_mappe", {"sti": "/Volumes/norsk-tale-finnes-ikke/x"}]])
    assert ut["verktoy"] == sorted(["transkriber_fil", "start_opptak", "stopp_opptak", "status", "frigjor",
                                    "oppsett", "sjekk_mappe", "start_kalibrering"])
    status = json.loads(ut["svar"][0]["tekst"])
    assert status == {"hendelser": [], "nr": 0, "opptak": False}
    mappe = json.loads(ut["svar"][1]["tekst"])
    assert mappe["ok"] is False and "ikke montert" in mappe["melding"]


def test_oppsett_leser_innstillingene_fra_miljoet(tmp_path):
    ut = kjor([["oppsett", {}]], env={"NORSK_TALE_MODELLVALG": "medium",
                                      "NORSK_TALE_MODELL": str(tmp_path / "mangler.bin"),
                                      "NORSK_TALE_WHISPER": str(tmp_path / "whisper-cli")})
    r = json.loads(ut["svar"][0]["tekst"])
    assert r["ok"] is False and "medium" in r["melding"] and "mangler.bin" in r["melding"]


@pytest.mark.skipif(not SANDBOX, reason="krever sandbox-exec (macOS)")
def test_serveren_virker_under_nettverksforbud():
    """Etter installasjonen bruker serveren ikke nett: oppstart og verktøykall
    under et forbud mot all ekstern nettverkstrafikk på OS-nivå."""
    ut = kjor([["status", {"etter": 0}], ["oppsett", {}]], prefiks=(SANDBOX, "-p", NETTFORBUD))
    assert "transkriber_fil" in ut["verktoy"]
    assert json.loads(ut["svar"][0]["tekst"])["opptak"] is False
    assert "melding" in json.loads(ut["svar"][1]["tekst"])


@pytest.mark.skipif(not SANDBOX, reason="krever sandbox-exec (macOS)")
def test_nettverksforbudet_faktisk_virker():
    """Kontroll av selve forbudet: et utgående kall under samme profil feiler."""
    r = subprocess.run([SANDBOX, "-p", NETTFORBUD, sys.executable, "-I", "-c",
                        "import socket; socket.create_connection(('1.1.1.1', 443), timeout=5)"],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode != 0


def test_valgt_innstilling_slaar_miljoet(tmp_path):
    """Innstillingen fra .mcp.json (NORSK_TALE_VALGT_*) går foran kjernens miljøvariabel."""
    ut = kjor([["oppsett", {}]], env={"NORSK_TALE_MODELLVALG": "large", "NORSK_TALE_VALGT_MODELLVALG": "small",
                                      "NORSK_TALE_VALGT_MODELL": str(tmp_path / "valgt.bin"),
                                      "NORSK_TALE_MODELL": str(tmp_path / "miljo.bin")})
    melding = json.loads(ut["svar"][0]["tekst"])["melding"]
    assert "small" in melding and "valgt.bin" in melding and "miljo.bin" not in melding


def test_mcp_json_sender_innstillingene_til_serveren():
    d = json.loads((ROT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["norsk-tale"]
    assert d["command"] == "python3" and d["args"][:2] == ["-I", "${CLAUDE_PLUGIN_ROOT}/mcp/start.py"]
    assert d["args"][2:] == ["--data", "${CLAUDE_PLUGIN_DATA}"]
    for k in ("modellvalg", "malform", "modell", "whisper", "opptak"):
        assert d["env"][f"NORSK_TALE_VALGT_{k.upper()}"] == "${user_config.%s}" % k
