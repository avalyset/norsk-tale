# norsk-tale

Lokal norsk tale-til-tekst for Claude Code. Dette repoet er to tynne adaptere
rundt **NORSKRIBER-kjernen** (whisper.cpp + NB-Whisper + fasitkorrektur), som
ligger i sitt eget repo og ikke kopieres hit:

- **Mod for Claude Code** (`hooks/`, `lytter/`): knappen «🎙 Norsk» over prompten og
  `/norsk`. Trykk, snakk norsk, og teksten settes inn ved markøren.
- **MCP-server** (`mcp/`): verktøyet `transkriber_fil(sti)` for agenter og klienter som
  snakker MCP over stdio.

Ingen vekter, ingen lyd og ingen transkripsjoner ligger i repoet.

## Hva «lokalt» betyr, og hva det ikke betyr

**Det betyr:** lyden forlater ikke maskinen. Mikrofonopptaket går fra ffmpeg til en
lytterprosess og videre til whisper.cpp, og alt skjer på din egen maskin. Lyden ligger
bare i en midlertidig katalog og slettes når transkripsjonen er ferdig. Modellfila
sjekkes mot en låst SHA256 før den brukes. Rensingen gjøres av NORSKRIBERs
fasittabell (`korriger.py`), ikke av en språkmodell. Det finnes ingen sky-fallback: når
noe mangler, får du en feilmelding.

**Det betyr ikke** at teksten blir lokal. Teksten havner i promptboksen, og når du
trykker Enter, sendes den til Claude som enhver annen prompt. Den går da til
Anthropics servere, eller til leverandøren økten din bruker. Lokal transkripsjon
beskytter lyden din, ikke det du velger å sende.

**Én lokal port:** modellen holdes lastet i en `whisper-server` som bare er bundet til
`127.0.0.1` på en tilfeldig port. Lytteren snakker med den over loopback, og ingenting
går ut av maskinen. Andre prosesser på samme maskin kan likevel nå porten så lenge
den er oppe. MCP-serveren og NORSKRIBERs filbane bruker ingen sockets i det hele tatt.

## Forutsetninger

- NORSKRIBER på disk (standard `~/norskriber`), med `kjerne.py` og `modell.lock.json`
- whisper.cpp bygget med `whisper-cli` og `whisper-server` (standard `~/whisper.cpp`)
- NB-Whisper large som ggml (`~/whisper.cpp/models/nb-large.bin`). SHA256 må stemme
  med `modell.lock.json`, ellers stopper kjernen.
- ffmpeg og Python 3 på PATH. Python-delen trenger ingen pakker utover standardbiblioteket.

Stiene kan overstyres med `NORSKRIBER_WHISPER_DIR`, `NORSKRIBER_MODELL` og
`NORSKRIBER_UT_KATALOG`, og i modden med valgene `norskriber` og `python`.

## Modden

Last den fra mappa mens den er under utvikling:

```bash
claude --plugin-dir ~/dev/norsk-tale
```

- **Trykk** «🎙 Norsk», eller skriv `/norsk`. Mikrofonen er lukket til du trykker.
  Første trykk laster modellen (noen sekunder), og deretter blir den liggende til
  økten slutter. `/norsk av` laster den ut.
- **Stopp:** trykk igjen. Opptaket stopper også av seg selv etter 1,5 s stillhet etter
  tale, og senest etter 2 minutter. Ledende stillhet skjæres bort, men 0,5 s før
  taleinnsatsen beholdes (pre-roll), så første stavelse ikke klippes.
- **Språket er tvunget til norsk** (`-l no`). Vokabularet (`vokabular/offentlig_no.txt`
  og eventuell `lokal.txt` i NORSKRIBER) går inn som whisper `--prompt`.
- **Innsetting:** `$.prompt.fill` med `mode: 'insert'` setter teksten inn ved markøren.
  Det du har skrevet står urørt på begge sider, og det settes inn mellomrom der det
  trengs. Modden sender aldri inn prompten. Det er alltid du som trykker Enter.
- **Angre:** knappen «Angre» eller `/norsk angre` setter prompten tilbake slik den var
  før dikteringen.
- **Feil:** mangler mikrofontilgang, binær, modell eller kjerne, får du én tydelig
  melding i båndet og som toast.

### Kjent: resident-banen er ikke bitidentisk mellom kall

Dette er målt 18.10.2026. Når samme lyd transkriberes flere ganger i **én** prosess,
gir whisper.cpp ikke alltid samme tekst. I testopptaket ble «gå med bare én dag» til
«gå, men bare en dag» i annet kall. Det kan reproduseres i ren `whisper-cli -f x -f x
-f x`, både på GPU og CPU, med og uten fallback, flash attention og prompt. Variantene
følger kallnummeret, og det peker mot tilstand som overlever mellom kall i libwhisper.
NORSKRIBERs filbane (én prosess per fil, som MCP-serveren bruker) er deterministisk:
tre kjøringer gir null diff. Modden bytter denne garantien mot at modellen holdes
lastet. Teksten havner uansett i promptboksen for gjennomlesing, og den sendes aldri inn
automatisk.

### Avvik: Esc

Bestillingen var at Esc skulle sette prompten tilbake. Det lar seg ikke gjøre i dette
mod-API-et (bygg 2.1.299). En mod leser aldri tastaturet selv, Escape når aldri en
mods tastehendelse, og Esc over tekst i promptboksen tilhører motoren. Angre er derfor
en knapp og en kommando. Den innebygde `/voice` har Esc-avbrudd fordi den er en del av
motoren.

### Flater

| Flate | Status |
|---|---|
| Terminal (`claude`) | Tegnes og testes i `claude plugin test` (surface `terminal`). |
| Claude desktop, Code-fanen | Tegnes og testes i `claude plugin test` (surface `desktop`). Mikrofontilgangen må da gis til Claude-appen. |
| VS Code, mobil | Ikke testet. |
| Windows | **Ikke testet.** Mikrofonen krever `NORSK_TALE_MIKROFON` (dshow-navn). |
| Linux | Ikke testet (PulseAudio via ffmpeg). |

Mikrofontilgang på macOS gis til appen som kjører Claude Code (Terminal, iTerm eller
Claude) under Systeminnstillinger → Personvern og sikkerhet → Mikrofon. Uten tilgang
leverer macOS bare null-signal, og lytteren sier fra etter ett sekund.

## Når innebygd `/voice` er et bedre valg

- Du vil ha **trykk-og-hold** (mellomrom) eller Esc-avbrudd innebygd i promptboksen.
- Du har ikke whisper.cpp, NB-Whisper (~3 GB) og 4 GB ledig minne til modellen.
- Du dikterer på flere språk enn norsk, eller vil ha automatisk innsending.
- Du er logget inn med en claude.ai-konto og har ikke noe imot at lyden strømmes til
  Anthropic. Den innebygde dikteringen sender opptaket til Anthropics servere for
  transkripsjon, behandler ikke lyd lokalt og krever en claude.ai-konto
  (https://code.claude.com/docs/en/voice-dictation).

`norsk-tale` er for deg som vil at lyden blir på maskinen, at det er norsk
NB-Whisper som transkriberer, og at faste skrivemåter for etater og navn rettes av
en sporbar fasittabell.

## MCP-serveren

```bash
claude mcp add norsk-tale -- python3 -I ~/dev/norsk-tale/mcp/server.py
```

Den har ett verktøy, `transkriber_fil`, med argumentet `sti`, og svarer med kjernens
JSON (`verbatim`, `korrigert`, `substitusjonslogg`, `modell_sha256`, `versjon`) som
`structuredContent`. Hvert kall laster modellen på nytt, fordi filbanen ikke holder
noen server oppe. Merk at resultatet går til den som kaller verktøyet. Kaller en
sky-LLM det, forlater teksten maskinen.

## Tester

```bash
claude plugin validate --strict .
claude plugin test .
tsc -p .
python3 -m pytest tests mcp
```

`tsc -p .` trenger typene motoren legger i `.claude-plugin/types/` når modden lastes
med `--plugin-dir`. Før det kan du peke en tsconfig utenfor mappa mot typefila
plugin-authoring-skillen skriver.

`claude plugin test` mocker lytterprosessen, promptboksen og innsending. Python-
testene kjører stillhetsvakten på konstruerte rammer. Tester som krever modellen og
et ekte opptak, hoppes over med begrunnelse til `NORSKRIBER_TESTLYD` peker på en
ekte norsk lydfil. Da kjøres MCP-serveren under et nettverksforbud på OS-nivå, og
hele kjeden (lytter → whisper-server → kjerne) med opptaket spilt i sanntid i stedet
for mikrofonen (`NORSK_TALE_TESTKILDE`).

## Lisens

Koden er under Apache-2.0 (`LICENSE`). Modellen følger ikke med. NB-Whisper large
fra Nasjonalbiblioteket er oppgitt som `license: apache-2.0` på modellkortet
(https://huggingface.co/NbAiLab/nb-whisper-large). Kortet minner også om
attribusjonskravene i åndsverkloven for nedlastinger i Norge. whisper.cpp er
MIT-lisensiert.

Referansearkitekturen var hemanth/voice-mod (MIT). Ingen kode er kopiert derfra.
Den bruker Moonshine og opprydding med Haiku, mens denne bruker NORSKRIBER og ingen
LLM.
