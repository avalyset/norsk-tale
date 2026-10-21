---
name: transkriber
description: Transkriberer en lokal norsk lydfil (talememo, opptak, .m4a/.wav/.mp3) til tekst med NB-Whisper på denne maskinen. Bruk når brukeren ber om å transkribere, skrive ut eller lese av et norsk lydopptak som ligger på disk.
allowed-tools: "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dikter --fil *)"
---

# Transkriber norsk lydfil lokalt

norsk-tale kjører NB-Whisper med whisper.cpp på denne maskinen, gjennom skriptet
`scripts/dikter` i testmodus (`--fil`), som aldri åpner mikrofonen. Lyden forlater ikke
maskinen. Teksten du får tilbake og viser i samtalen, går til modellen som alt annet i
samtalen. Si det til brukeren hvis opptaket er sensitivt.

## Slik gjør du det

1. Finn den absolutte stien til lydfila. Spør brukeren hvis den ikke er gitt. Ikke
   let i mapper brukeren ikke har pekt på.
2. Kjør nøyaktig denne kommandoen med Bash-verktøyet, med stien i anførselstegn:

   ```
   ${CLAUDE_PLUGIN_ROOT}/scripts/dikter --fil "<absolutt sti>" --modellvalg "${user_config.modellvalg}" --modell "${user_config.modell}" --whisper "${user_config.whisper}" --malform "${user_config.malform}"
   ```

   Svaret er transkripsjonen (etter fasittabellen) på én linje. Hvert kall laster
   modellen på nytt, så det tar noen sekunder før transkripsjonen kommer.
3. Vis teksten for brukeren. Står det `⟦feilform → forslag?⟧` i den, er det en
   skrivemåte korrektoren ikke har lov til å avgjøre: vis markøren som den er og la
   brukeren velge.

## Når det feiler

- Begynner svaret med `[norsk-tale]`, er det en statusmelding fra skriptet (mangler
  whisper.cpp, ffmpeg eller modellen, SHA256 stemmer ikke, eller lydfila finnes ikke).
  Vis meldingen ordrett. Ikke last ned modellen eller installer noe selv.
- Ikke start opptak fra mikrofonen: skriptet uten `--fil` hører bare til skillen
  `dikter`, som brukeren selv starter.

Ikke rett i teksten med egne gjetninger. Transkripsjonen kan inneholde feil, og det
er brukeren som avgjør.
