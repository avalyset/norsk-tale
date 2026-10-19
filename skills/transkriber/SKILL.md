---
name: transkriber
description: Transkriberer en lokal norsk lydfil (talememo, opptak, .m4a/.wav/.mp3) til tekst med NB-Whisper på denne maskinen. Bruk når brukeren ber om å transkribere, skrive ut eller lese av et norsk lydopptak som ligger på disk.
allowed-tools: Bash(python3 -I ${CLAUDE_PLUGIN_ROOT}/kjerne/kjerne.py *)
---

# Transkriber norsk lydfil lokalt

Kjernen i norsk-tale kjører whisper.cpp med NB-Whisper på denne maskinen. Lyden
forlater ikke maskinen. Teksten du får tilbake og viser i samtalen, går til
modellen som alt annet i samtalen. Si det til brukeren hvis opptaket er sensitivt.

## Slik gjør du det

1. Finn den absolutte stien til lydfila. Spør brukeren hvis den ikke er gitt. Ikke
   let i mapper brukeren ikke har pekt på.
2. Kjør kjernen med brukerens valg:

   ```bash
   python3 -I ${CLAUDE_PLUGIN_ROOT}/kjerne/kjerne.py --modellvalg "${user_config.modellvalg}" --modell "${user_config.modell}" --whisper "${user_config.whisper}" "<absolutt sti til lydfila>"
   ```

   Svaret er ett JSON-objekt på stdout:
   `verbatim` (modellens tekst), `korrigert` (etter fasittabellen),
   `substitusjonslogg`, `modell_sha256` og `versjon`. Hvert kall laster modellen
   på nytt, så det tar noen sekunder før transkripsjonen starter.
3. Vis `korrigert` for brukeren. Står det `⟦feilform → forslag?⟧` i teksten, er det
   en skrivemåte korrektoren ikke har lov til å avgjøre: vis markøren som den er og
   la brukeren velge. Nevn kort hva `substitusjonslogg` endret, hvis noe.

## Når det feiler

- Avslutningskode 2 eller 3 med en melding på stderr: vis meldingen ordrett. Kode 3
  betyr at modellfila ikke stemmer med SHA256-en Hugging Face publiserer.
- Mangler whisper.cpp, ffmpeg eller modellen, kjør sjekken og vis `melding`:

  ```bash
  python3 -I ${CLAUDE_PLUGIN_ROOT}/kjerne/kjerne.py --sjekk --modellvalg "${user_config.modellvalg}" --modell "${user_config.modell}" --whisper "${user_config.whisper}"
  ```

  Sjekken laster ikke ned noe. Ikke last ned modellen eller installer noe selv.
  Vis kommandoen sjekken foreslår, og la brukeren bestemme.

Ikke rett i teksten med egne gjetninger. Transkripsjonen kan inneholde feil, og det
er brukeren som avgjør.
