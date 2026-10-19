"""Testklient for MCP-serveren, kjøres med venv-Pythonen (som har MCP-SDK-en).

  mcp_klient.py '<json>'   der json = {"server": [argv ...], "env": {...}, "kall": [[verktøy, args], ...]}

Skriver ett JSON-objekt: verktøyene serveren lister, og resultatet av hvert kall.
Bruker den offisielle klienten (mcp.client.stdio), ikke håndskrevet protokoll."""
import json
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(spes):
    params = StdioServerParameters(command=spes["server"][0], args=spes["server"][1:], env=spes.get("env"))
    ut = {"verktoy": [], "svar": []}
    async with stdio_client(params) as (les, skriv):
        async with ClientSession(les, skriv) as s:
            await s.initialize()
            ut["verktoy"] = sorted(t.name for t in (await s.list_tools()).tools)
            for navn, args in spes.get("kall", []):
                r = await s.call_tool(navn, args)
                tekst = "".join(getattr(b, "text", "") for b in r.content)
                ut["svar"].append({"verktoy": navn, "feil": bool(r.is_error), "tekst": tekst})
    print(json.dumps(ut, ensure_ascii=False))


anyio.run(main, json.loads(sys.argv[1]))
