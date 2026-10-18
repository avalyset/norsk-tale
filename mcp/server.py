#!/usr/bin/env python3
"""norsk-tale MCP — lokal stdio-server med ett verktøy:

  transkriber_fil(sti) → NORSKRIBER-kjernens JSON
                         {verbatim, korrigert, substitusjonslogg, modell_sha256, versjon}

Tynn adapter: protokollen er her, transkripsjonen er `kjerne.transkriber`
(filbanen — ingen sockets, modell-SHA verifisert før bruk). Serveren snakker
bare over stdin/stdout og åpner ingen nettverksforbindelse. Ingen avhengigheter
utover standardbiblioteket.

  NORSKRIBER_HJEM   katalogen med kjerne.py (standard ~/norskriber)
"""
import json
import os
import pathlib
import sys

HJEM = pathlib.Path(os.environ.get("NORSKRIBER_HJEM", "~/norskriber")).expanduser()
sys.path.insert(0, str(HJEM))

PROTOKOLLER = ("2025-06-18", "2025-03-26", "2024-11-05")
VERKTOY = {
    "name": "transkriber_fil",
    "title": "Transkriber norsk lydfil lokalt",
    "description": ("Transkriberer én lokal lydfil med NB-Whisper (whisper.cpp) på denne maskinen, "
                    "språk tvunget til norsk, og kjører NORSKRIBERs fasitkorrektur. Lyden forlater "
                    "ikke maskinen. Returnerer verbatim, korrigert, substitusjonslogg, modell_sha256 "
                    "og versjon."),
    "inputSchema": {
        "type": "object",
        "properties": {"sti": {"type": "string", "description": "Absolutt sti til lydfila."}},
        "required": ["sti"],
        "additionalProperties": False,
    },
}


def svar(id_, resultat=None, feil=None):
    melding = {"jsonrpc": "2.0", "id": id_}
    if feil is not None:
        melding["error"] = feil
    else:
        melding["result"] = resultat
    sys.stdout.write(json.dumps(melding, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def kall_verktoy(params):
    if params.get("name") != VERKTOY["name"]:
        return None, {"code": -32602, "message": f"Ukjent verktøy: {params.get('name')!r}"}
    sti = (params.get("arguments") or {}).get("sti")
    if not isinstance(sti, str) or not sti:
        return None, {"code": -32602, "message": "Argumentet «sti» mangler."}
    try:
        import kjerne
    except ImportError as e:
        return _verktoyfeil(f"Fant ikke NORSKRIBER-kjernen i {HJEM} ({e})."), None
    try:
        resultat = kjerne.transkriber(sti)
    except Exception as e:  # KjerneFeil, korriger.Avvisning, ModellAvvik
        return _verktoyfeil(str(e)), None
    return {"content": [{"type": "text", "text": json.dumps(resultat, ensure_ascii=False)}],
            "structuredContent": resultat, "isError": False}, None


def _verktoyfeil(tekst):
    return {"content": [{"type": "text", "text": f"NORSKRIBER: {tekst}"}], "isError": True}


def behandle(m):
    metode, id_, params = m.get("method"), m.get("id"), m.get("params") or {}
    if id_ is None:              # varsler (notifications/initialized m.fl.) får ikke svar
        return
    if metode == "initialize":
        onsket = params.get("protocolVersion")
        svar(id_, {"protocolVersion": onsket if onsket in PROTOKOLLER else PROTOKOLLER[0],
                   "capabilities": {"tools": {}},
                   "serverInfo": {"name": "norsk-tale", "version": "0.1.0"}})
    elif metode == "ping":
        svar(id_, {})
    elif metode == "tools/list":
        svar(id_, {"tools": [VERKTOY]})
    elif metode == "tools/call":
        resultat, feil = kall_verktoy(params)
        svar(id_, resultat, feil)
    else:
        svar(id_, feil={"code": -32601, "message": f"Ukjent metode: {metode}"})


def main():
    for linje in sys.stdin:
        linje = linje.strip()
        if not linje:
            continue
        try:
            m = json.loads(linje)
        except json.JSONDecodeError as e:
            svar(None, feil={"code": -32700, "message": f"Ugyldig JSON: {e}"})
            continue
        behandle(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
