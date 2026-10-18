"""MCP-serveren startes som egen prosess og snakkes med over stdio.

Den tunge testen krever en EKTE norsk lydfil og modellen:
  NORSKRIBER_TESTLYD=/sti/til/opptak.m4a python3 -m pytest mcp/
På macOS kjøres serveren da under et nettverksforbud på OS-nivå (sandbox-exec),
så et nettverksforsøk fra serveren eller dens underprosesser ville feilet testen.
"""
import json, os, pathlib, shutil, subprocess, sys
import pytest

SERVER = pathlib.Path(__file__).resolve().parent / "server.py"
TESTLYD = os.environ.get("NORSKRIBER_TESTLYD")
HJEM = pathlib.Path(os.environ.get("NORSKRIBER_HJEM", "~/norskriber")).expanduser()
NETTFORBUD = (["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]
              if sys.platform == "darwin" and shutil.which("sandbox-exec") else [])


def samtale(meldinger, prefiks=(), timeout=600):
    inn = "".join(json.dumps(m) + "\n" for m in meldinger)
    r = subprocess.run([*prefiks, sys.executable, "-I", str(SERVER)], input=inn,
                       capture_output=True, text=True, timeout=timeout)
    assert r.returncode == 0, r.stderr
    return [json.loads(ln) for ln in r.stdout.splitlines() if ln.strip()]


INIT = [{"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"}]


def test_starter_og_lister_verktoyet():
    svar = samtale(INIT + [{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}])
    assert [s["id"] for s in svar] == [1, 2]
    assert svar[0]["result"]["serverInfo"]["name"] == "norsk-tale"
    verktoy = svar[1]["result"]["tools"]
    assert [v["name"] for v in verktoy] == ["transkriber_fil"]
    assert verktoy[0]["inputSchema"]["required"] == ["sti"]


def test_manglende_fil_er_verktoyfeil_ikke_krasj(tmp_path):
    svar = samtale(INIT + [{"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                            "params": {"name": "transkriber_fil",
                                       "arguments": {"sti": str(tmp_path / "finnes-ikke.wav")}}}])
    r = svar[1]["result"]
    assert r["isError"] is True and "Fant ikke lydfila" in r["content"][0]["text"]


def test_ukjent_metode():
    svar = samtale([{"jsonrpc": "2.0", "id": 9, "method": "resources/list"}])
    assert svar[0]["error"]["code"] == -32601


@pytest.mark.skipif(not (TESTLYD and pathlib.Path(TESTLYD).is_file() and (HJEM / "kjerne.py").is_file()),
                    reason="krever NORSKRIBER_TESTLYD (ekte opptak) og NORSKRIBER-kjernen")
def test_svarer_paa_ekte_norsk_lydfil():
    svar = samtale(INIT + [{"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                            "params": {"name": "transkriber_fil", "arguments": {"sti": TESTLYD}}}],
                   prefiks=NETTFORBUD)
    r = svar[1]["result"]
    assert r["isError"] is False, r["content"][0]["text"]
    ut = r["structuredContent"]
    assert set(ut) == {"verbatim", "korrigert", "substitusjonslogg", "modell_sha256", "versjon"}
    assert ut["verbatim"].strip()
    assert json.loads(r["content"][0]["text"]) == ut
    print("\nMCP verbatim:", ut["verbatim"])
