---
name: transkriber
description: Transkriberer en lokal norsk lydfil (talememo, opptak, .m4a/.wav/.mp3) til tekst med NB-Whisper på denne maskinen. Bruk når brukeren ber om å transkribere, skrive ut eller lese av et norsk lydopptak som ligger på disk.
allowed-tools: mcp__plugin_norsk-tale_norsk-tale__transkriber_fil
---

# Transkriber norsk lydfil lokalt

norsk-tale kjører NB-Whisper med whisper.cpp på denne maskinen, gjennom pluginens
egen lokale MCP-server. Lyden forlater ikke maskinen. Teksten du får tilbake og
viser i samtalen, går til modellen som alt annet i samtalen. Si det til brukeren
hvis opptaket er sensitivt.

## Slik gjør du det

1. Finn den absolutte stien til lydfila. Spør brukeren hvis den ikke er gitt. Ikke
   let i mapper brukeren ikke har pekt på.
2. Kall verktøyet `transkriber_fil` fra norsk-tale-serveren med `sti` (absolutt sti)
   og eventuelt `malform` (`nb`, `nn` eller `auto`; tom bruker pluginens
   innstilling). Modell, whisper-cli og målform er ellers de brukeren har valgt i
   pluginens innstillinger.

   Svaret er ett JSON-objekt: `verbatim` (modellens tekst), `korrigert` (etter
   fasittabellen), `substitusjonslogg`, `modell_sha256` og `versjon`. Hvert kall
   laster modellen på nytt, så det tar noen sekunder før transkripsjonen starter.
3. Vis `korrigert` for brukeren. Står det `⟦feilform → forslag?⟧` i teksten, er det
   en skrivemåte korrektoren ikke har lov til å avgjøre: vis markøren som den er og
   la brukeren velge. Nevn kort hva `substitusjonslogg` endret, hvis noe.

## Når det feiler

- Verktøyet svarer med en feil: vis meldingen ordrett. En melding om SHA256 betyr at
  modellfila ikke stemmer med verdien Hugging Face publiserer.
- Mangler whisper.cpp, ffmpeg eller modellen, be brukeren kjøre `/norsk oppsett`.
  Den viser hva som mangler, og laster ikke ned noe. Ikke last ned modellen eller
  installer noe selv.

De andre verktøyene i norsk-tale-serveren (opptak, status, oppsett, kalibrering) er
ikke for deg. Kall til dem blir avvist: Claude kan aldri starte mikrofonen.

Ikke rett i teksten med egne gjetninger. Transkripsjonen kan inneholde feil, og det
er brukeren som avgjør.
