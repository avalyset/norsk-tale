# NTA-0003: Skill i stedet for håndskrevet MCP-server

*Skrevet i etterkant, 2026-10-19.*

## Beslutning

Den første versjonen hadde en håndskrevet MCP-server som adapter rundt kjernen
([e73cb3e](https://github.com/avalyset/norsk-tale/commit/e73cb3e)). Den ble erstattet av skillen `transkriber`, som
kaller `kjerne/kjerne.py` direkte via Bash med en avgrenset `allowed-tools`
([d95f193](https://github.com/avalyset/norsk-tale/commit/d95f193)).

## Grunnlag

- Ingen langlivet serverprosess og ingen protokoll å vedlikeholde. Kjernen
  returnerer ett JSON-objekt per fil.
- Samme kjerne brukes av modden, skillen og riggen. Ingenting dupliseres.
- Fra og med d95f193 finnes ingen MCP-server og ingen `.mcp.json` i repoet.

## Kan falsifiseres ved

- at skillen ikke kan transkribere en fil uten noe utover `kjerne.py`
- at repoet inneholder en MCP-server i en versjon etter d95f193
