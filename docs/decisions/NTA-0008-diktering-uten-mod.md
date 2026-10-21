# NTA-0008: Diktering som skill og ett skript, uten mod og MCP-server, med én vanlig hook

*Skrevet 2026-10-21, oppdatert samme dag med målingene i en innlogget økt. Status: implementert i v0.3.0.*

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
brukerens prompt. Ingen mod, ingen MCP-server, ingen bakgrunnsprosess. Den eneste kroken er en
vanlig `PreToolUse`-hook på Bash (`hooks/hooks.json`, `scripts/avvis-opptak`) som nekter
modellen å kjøre `scripts/dikter` uten `--fil`. Den ble lagt til etter målingen under.
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
- **Vernet ble målt, og de to første lagene holdt ikke i auto-modus.** Claude Code 2.1.303,
  innlogget, 21.10.2026, med forespørselen «ta opp lyd fra mikrofonen med norsk-tale-skriptet»:
  uten hook kjørte modellen skriptet via Bash uten tillatelsesforespørsel i **auto-modus**
  (mikrofonen åpen i 10 s, «Allowed by auto mode classifier»), mens **vanlig modus** ba om
  tillatelse (skillen, og så Bash: «This command requires approval»), som ble avvist. Med
  hooken ble modellens kall avvist i begge moduser, før noen forespørsel. Hooken utløses ikke
  av skillens injiserte `!`-kommando (den så bare modellens egne Bash-kall), så brukerens
  `/norsk-tale:dikter` virker i begge moduser, og `transkriber --fil` slipper gjennom.
- **Injeksjonen i auto-modus:** dokumentasjonen (sammendrag) sa at injeksjonen ikke kjører
  ved rendering i auto-modus, men delegeres til modellen. Målt: Claude Code kjørte den selv,
  og skill-teksten kom med transkripsjonen i; modellen gjorde ingen verktøykall først. Det
  gjaldt også etter at hooken var lagt til.
- **Hooken er en fartshump, ikke en garanti.** Den leser teksten i Bash-kommandoen, og
  modellen kan i prinsippet ta opp lyd på andre måter (ffmpeg direkte). Et kall brukeren
  godkjenner selv, er brukerens kall.
- **En bivirkning:** etter en diktering leser modellen noen ganger `skills/dikter/SKILL.md`
  av eget initiativ, noe som ber om tillatelse når pluginen ligger utenfor arbeidsmappen.
- **Tidsgrense:** Bash-verktøyets standard er 2 minutter for hele kommandoen. Målt på M1 Pro
  med large og Metal: 87 s tale tok 16,8 s å laste, verifisere og transkribere, så 90 s
  holder med marginal. Langsommere maskiner kan trenge `medium` eller `small`.
- **Innstillingene:** livetesten i Claude Code 2.1.303 viste at `${user_config.*}` blir
  stående bokstavelig i `!`-kommandoen når innstillingene ikke er lagret, og at
  kommandotolkeren avviser det uten anførselstegn («Parse error»). Verdiene står derfor i
  enkle anførselstegn, og skriptet behandler en uløst plassholder som ikke satt. Med lagrede
  innstillinger ble verdiene byttet ut (en lagret `modellvalg=medium` nådde skriptet).
- **Nett:** pluginen bruker ikke nett. Installasjonen av MCP-SDK-en fra PyPI er borte.
- **Katalogen:** funnene som gjaldt modden og MCP-serveren forsvinner med dem. Hooken kan gi
  et nytt funn («Uses hooks», informasjon). Hva som blir stående, avgjøres av neste skanning.

## Preregistreringen

Kjernen (`kjerne/`) er urørt, og `tests/test_preregistrering.py` er grønn. Fase-1-resultatene
gjelder fortsatt kjernen ved SHA-ene i README. `METHOD.md`, `manifest.json`, `reproduser.py`
og `fase1.py` er ikke endret.
