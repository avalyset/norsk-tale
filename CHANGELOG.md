# Endringslogg

Formatet følger [Keep a Changelog](https://keepachangelog.com/no/1.1.0/), og
versjonene følger semantisk versjonering.

## [0.2.0] – 2026-10-19

### Lagt til

- Lokal MCP-server (`mcp/server.py`, stdio), bygget med den offisielle
  MCP-Python-SDK-en og deklarert i `.mcp.json`. Den starter alle lokale programmer:
  lytteren (ffmpeg og whisper), kjernens oppsettsjekk, kalibreringsriggen og
  nettleseren. Verktøyene er `transkriber_fil`, `start_opptak`, `stopp_opptak`,
  `status`, `frigjor`, `oppsett`, `sjekk_mappe` og `start_kalibrering`.
- `mcp/start.py` installerer SDK-en én gang i `${CLAUDE_PLUGIN_DATA}`, med låste
  versjoner og SHA256-hasher (`mcp/krav.txt`, mcp 2.3.0).
- Mikrofonvern: bare `transkriber_fil` er synlig for Claude. Opptaksverktøyene og
  moddens øvrige verktøy skjules (`tool.describe`) og avvises for alle kall som ikke
  kommer fra modden (`tool.check`, `tool.call`, `mcp.call`). Porttesten feiler uten
  vernet.
- `tests/test_preregistrering.py`: feiler hvis kjernen eller de frosne
  kalibreringsfilene avviker fra SHA-ene i preregistreringen.
- Tester for MCP-serveren, blant annet oppstart og verktøykall under
  nettverksforbud.
- ADR NTA-0007.

### Endret

- Modden starter ingen prosesser. Den kaller serveren med `$.mcp.connect` og
  `$.mcp.call`, og kontrollkatalogen med kommandofiler er borte.
- Skillen bruker MCP-verktøyet `transkriber_fil` i stedet for Bash.
- `malform` er fritekst i innstillingene, som `modellvalg`. Innstillingene går til
  serveren fra `.mcp.json`.
- Nett brukes én gang ved installasjon (MCP-SDK), aldri under bruk. README og
  PRIVACY er oppdatert.
- Avsnittet om autooppdatering i testøkter er flyttet til `docs/UTVIKLING.md`.

### Uendret

- Kjernen (`kjerne/kjerne.py`, `kjerne/korriger.py` og vokabularfilene) er
  byte-identisk med prereg-v1. Fase-1-resultatene gjelder fortsatt.

## [0.1.1] – 2026-10-19

### Endret

- Modden ligger nå i én fil (`hooks/register.tsx`), og en parameter er ikke lenger
  kalt `h`. Det er for at katalogens statiske analyse skal kunne følge kallene på
  `$`. Oppførselen er uendret.
- `modellvalg` er fritekst i innstillingene. Ugyldige verdier gir fortsatt en
  tydelig feilmelding fra kjernen.
- README har fått avsnittet «Hva pluginen kjører, skriver og leser».

## [0.1.0] – 2026-10-19

### Lagt til

- Lokal norsk diktering i promptboksen: knappen «🎙 Norsk» og `/norsk`, med NB-Whisper
  og whisper.cpp på egen maskin. Lyden forlater ikke maskinen.
- Tastatursnarvei: `ctrl+x tab` og så `n` (start og stopp), `a` (Angre) og `x`
  (Avbryt test). Virker også med tekst i promptboksen og uten mus.
- Angre-knapp og `/norsk angre`.
- Skillen `transkriber` for lokale lydfiler.
- `/norsk oppsett`: sjekker ffmpeg, whisper.cpp og modellen (SHA256 mot Hugging Face).
  Laster ikke ned noe.
- Målform `nb`, `nn` eller `auto` (whisper `-l no`, `-l nn` eller `auto`).
- `/norsk selvtest`: én diktering som sjekker innsetting etter prefikset og Angre.
- `/norsk kalibrer`: lokal kalibreringsrigg på `127.0.0.1` med token. Fanen
  «Selvtest» har seks kjente setninger med scoring av nektelse, tall, navn, første
  ord og målform, pluss stopp-tider. Bidrag kan eksporteres med bare tall.
- Standardkalibrering preregistrert på OSF (rtbkz, embargo til 2027-04-19). Fase 1
  er kjørt og scoret: `kalibrering/resultater/prereg-v1-fase1.md`.
- ADR-er i `docs/decisions/` (NTA-0001 til NTA-0006) og `CITATION.cff`.

### Endret

- Kjernen er utgått fra NORSKRIBER. Den håndskrevne MCP-serveren fra første utkast
  er erstattet av skillen (NTA-0003).
- Seks-setningstesten er flyttet fra `/norsk selvtest` til riggens fane
  «Selvtest».
- Riggen leser hele POST-kroppen før ruting. Ruter som ikke brukte kroppen, ga
  HTTP 501 på neste forespørsel over samme tilkobling.

### Kjente begrensninger

- Testet bare på macOS (Apple M1 Pro). Ikke testet på Windows eller Linux.
- FLEURS, fase 1: medium mistet 2 av 77 nektelser (begge prompt-cellene). Large
  mistet ingen.
- Korrektoren (fasittabellen) ga 0 treff i FLEURS og NB Tale. Den retter bare 13
  kjente feilformer av navn.
- Med en resident `whisper-server` er gjentatte transkripsjoner av samme lyd ikke
  bitidentiske. Filbanen er deterministisk (NTA-0002).
- Chrome spør om mikrofontilgang hver gang riggen startes, fordi porten er
  tilfeldig og tillatelsen gjelder per port.
- Målformkrysset (nb mot nn) og de øvrige testsettene (NST, NPSC, NB Samtale) er
  fase 2 og ikke kjørt.

[0.2.0]: https://github.com/avalyset/norsk-tale/releases/tag/v0.2.0
[0.1.1]: https://github.com/avalyset/norsk-tale/releases/tag/v0.1.1
[0.1.0]: https://github.com/avalyset/norsk-tale/releases/tag/v0.1.0
