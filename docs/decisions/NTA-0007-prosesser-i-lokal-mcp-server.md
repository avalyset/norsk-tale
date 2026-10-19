# NTA-0007: All oppstart av lokale programmer i én deklarert lokal MCP-server

*Skrevet før implementeringen, 2026-10-19. Gjelder fra versjon 0.2.0. Status: implementert i v0.2.0.*

## Kontekst

- **Katalogens erklæring 3.** Innsendingen til Anthropics katalog
  (claude.ai/directory/manage, trinn «Samsvar») krever at utgiveren krysser av for
  «The plugin does not exfiltrate credentials or execute code outside its declared
  MCP servers». I v0.1.1 er den erklæringen ikke sann: pluginen har ingen
  MCP-servere, men starter lokale programmer to steder.
- **Prosesskjøringen er spredt i v0.1.1:**
  - Modden (`hooks/register.tsx`) starter lytteren og riggen med
    `$.process.spawn`. Med `$.process.run` kjører den `kjerne.py --sjekk`,
    `kjerne.py --krev-montert` og `open`/`xdg-open`.
  - Lytteren og kjernen starter i sin tur `ffmpeg`, `whisper-cli` og
    `whisper-server`.
  - Skillen `transkriber` kjører `python3 -I ${CLAUDE_PLUGIN_ROOT}/kjerne/kjerne.py`
    via Bash.

## Beslutning

All oppstart av lokale programmer flyttes til én lokal MCP-server over stdio.
- **Server:** serveren deklareres i `.mcp.json` og bygges med den offisielle
  MCP-Python-SDK-en, ikke en håndskrevet protokoll.
- **Avhengigheter:** SDK-en installeres med låste versjoner i
  `${CLAUDE_PLUGIN_DATA}`.
- **Verktøy:** `start_opptak`, `stopp_opptak`, `transkriber_fil` og `status`,
  pluss det som trengs for `/norsk oppsett`, `/norsk av`, `/norsk kalibrer` og
  mappesjekken før lagring.
- **Modden** starter ingen prosesser. Den kaller serveren med `$.mcp.connect` og
  `$.mcp.call`.
- **Skillen** bruker MCP-verktøyet `transkriber_fil` i stedet for Bash.
- **Verktøy som kan åpne mikrofonen eller starte riggen** nektes for modellen i
  modden (`tool.check`). Bare brukerens egne handlinger, via modden, kan starte
  et opptak.

## Alternativer som ble vurdert

1. **Beholde v0.1.1 og spørre directory@anthropic.com hvordan erklæring 3 gjelder
   for en mod og en skill som starter lokale programmer.** Mot: svaret og
   svartiden er ukjent. Inntil svaret kommer, kan erklæringen ikke krysses av
   sannferdig, og innsendingen står stille. Spørsmålet kan stilles uansett, men
   det gjør ikke erklæringen sann.
2. **Ikke søke katalogen**, og bare distribuere via egen markedsplass
   (`/plugin install norsk-tale --marketplace avalyset/norsk-tale`). Mot: brukere
   som leter i katalogen, finner ikke pluginen. Egen markedsplass fungerer allerede
   og blir uansett stående, så katalogen er et tillegg, ikke en erstatning.

## Konsekvenser

- **Ny avhengighet:** MCP-Python-SDK-en med sine avhengigheter, i låste versjoner.
  Den installeres i `${CLAUDE_PLUGIN_DATA}` første gang serveren starter. Det er
  én nedlasting fra PyPI, og deretter ingen nettverkskall. README og PRIVACY må si
  dette. Påstanden i v0.1.x om at pluginen «ikke laster ned noe», gjelder ikke
  lenger uten forbehold.
- **Endret oppstart:** serveren starter med økten når pluginen er aktiv, ikke ved
  første trykk på «🎙 Norsk». Modellen lastes fortsatt først ved første opptak.
- **Endret mekanikk:** lytterens hendelser gikk tidligere som JSON-linjer på
  stdout til modden. Nå går de gjennom verktøykall (`start_opptak`, `status`,
  `stopp_opptak`). Brukeroppførselen skal være lik: knapp og snarvei, innsetting
  ved markøren, Angre.
- **Katalogvurdering:** punktene som holdes for manuell gjennomgang, endres
  sannsynligvis. Moddens egne «starts other programs»-funn bør forsvinne. Nye kan
  komme for pakkeinstallasjonen.

## Forholdet til preregistreringen

- Disse filene skal være byte-identiske med SHA256-ene i
  `kalibrering/manifest.json` (prereg-v1):
  - `kjerne/kjerne.py`
  - `kjerne/korriger.py`
  - `kjerne/vokabular/fasit_offentlig.tsv`
  - `kjerne/vokabular/offentlig_no.txt`
- MCP-serveren pakker inn kjernen og endrer den ikke. En test skal feile hvis noen
  av SHA-ene avviker.
- Fase-1-resultatene gjelder kjernen ved disse SHA-ene, og den er uendret i v0.2.0.
- `METHOD.md`, `manifest.json`, `reproduser.py` og `fase1.py` røres ikke.
- Må kjernen likevel endres, stopper arbeidet før AVVIK nr. 4. README skal da si at
  fase 1 bare gjelder v0.1.x.

## Kan falsifiseres ved

- et `$.process.run` eller `$.process.spawn` i `hooks/register.tsx`, eller et
  Bash-kall i `skills/transkriber/SKILL.md`, i v0.2.0 eller senere
- en SHA256 for de fire kjernefilene som avviker fra `kalibrering/manifest.json`
- at modellen kan starte et opptak uten brukerens trykk

## Lenker

- Erklæringen: trinn 4 i innsendingsskjemaet på claude.ai/directory/manage
  (lest 2026-10-19)
- [NTA-0003](https://github.com/avalyset/norsk-tale/blob/main/docs/decisions/NTA-0003-skill-i-stedet-for-mcp.md):
  NTA-0007 snur delvis NTA-0003. Skillen blir stående, men kaller nå en MCP-server
  i stedet for Bash. MCP-serveren er bygget med SDK-en, ikke håndskrevet.
- Tag [prereg-v1](https://github.com/avalyset/norsk-tale/releases/tag/prereg-v1)
