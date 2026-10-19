#!/usr/bin/env python3
"""norsk-tale — oppstart av den lokale MCP-serveren (stdio).

Claude Code starter denne fila fra .mcp.json med pluginens datamappe
(${CLAUDE_PLUGIN_DATA}). Første gang lages et venv der, og MCP-Python-SDK-en
installeres med låste versjoner og SHA256-hasher fra mcp/krav.txt
(`pip install --require-hashes --only-binary :all:`). Det er den eneste gangen
pluginen bruker nett. Deretter startes serveren direkte fra venvet, uten nett.

stdout er MCP-protokollen: alt fra installasjonen går til stderr. Bare
standardbiblioteket brukes her.
"""
import argparse
import hashlib
import os
import pathlib
import subprocess
import sys
import venv

HER = pathlib.Path(__file__).resolve().parent
KRAV = HER / "krav.txt"
SERVER = HER / "server.py"


def venv_mappe(data):
    """Ett venv per låsefil: ny krav.txt gir et nytt venv, det gamle røres ikke."""
    merke = hashlib.sha256(KRAV.read_bytes()).hexdigest()[:12]
    return pathlib.Path(data) / f"venv-{merke}"


def python_i(mappe):
    return mappe / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def sikre_venv(data):
    mappe = venv_mappe(data)
    ferdig = mappe / ".installert"
    if ferdig.is_file():
        return python_i(mappe)
    print(f"norsk-tale: installerer MCP-SDK-en (låste versjoner) i {mappe} …", file=sys.stderr, flush=True)
    mappe.parent.mkdir(parents=True, exist_ok=True)
    venv.EnvBuilder(with_pip=True, clear=True).create(mappe)
    r = subprocess.run([str(python_i(mappe)), "-m", "pip", "install", "--disable-pip-version-check",
                        "--no-input", "--require-hashes", "--only-binary", ":all:", "-r", str(KRAV)],
                       stdout=sys.stderr, stderr=sys.stderr)
    if r.returncode != 0:
        print("norsk-tale: installasjonen av MCP-SDK-en feilet (se over). Ingenting annet er endret.",
              file=sys.stderr, flush=True)
        sys.exit(r.returncode)
    ferdig.write_text("ok\n", encoding="utf-8")
    return python_i(mappe)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", required=True, help="pluginens datamappe (${CLAUDE_PLUGIN_DATA})")
    a = ap.parse_args(argv)
    if not a.data or "${" in a.data:
        print("norsk-tale: fikk ingen datamappe fra Claude Code (${CLAUDE_PLUGIN_DATA}).", file=sys.stderr)
        return 2
    py = sikre_venv(a.data)
    os.execv(str(py), [str(py), "-I", str(SERVER)])


if __name__ == "__main__":
    sys.exit(main())
