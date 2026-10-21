# Endringslogg

Formatet følger [Keep a Changelog](https://keepachangelog.com/no/1.1.0/), og
versjonene følger semantisk versjonering.

## [Ikke utgitt] – grenen `feat/uten-mod`

Samme diktering uten mod, uten MCP-server og uten kroker (docs/decisions/NTA-0008).

### Endret

- Dikteringen er skillen `dikter` (`/norsk-tale:dikter`) og skriptet `scripts/dikter`: ffmpeg
  tar opp til stillhet (høyst 90 s, gir opp etter 10 s uten tale), én ny `whisper-cli`
  transkriberer via kjernen med SHA256-sjekk av modellen, og bare transkripsjonen skrives
  til stdout. Skillen har `disable-model-invocation: true`, og bare skriptet er
  forhåndsgodkjent (`allowed-tools`).
- Innstillingene leses som `${user_config.*}` i skillens kommando, i enkle anførselstegn.
  Uløste plassholdere (innstillingene er ikke lagret) teller som ikke satt, så pluginen
  virker uten oppsett. Kjørt i Claude Code 2.1.303: en lagret `modellvalg` nådde skriptet.
- Skillen `transkriber` bruker `scripts/dikter --fil` i stedet for MCP-verktøyet.
- README er skrevet om på engelsk. Den gamle README-en er arkivert i
  `docs/README-0.2-mod-og-mcp.md`. PRIVACY og NOTICE er oppdatert.

### Fjernet

- Modden (`hooks/`), MCP-serveren (`mcp/`, `.mcp.json`), typekontrakten (`types/`,
  `tsconfig.json`) og testene som hørte til dem. Dermed er også installasjonen av
  MCP-SDK-en fra PyPI borte: pluginen bruker ikke nett.
- Knappen, hurtigtasten, Angre og `/norsk selvtest`, som trengte modden.
- Innstillingen `opptak` (bare kalibreringsriggen brukte den, og den startes nå for hånd).

### Lagt til

- `tests/test_dikter.py` (skriptet, opptaksbanen med testkilde, ende-til-ende med modell) og
  `tests/test_skills.py` (skillene, manifestet og «ingen mod»).

Kjernen, preregistreringen og kalibreringen er urørt: `tests/test_preregistrering.py` er grønn.

## [0.2.4] – 2026-10-21

Svar på katalogens funn for 0.2.3. Ingen funksjonsendring: koden i modden og serveren er
uendret.

### Endret

- README har fått én underseksjon per krok i «What this plugin does», med hendelse,
  matcher og linje slik de står i registreringen, og hva kroken ser, bestemmer og endrer.
  Et nytt avsnitt, «What the mod sends, and where», viser hva hvert `$.mcp.call` sender,
  og at det går til pluginens egen lokale MCP-server over stdio.
- README nevner ikke lenger ikonfilen. Katalogen leste henvisningen som et funn
  (`UNREAD_ASSET_REFERENCED`). Ikonet står fortsatt i `plugin.json`.
- Versjonslista i README og `CITATION.cff` har fått versjons-DOI-en for 0.2.3
  (10.5281/zenodo.23526913).

### Lagt til

- `tests/test_katalogregler.py`: README har en underseksjon for hver krok i
  `hooks/register.tsx`, med riktig hendelse og linjenummer, og nevner ikke bildefilen.
  Hver DOI i `CITATION.cff` står også i README-ens versjonsliste.

## [0.2.3] – 2026-10-21

Svar på funnene fra katalogens automatiske sjekk. Ingen funksjonsendring for brukeren:
selvtestrapporten får samme innhold og havner samme sted.

### Endret

- Mikrofonvernets hooks (`tool.describe`, `tool.check`, `tool.call`) har fått en
  matcher som bare velger pluginens sju egne verktøy (`VERNEDE`). Andre verktøy går
  forbi uten å se hookene.
- Hooken på `mcp.call` er fjernet. Modellens kall stoppes av `tool.check` og
  `tool.call`, og porttesten for mikrofonvernet består uendret og feiler fortsatt
  uten vernet. Modden hooker nå ingen nettverks-, MCP- eller programkall.
- `mcp/start.py` starter serveren med et filtrert miljø: bare `PATH`, `HOME`,
  `TMPDIR`, språkvariablene, det `xdg-open` og Windows trenger, og `NORSK_TALE_*`.
  Resten av Claude Codes miljø (også eventuelle nøkler) når ikke serveren, ffmpeg
  eller whisper. `.mcp.json` sender fortsatt bare de fem `NORSK_TALE_VALGT_*`-verdiene
  fra `${user_config.*}`.
- Modden skriver ingen filer og leser ingen miljøvariabler lenger (`$.fs` og `$.env`
  er ute). Selvtestrapporten skrives av MCP-serveren: det nye verktøyet
  `lagre_selvtest` erstatter `sjekk_mappe`. Serveren bestemmer mappe og filnavn og
  nekter alt som ikke er et gyldig tidsstempel, og et umontert eksternt volum stopper
  skrivingen som før.
- Hvert `$.mcp.call` i modden har verktøynavnet som fast tekst (`kall` er en `switch`
  i stedet for en videresending av et variabelt navn).
- README har fått en engelsk seksjon «What this plugin does»: hva modden skriver, sender
  og kjører, og hva mikrofonvernets hooks ser og bestemmer.
- README lenker til Nasjonalbibliotekets leverandørliste for NB-Whisper
  (`NbAiLab/nostram`, `leverandorer.md`), der norsk-tale er oppført.
- README har fått seksjonen «Til katalogens vurderere», som svarer på hvert funn med
  fil og linje.
- `docs/UTVIKLING.md` nevner ikke lenger stien til Claude Codes konfigurasjonsfil,
  og README-avsnittet om legitimasjon er omformulert. Ingen kode leser
  innloggingsopplysninger.

### Lagt til

- `tests/test_katalogregler.py`: modden hooker ingen nett-, MCP- eller programkall,
  verktøyhookene har matcheren, modden bruker ikke `$.fs`/`$.env`, og hvert
  `$.mcp.call` har verktøynavnet som fast tekst.
- `tests/test_mcp_server.py`: `lagre_selvtest` skriver bare riktig navngitt JSON i
  opptaksmappa og avviser ugyldige tidsstempler og ugyldig JSON.
- `tests/test_mcp_start.py`: serveren får bare de tillatte miljøvariablene.

## [0.2.2] – 2026-10-19

### Rettet

- Katalogvalideringen blokkerte 0.2.1 fordi en løkkevariabel i modden het `h`
  (JSX kompileres til `h(...)`). Den har fått et annet navn. Oppførselen er uendret.
- `tests/test_katalogregler.py` fanger det lokalt: ingen `h`/`Fragment` i modden,
  ingen `$.process` i modden og ingen Bash i skillen.

## [0.2.1] – 2026-10-19

### Rettet

- Første oppstart fra en GitHub-installasjon: MCP-serveren koblet ikke til.
  Installasjonen av MCP-SDK-en tok mer enn de 5 s Claude Code venter på et første
  svar, så serveren ble startet på nytt, og den nye prosessen ryddet venvet den
  første skrev i. Nå installerer hver prosess i sin egen midlertidige mappe og
  flytter den atomisk på plass. Den første som blir ferdig vinner, og bare egne
  rester fra prosesser som ikke lever lenger, ryddes. Funnet i installasjonstesten
  av 0.2.0. `tests/test_mcp_start.py` dekker det uten nett.
- `pip install --no-compile` gjør første oppstart raskere.

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

[0.2.4]: https://github.com/avalyset/norsk-tale/releases/tag/v0.2.4
[0.2.3]: https://github.com/avalyset/norsk-tale/releases/tag/v0.2.3
[0.2.2]: https://github.com/avalyset/norsk-tale/releases/tag/v0.2.2
[0.2.1]: https://github.com/avalyset/norsk-tale/releases/tag/v0.2.1
[0.2.0]: https://github.com/avalyset/norsk-tale/releases/tag/v0.2.0
[0.1.1]: https://github.com/avalyset/norsk-tale/releases/tag/v0.1.1
[0.1.0]: https://github.com/avalyset/norsk-tale/releases/tag/v0.1.0
