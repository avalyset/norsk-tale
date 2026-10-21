# NTA-0008: Diktering som skill og ett skript, uten mod, MCP-server og kroker

*Skrevet 2026-10-21 på grenen `feat/uten-mod`. Status: implementert på grenen, ikke utgitt.*

## Kontekst

- **Katalogens funn for v0.2.2–v0.2.4** gjaldt det modden gjør: den kaller verktøy selv
  (`$.mcp.call`, `MOD_CALLS_TOOLS`), leser promptboksen og tilstand mens den kan sende ut
  (`MOD_SESSION_DATA_LEAVES`, `MOD_LOCAL_DATA_LEAVES`), hooker tillatelsessjekken
  (`MOD_HOOKS_PERMISSION_CHECK`) og kommandoer (`MOD_CAN_FETCH_AND_RUN`). Disse er ikke feil
  i koden: de er selve funksjonen til en mod som styrer en MCP-server. De kan forklares i
  README, men ikke fjernes uten å fjerne modden.
- **Modden var nødvendig av to grunner:** knappen og hurtigtasten, og mikrofonvernet
  (kroker som hindrer modellen i å kalle opptaksverktøyene i MCP-serveren).
- **Dokumentasjonen** (code.claude.com, skills og manifest-referansen) beskriver en annen vei:
  en skill kan kjøre en kommando med `!`…`` før Claude ser innholdet, og
  `disable-model-invocation: true` hindrer Claude i å starte skillen selv.

## Beslutning

Dikteringen er skillen `dikter` (`/norsk-tale:dikter`) som kjører `scripts/dikter`:
ffmpeg tar opp til stillhet (høyst 90 s), én ny `whisper-cli` transkriberer via kjernen
(SHA256 av modellen verifiseres der), og bare transkripsjonen skrives til stdout og blir
brukerens prompt. Ingen mod, ingen MCP-server, ingen kroker, ingen bakgrunnsprosess.
Innstillingene sendes som `${user_config.*}` i kommandoen.

## Alternativer, og hvorfor ikke

- **Beholde modden og forklare funnene i README.** Gjort i v0.2.3 og v0.2.4. Holdene
  består, og et menneske må gå gjennom hver versjon. Valget er ikke feil, bare dyrere.
- **MCP-server uten mod.** Da kan modellen kalle `start_opptak` uten at noe stopper den.
  Vernet krevde kroker, altså en mod.
- **`CLAUDE_PLUGIN_OPTION_<KEY>` i miljøet.** Dokumentasjonen eksporterer dem bare til
  hook-prosesser, ikke til Bash-kommandoer. En fil i `${CLAUDE_PLUGIN_DATA}` ville krevd
  at brukeren skriver den for hånd. `${user_config.*}` i kommandoen er det som virker uten
  oppsett (se konsekvensene).

## Konsekvenser

- **Tapt:** knapp, hurtigtast, Angre, `/norsk selvtest`, og at modellen kan holdes lastet.
  Hver diktering laster modellen på nytt (noen sekunder).
- **Vernet er svakere.** Det hviler på tillatelsessystemet: `disable-model-invocation`,
  og at bare skriptet er forhåndsgodkjent mens skillen kjører. Et menneske som godkjenner
  skriptet selv, eller en modus som godkjenner Bash-kall av seg selv, kan la Claude kjøre
  det. I auto-modus kjører ikke injeksjonen ved rendering; Claude får beskjed om å kjøre
  kommandoen først (dokumentasjonen; ikke testet).
- **Tidsgrense:** Bash-verktøyets standard er 2 minutter for hele kommandoen. Målt på M1 Pro
  med large og Metal: 87 s tale tok 16,8 s å laste, verifisere og transkribere, så 90 s
  holder med marginal. Langsommere maskiner kan trenge `medium` eller `small`.
- **Innstillingene:** livetesten i Claude Code 2.1.303 viste at `${user_config.*}` blir
  stående bokstavelig i `!`-kommandoen når innstillingene ikke er lagret, og at
  kommandotolkeren avviser det uten anførselstegn («Parse error»). Verdiene står derfor i
  enkle anførselstegn, og skriptet behandler en uløst plassholder som ikke satt. Med lagrede
  innstillinger ble verdiene byttet ut (en lagret `modellvalg=medium` nådde skriptet).
- **Nett:** pluginen bruker ikke nett. Installasjonen av MCP-SDK-en fra PyPI er borte.
- **Katalogen:** funnene som gjaldt modden og MCP-serveren forsvinner med dem. Hva som
  blir stående, avgjøres av neste skanning.

## Preregistreringen

Kjernen (`kjerne/`) er urørt, og `tests/test_preregistrering.py` er grønn. Fase-1-resultatene
gjelder fortsatt kjernen ved SHA-ene i README. `METHOD.md`, `manifest.json`, `reproduser.py`
og `fase1.py` er ikke endret.
