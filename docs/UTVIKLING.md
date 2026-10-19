# Utvikling

Instrukser for den som utvikler og tester norsk-tale. Brukerdokumentasjonen står i [README.md](../README.md).

## Interaktive testøkter og autooppdatering

En interaktiv `claude`-økt kan oppdatere Claude Code i bakgrunnen. Ved
native-installasjon bytter den da `~/.local/bin/claude`, også når økten er startet
fra en annen binær, for eksempel den som følger med Claude-appen. Slik hindrer du
det for en testøkt:

```bash
DISABLE_AUTOUPDATER=1 claude --plugin-dir .
```

- `DISABLE_AUTOUPDATER=1` (eller `DISABLE_UPDATES=1`, som også stopper `claude
  update`) må stå i miljøet til selve `claude`-prosessen.
- `"autoUpdates": false` i Claude Codes globale konfigurasjon **holder ikke** ved
  native-installasjon. Når `autoUpdatesProtectedForNative` er satt, ser
  oppdatereren bort fra den (målt i koden til 2.1.303).
- «Updated to latest. Got …» ved oppstart er utgivelsesnotater. Meldingen vises
  første gang en versjon nyere enn `lastReleaseNotesSeen` i den samme fila
  starter, også når oppdatering er slått av. Den betyr ikke at noe ble lastet ned
  i den økten.
- Sjekk før og etter: `ls ~/.local/share/claude/versions` og
  `readlink ~/.local/bin/claude`.
