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
import re
import shutil
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
    """Ferdig venv brukes som det er. Ellers installerer denne prosessen i sin egen
    midlertidige mappe og flytter den på plass atomisk.

    Claude Code kan starte serveren på nytt mens første installasjon pågår (en
    treg oppstart får en ny prosess). Da installerer hver prosess for seg, den
    første som blir ferdig vinner, og ingen rydder i en mappe en annen skriver i."""
    mappe = venv_mappe(data)
    if (mappe / ".installert").is_file():
        rydd_etter_avbrutte(mappe)
        return python_i(mappe)
    mappe.parent.mkdir(parents=True, exist_ok=True)
    egen = mappe.with_name(f"{mappe.name}.ny-{os.getpid()}")
    print(f"norsk-tale: installerer MCP-SDK-en (låste versjoner) i {mappe} …", file=sys.stderr, flush=True)
    venv.EnvBuilder(with_pip=True).create(egen)
    r = subprocess.run([str(python_i(egen)), "-m", "pip", "install", "--disable-pip-version-check",
                        "--no-input", "--no-compile", "--require-hashes", "--only-binary", ":all:", "-r", str(KRAV)],
                       stdout=sys.stderr, stderr=sys.stderr)
    if r.returncode != 0:
        shutil.rmtree(egen, ignore_errors=True)
        print("norsk-tale: installasjonen av MCP-SDK-en feilet (se over). Ingenting annet er endret.",
              file=sys.stderr, flush=True)
        sys.exit(r.returncode)
    (egen / ".installert").write_text("ok\n", encoding="utf-8")
    try:
        os.rename(egen, mappe)          # atomisk; feiler hvis mappen alt finnes
    except OSError:
        if (mappe / ".installert").is_file():
            shutil.rmtree(egen, ignore_errors=True)     # en annen prosess kom først
        else:
            # En halvferdig mappe fra et avbrutt eldre oppstartsforsøk: legg den til side.
            os.rename(mappe, mappe.with_name(f"{mappe.name}.forlatt-{os.getpid()}"))
            os.rename(egen, mappe)
    rydd_etter_avbrutte(mappe)
    return python_i(mappe)


def lever(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def rydd_etter_avbrutte(mappe):
    """Fjerner bare egne rester ved siden av et ferdig venv: «<venv>.ny-<pid>» fra
    en prosess som ikke lever lenger, og «<venv>.forlatt-<pid>»."""
    mønster = re.compile(rf"^{re.escape(mappe.name)}\.(ny|forlatt)-(\d+)$")
    for p in mappe.parent.iterdir():
        m = mønster.match(p.name)
        if m and p.is_dir() and (m.group(1) == "forlatt" or not lever(int(m.group(2)))):
            shutil.rmtree(p, ignore_errors=True)


# Miljøet serveren (og ffmpeg/whisper under den) får. Claude Code starter denne fila
# med hele sitt eget miljø; serveren trenger bare dette. Alt annet, også eventuelle
# nøkler i brukerens miljø, blir igjen her.
SLIPPES_GJENNOM = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
                   # Linux: xdg-open for /norsk kalibrer
                   "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR",
                   # Windows
                   "SYSTEMROOT", "PATHEXT", "USERPROFILE", "TEMP", "TMP")


def server_miljo(miljo):
    return {k: v for k, v in miljo.items() if k in SLIPPES_GJENNOM or k.startswith("NORSK_TALE_")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", required=True, help="pluginens datamappe (${CLAUDE_PLUGIN_DATA})")
    a = ap.parse_args(argv)
    if not a.data or "${" in a.data:
        print("norsk-tale: fikk ingen datamappe fra Claude Code (${CLAUDE_PLUGIN_DATA}).", file=sys.stderr)
        return 2
    py = sikre_venv(a.data)
    os.execve(str(py), [str(py), "-I", str(SERVER)], server_miljo(os.environ))


if __name__ == "__main__":
    sys.exit(main())
