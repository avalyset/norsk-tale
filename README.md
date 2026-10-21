# Norsk tale

Krever Claude Code. Virker ikke i Claude-appene på web, desktop eller mobil.

Lokal norsk diktering i Claude Code. Trykk «🎙 Norsk» over prompten eller skriv
`/norsk`, snakk norsk, og teksten settes inn der markøren står. Transkripsjonen
gjøres av [NB-Whisper](https://huggingface.co/NbAiLab/nb-whisper-large) fra
Nasjonalbiblioteket, kjørt med [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
på din egen maskin. Lyden forlater ikke maskinen.

Oppført på Nasjonalbibliotekets leverandørliste for NB-Whisper: https://github.com/NbAiLab/nostram/blob/main/leverandorer.md

Pluginen har fire deler:

- **Knappen og `/norsk`** (en mod) for diktering inn i promptboksen.
- **Skillen `transkriber`**, som lar Claude transkribere en lydfil du peker på.
- **MCP-serveren** (`mcp/`), en lokal stdio-server bygget med den offisielle
  MCP-Python-SDK-en. Den starter alle lokale programmer. Modden og skillen starter
  ingen prosesser selv ([NTA-0007](docs/decisions/NTA-0007-prosesser-i-lokal-mcp-server.md)).
- **Kjernen** (`kjerne/`): whisper.cpp med språket låst til norsk, et offentlig
  vokabular som whisper-prompt, og en fasittabell som retter kjente feilstavinger av
  etater uten å bruke noen språkmodell.

**Claude kan aldri starte mikrofonen; bare ditt trykk eller din snarvei gjør det.**
**Nett brukes én gang ved installasjon (MCP-SDK), aldri under bruk.**

Versjon 0.2.4 (2026-10-21), arkivert på Zenodo:
[10.5281/zenodo.23473248](https://doi.org/10.5281/zenodo.23473248) (alle versjoner;
v0.2.2 er [10.5281/zenodo.23474643](https://doi.org/10.5281/zenodo.23474643), v0.2.1 er [10.5281/zenodo.23474554](https://doi.org/10.5281/zenodo.23474554), v0.2.0 er
[10.5281/zenodo.23474380](https://doi.org/10.5281/zenodo.23474380), v0.1.1 er
[10.5281/zenodo.23473432](https://doi.org/10.5281/zenodo.23473432) og v0.1.0 er
[10.5281/zenodo.23473249](https://doi.org/10.5281/zenodo.23473249)).
Endringer står i [CHANGELOG.md](CHANGELOG.md), og beslutningene med begrunnelse i
[docs/decisions/](docs/decisions/). Se [CITATION.cff](CITATION.cff) for sitering.

## Krav

- Claude Code v2.1.287 eller nyere (testet med 2.1.303)
- Python 3.10 eller nyere og ffmpeg på PATH
- Nett én gang, første gang pluginen starter. MCP-serveren installerer da
  MCP-Python-SDK-en (mcp 2.3.0 med avhengigheter, låst med SHA256-hasher i
  `mcp/krav.txt`; 28 pakker og ca. 50 MB på macOS med Python 3.14) i pluginens
  datamappe (`${CLAUDE_PLUGIN_DATA}`)
- whisper.cpp med `whisper-cli`. `whisper-server` er valgfri: med den holdes modellen
  lastet mellom opptakene, uten den lastes modellen for hvert opptak
- En NB-Whisper-modell i ggml-format (large, medium eller small)

| Plattform | Status |
|---|---|
| macOS | Utviklet på macOS 27.0.1, Apple M1 Pro, Python 3.14.8, ffmpeg 9.0.1 og whisper.cpp 1.9.2 bygget fra kilde (Metal). Livetest 2026-10-19 i Claude Code 2.1.303, også med MCP-serveren i v0.2.0: en ekte FLEURS-ytring ble spilt gjennom høyttaleren inn i mikrofonen, dikteringen ble startet med snarveien, teksten kom inn riktig, og Angre virket. **Opplesning av et menneske i sanntid er ikke testet automatisk.** |
| whisper.cpp fra Homebrew | Ikke testet. Formelen (1.9.5 da dette ble skrevet) bygger ikke `whisper-server`, så dikteringen bruker `whisper-cli` og laster modellen for hvert opptak |
| Windows, Linux | Ikke testet |

## Installasjon

Ved prompten i en Claude Code-økt i terminalen:

```
/plugin install norsk-tale --marketplace avalyset/norsk-tale
```

Svar `y` for å legge til markedsplassen, og velg deretter omfang.

## Oppsett

Kjør `/norsk oppsett`. Kommandoen sjekker ffmpeg, whisper.cpp og modellen, og sier
hva som mangler. Den laster ikke ned noe.

Første gang Claude Code starter pluginen, lager MCP-serveren et Python-venv i
pluginens datamappe og installerer MCP-SDK-en der med
`pip install --require-hashes --only-binary :all:`. Det tar under et halvt minutt
og er den eneste gangen pluginen bruker nett. Senere starter serveren rett fra
venvet, og blir låsefila endret, lages et nytt venv ved siden av det gamle.

På macOS installerer du verktøyene med:

```bash
brew install whisper-cpp ffmpeg
```

Modellen er NbAiLabs ferdige ggml-fil `ggml-model.bin` fra Hugging Face. Den
konverteres ikke. Hvis fila mangler, viser `/norsk oppsett` størrelsen og en
`curl`-kommando du kan kjøre selv. Hver gang modellen lastes, sjekkes fila mot
SHA256-en Hugging Face publiserer (`kjerne/modeller.json`). Stemmer den ikke,
stopper transkripsjonen.

### Innstillinger

Innstillingene finnes i `/config` under pluginen:

| Valg | Standard | Betydning |
|---|---|---|
| `modellvalg` | `large` | `large`, `medium` eller `small` |
| `malform` | `nb` | Målformen whisper skal skrive: `nb` (bokmål, `-l no`), `nn` (nynorsk, `-l nn`) eller `auto` (whisper velger språk). Se målingen under |
| `modell` | tom | Sti til `ggml-model.bin`. Tom betyr `~/.cache/norsk-tale/nb-whisper-<modellvalg>.bin` |
| `whisper` | tom | Navn eller sti til `whisper-cli`. Tom betyr `whisper-cli` på PATH. En eventuell `whisper-server` letes etter i samme mappe, eller på PATH når bare navnet er gitt |
| `opptak` | tom | Mappe for kalibreringsopptak og selvtest-resultater. Tom betyr `NORSK_TALE_OPPTAK`, ellers `~/norsk-tale-opptak`. Ligger mappa på et eksternt volum (`/Volumes/…`) som ikke er montert, stopper norsk-tale i stedet for å skrive til intern disk. Det samme gjelder modellfila, også via symlenke |

### Modell og opptak på et eksternt volum

Modell, datasett og opptak kan ligge på en ekstern disk, for eksempel
`/Volumes/Ekstern/norsk-tale/`. Pek `modell` og `opptak` (eller `NORSK_TALE_MODELL`
og `NORSK_TALE_OPPTAK`) dit. Er disken ikke montert, får du en tydelig feilmelding,
og ingenting skrives til intern disk i stedet.

`kalibrering/vakt.py` kjører tunge jobber (for eksempel whisper på CPU) med
`nice -n 19`. Den avbryter jobben i tre tilfeller:

- ledig minne faller under 20 %, målt med `memory_pressure -Q` (feltet «free percentage»)
- brukt swap øker mer enn 1 GB fra kjøringen startet
- intern disk har mindre enn 10 GiB ledig

Den sjekker hvert 5. sekund og logger hver sjekk og hvert avbrudd.

### Observert i ett klipp: bokmålstale transkribert med `-l nn`

19.10.2026 ble ett klipp med bokmålstale (45 s) transkribert med `-l nn`, med
medium og large på CPU. whisper.cpp skrev da nynorske former («sjå», «ein»,
«berre», «mogleg», «ikkje»). I samme klipp forsvant én av to nektelser med large:
«Det er ikke sikkert …» med `nb` ble «Det er sikkert …» med `nn`.

Dette er én observasjon i ett klipp, ikke en måling av hvor ofte det skjer.
Standard målform er `nb` ([NTA-0005](docs/decisions/NTA-0005-nb-som-standard.md)).
Målformkrysset er preregistrert i standardkalibreringen, men ligger i fase 2 og
er ikke kjørt.

### Modellvalg og minnebruk

| Modell | Filstørrelse (HF) | Målt toppminne |
|---|---|---|
| large | 3,10 GB | ca. 4,1 GB (`whisper-cli`, 42 s opptak, M1 Pro; `whisper-server` ikke målt separat) |
| medium | 1,53 GB | ikke målt |
| small | 0,49 GB | ikke målt |

Med `whisper-server` lastes modellen ved første trykk og frigjøres etter 10
minutter uten bruk. `/norsk av` frigjør den med en gang. Uten `whisper-server`
lastes modellen for hvert opptak og frigjøres så snart teksten er klar. Large og
medium er målt på FLEURS (se under). Small er ikke målt.

### Mikrofontillatelse

macOS spør om mikrofontilgang for appen som kjører Claude Code: Terminal, iTerm
eller Claude. Har du sagt nei, gir du tilgang under Systeminnstillinger →
Personvern og sikkerhet → Mikrofon, og starter appen på nytt. Gir mikrofonen bare
null-signal i ett sekund, sier norsk-tale fra og ber deg sjekke tilgangen.

## Målt kvalitet: standardkalibrering, fase 1

Standardkalibreringen ble preregistrert før kjøring, på OSF som
[rtbkz](https://osf.io/rtbkz/) med embargo til 2027-04-19, og som git-taggen
`prereg-v1`. Den ble så delt i to faser (`kalibrering/AVVIK.md` nr. 1). Koden som
kjørte og kan gjenskape fase 1, er versjon `v0.1.0` (kommandoen står i AVVIK nr. 2).
Fase 1 er kjørt med kjeden slik den leveres: whisper.cpp med NB-Whisper ggml på Metal, beam
5, én prosess per ytring. Tallene er ordfeilrate (WER) i prosent med 95 %
konfidensintervall, og står i sin helhet i
[`kalibrering/resultater/prereg-v1-fase1.md`](kalibrering/resultater/prereg-v1-fase1.md).

Fase-1-resultatene gjelder kjernen ved disse SHA-ene, uendret i v0.2.0:

- `kjerne/kjerne.py` `962e691c47824a4160bbd8fd208330abac5a7d4fd85ab803bedfaa17fb528a24`
- `kjerne/korriger.py` `335bc6ac2454ee1744556f411c2f7cf6a44fcd02579b07ba9d201e863752cc68`
- `kjerne/vokabular/fasit_offentlig.tsv` `fb61815f42d71323fce6680dec388eccf78de68c5d0062c922c07389e4c63ce6`
- `kjerne/vokabular/offentlig_no.txt` `c6ddfd764ce1b0bb113e94df172e307414990067f3d7f67102ef4236036cb341`

Testen `tests/test_preregistrering.py` feiler hvis noen av dem avviker.

**FLEURS nb_no, test (357 ytringer), målform nb, rå tekst:**

| Modell | Prompt av | Prompt på | NB-Whisper publisert (tabell 5) |
|---|---|---|---|
| medium | 6,76 [5,96–7,60] | 6,53 [5,78–7,35] | 7,2 |
| large | 5,26 [4,64–5,92] | 5,34 [4,72–5,98] | 6,6 |

**NB Tale, modul 1 (480 ytringer fra 72 testtalere i 12 dialektgrupper), large, nb,
prompt på:** 9,37 [8,14–10,74]. Tallene per dialektgruppe står i rapporten.

- **Nektelser:** referansene i FLEURS har 77. Medium mistet 2 i begge
  prompt-cellene, large mistet ingen. I NB Tale ble ingen av 29 nektelser borte.
- **Korrektoren** ga 0 treff i FLEURS og NB Tale, så rå og korrigert tekst er like.
  Fasittabellen retter bare 13 kjente feilformer av navn, og ingen av dem forekom.

**Tallene kan ikke sammenlignes direkte med NB-Whispers publiserte tall:**

- NB kjørte HF transformers/JAX med full presisjon. Her er det whisper.cpp ggml
  med Metal.
- At normaliseringen er den samme (små bokstaver og tegnsetting fjernet,
  NbAiLab/nostram), er sannsynlig, men ikke dokumentert.
- Det er ikke dokumentert hvilket FLEURS-felt NB brukte som fasit. Her brukes
  `raw_transcription`.
- Forskjellene forklares bare som hypoteser, ikke som at den ene kjeden er bedre.

Målformkrysset (nb mot nn) og testsettene NST, NPSC og NB Samtale er fase 2 og ikke
kjørt.

## Bruk

- **Trykk** «🎙 Norsk» eller skriv `/norsk`. Mikrofonen er lukket til du trykker.
  Modellen lastes først når du trykker, og det tar noen sekunder.
- **Tastatur:** `ctrl+x tab` og så `n`. `ctrl+x tab` er Claude Codes egen snarvei
  for å flytte fokus til båndet over prompten. Den virker også når det står tekst i
  promptboksen, og i terminaler som ikke sender museklikk. I båndet trykker `n`
  «🎙 Norsk» (start og stopp), `a` «Angre» og `x` «Avbryt test». Ingen av disse
  bokstavene er bundet i båndet fra før. Esc tar deg tilbake til prompten.
  Snarveien står i knappeteksten.
- **Stopp** med et nytt trykk. Opptaket stopper også av seg selv etter 1,5 sekunder
  stillhet etter tale, og senest etter 2 minutter. 0,5 sekunder før taleinnsatsen
  beholdes, så første stavelse ikke klippes.
- **Teksten** settes inn ved markøren. Det du alt har skrevet står urørt, og
  pluginen sender aldri inn prompten for deg.
- **Angre:** knappen «Angre» (`a` i båndet) eller `/norsk angre` setter prompten
  tilbake slik den var før dikteringen. **Esc virker ikke**, fordi en mod ikke kan se Esc-tasten når
  det står tekst i promptboksen.
- **Skrivemåter** korrektoren ikke har lov til å avgjøre, vises som
  `⟦feilform → forslag?⟧`. Da velger du selv.
- **Skillen:** be Claude om å transkribere en lydfil, for eksempel «transkriber
  ~/Opptak/møte.m4a». Claude bruker da MCP-verktøyet `transkriber_fil`, som kjører
  den samme kjernen. Hvert kall laster modellen på nytt.

## Sjekk at det virker: `/norsk selvtest`

Selvtesten i Claude Code prøver selve veien inn i promptboksen, med én diktering:

1. Tøm promptboksen og skriv `/norsk selvtest`. Testen setter `TEST: ` i boksen.
2. Trykk `ctrl+x tab` og så `n` (eller «🎙 Norsk»), si en kort setning og vent til
   opptaket stopper av seg selv.
3. Trykk `a` (Angre).

Testen sjekker at teksten kom inn etter prefikset, og at Angre gir tilbake
`TEST: `. Så tømmes boksen. Mens testen pågår, sendes ingenting inn. Trykker du
Enter, blir det stoppet. Resultatet vises i panelet «norsk-tale selvtest» og
lagres som `~/norsk-tale-opptak/selvtest-claude-<tidspunkt>.json`, uten lyd.
`x` («Avbryt test») eller `/norsk selvtest avbryt` stopper underveis.

### Seks-setningstesten: fanen «Selvtest» i `/norsk kalibrer`

Den grundige testen ligger i kalibreringsriggen. Start `/norsk kalibrer`, velg
fanen «Selvtest» i nettleseren og trykk «Start selvtest». Du leser seks kjente
setninger med mikrofonen i nettleseren, og den siste er på nynorsk. Hvert opptak
stopper av seg selv etter 1,5 s stillhet etter tale, eller med «Stopp». Det
transkriberes med den samme kjernen som dikteringen, og setning 6 kjøres med
nynorsk. Testen sjekker:

- at nektelser, tall og etatsnavn kom med (tall som sifre eller ord)
- at første ord ikke er klippet bort
- målformen: kom den nynorske setningen ut på bokmål, står det som et funn, ikke
  som en feil

Den måler også tiden fra siste tale til opptaket stoppet (målet er 1,5 s), og fra
stopp til tekst. Lyden lagres ikke: den konverteres i en midlertidig mappe som
slettes. Resultatet lagres som `selvtest-<tidspunkt>.json` i opptaksmappen, som
kan ligge på et eksternt volum (innstillingen `opptak`). Scoringen
(`kalibrering/score.py`) er deterministisk og bruker ingen språkmodell.

## Kalibrer for din stemme: `/norsk kalibrer`

Riggen måler hvor godt dikteringen virker for **én taler med én mikrofon**, altså
deg ved din maskin. Den er et brukerverktøy og ikke en benchmark. Tallene sier noe
om ditt oppsett, ikke om modellen generelt.

`/norsk kalibrer` starter en liten server som bare lytter på `127.0.0.1`, og åpner
den i nettleseren. Adressen har et tilfeldig token og vises bare over prompten.
Serveren stopper når du trykker «Avslutt», eller etter 30 minutter uten bruk.

**Slik går du fram:**

1. Velg modus: fullt manus (100 opptak) eller dialektrunde (20 setninger, 10
   bokmål og 10 nynorsk, med tall, nektelse og etatsnavn i hver).
2. Oppgi dialektregion, dialektkilde og foretrukket målform om du vil. Alle tre er
   valgfrie. Spør ikke etter navn, alder eller annet som identifiserer deg. Velger
   du region, må du også si om dialekten er **morsmålet** ditt eller **imitert**.
   Imitert dialekt holdes alltid adskilt fra morsmål og slås aldri sammen.
3. Kjør mikrofonsjekken. Nivåmåleren skal bevege seg, og testopptaket lagres ikke.
4. Les én setning om gangen. Du kan ta opp, stoppe, spille av, ta om, hoppe over og
   gå fram og tilbake. Går du fra halvveis, fortsetter du der du slapp. Hver runde
   lagres for seg, så du kan ta flere runder, for eksempel med ulike dialekter.
5. Transkriber når maskinen er ledig. Hvert opptak kjøres med og uten
   vokabular-prompt, og vises både rått og etter korrektoren. Nynorske setninger
   kjøres i tillegg med både bokmål og nynorsk som målform, så du ser om en feil
   skyldes målformen eller hørselen.

**Hva den måler:** Riggen regner ut ordfeilrate (WER) og tegnfeilrate (CER) med
samme normalisering som NB-Whisper-prosjektet bruker (`kalibrering/norm.py`): små
bokstaver og tegnsetting fjernet. Den normaliseringen skriver ikke om tall. Når
manuset sier «to tusen» og whisper skriver «2000», blir det to ordfeil. I tillegg
gir riggen en feilanalyse som ikke er en score: om nektelser, tall, etatsnavn og
første ord kom med, og om målformen ble feil. Hver bom vises ordrett, fasit mot
utdata.

Opptak og resultater lagres i `~/norsk-tale-opptak/<runde>/` og kan slettes med
knappen på siden. Den lokale rapporten kan lastes ned som JSON eller HTML. Den
inneholder teksten, men ingen lyd.

## Lukket kalibrering: hva som blir på maskinen, og hva som kan deles

**Blir på maskinen:** Lydopptakene, manus, transkripsjonene og den lokale rapporten
med ordrette bom. Ingenting av dette sendes noe sted.

**Kan eksporteres:** «Eksporter bidrag» lager en JSON-fil med **bare tall**:
WER/CER-tellere (ordfeil og referanseord, tegnfeil og referansetegn), feiltelling
per klasse (nektelse, tall, navn, første ord, målform), antall setninger og talere,
dialektregion, dialektkilde, målform og modell og versjon. Fila inneholder ingen
lyd og ingen tekst, verken manus eller det du sa. Du ser hele innholdet før den
lagres i `~/norsk-tale-opptak/bidrag/`.

**Hvorfor eksporten er anonym:**

- Fila har verken lyd, tekst, navn, alder, tidspunkt eller filstier.
- Stedet er aldri finere enn region. Et eventuelt målepunkt fjernes automatisk når
  færre enn tre talere står bak, før du ser eksporten.
- Tallene beskriver feilrater og kan ikke brukes til å gjenskape hva som ble sagt.

**Slik bidrar du:** Del bidragsfila med prosjektet. `kalibrering/aggreger.py` slår
sammen mange bidrag til tall per klasse, målform og region, med morsmål og imitert
i hver sin kolonne. Den viser antall talere per celle og merker celler med færre
enn tre talere «for få».

## Kjente begrensninger

MCP-serveren er en Python-prosess som kjører hele økten mens pluginen er aktiv.
Modellen lastes likevel først ved første opptak. Første oppstart krever nett for å
installere MCP-SDK-en; uten nett starter serveren ikke første gang. Tar
installasjonen lenger enn Claude Code venter på tilkoblingen (30 s), kobler
serveren til ved neste økt, eller med `/mcp` → norsk-tale → «Reconnect».

Chrome spør om mikrofontilgang hver gang `/norsk kalibrer` startes, fordi riggen
får en tilfeldig port og tillatelsen gjelder per port.

Når samme lyd transkriberes flere ganger mens modellen ligger lastet i
`whisper-server`, kan teksten variere i enkeltord mellom kallene. Det er målt med
NORSKRIBER-kjernen som `kjerne/` er kopiert fra, og kan reproduseres i ren
whisper.cpp. Med samme kjerne ga filbanen (ny prosess per fil, som skillen bruker)
samme tekst i tre kjøringer av samme fil. Se
[NTA-0002](docs/decisions/NTA-0002-filbane-og-resident.md).

## Når innebygd `/voice` er et bedre valg

- Du vil ha trykk-og-hold på mellomromstasten, eller avbrudd med Esc.
- Du dikterer på andre språk enn norsk, eller vil ha automatisk innsending.
- Du trenger ikke velge mellom bokmål og nynorsk. Dokumentasjonen for `/voice`
  lister norsk (`no`) blant de støttede språkene, men ikke `nb` og `nn` hver for seg
  (sjekket 2026-10-19).
- Du har ikke plass til en modell på 0,5–3,1 GB, eller ikke minne til den.
- Du er logget inn med en claude.ai-konto og har ikke noe imot at lyden strømmes til
  Anthropic. Den innebygde dikteringen sender opptaket til Anthropics servere for
  transkripsjon og krever en claude.ai-konto
  ([dokumentasjon](https://code.claude.com/docs/en/voice-dictation)).

## Hva pluginen kjører, skriver og leser

**Programmer:** alle lokale programmer startes av pluginens MCP-server, aldri av
modden eller skillen. Claude Code starter serveren selv fra `.mcp.json` med
`python3 -I <plugin>/mcp/start.py`, og den kjører så lenge pluginen er aktiv i
økten. Serveren starter:

- `pip` én gang, for å installere MCP-SDK-en (se [Krav](#krav))
- lytteren, som tar opp fra mikrofonen med `ffmpeg` og transkriberer med
  `whisper-server` (hvis den finnes) eller `whisper-cli`, når du trykker
- `whisper-cli` for skillens `transkriber_fil`
- kjernens oppsettsjekk for `/norsk oppsett`
- kalibreringsriggen (`kalibrering/rigg.py`) og `open` (macOS) eller `xdg-open`
  (Linux) for `/norsk kalibrer`

**Verktøyene** i serveren:

| Verktøy | Hvem kan kalle det |
|---|---|
| `transkriber_fil` | Claude, for en lydfil du peker på |
| `start_opptak`, `stopp_opptak`, `status`, `frigjor`, `oppsett`, `lagre_selvtest` og `start_kalibrering` | Bare modden |

Modden skjuler de øvrige verktøyene for Claude (`tool.describe`) og avviser alle kall
til dem som ikke kommer fra modden selv (`tool.check` og `tool.call`, etter hvem som
kaller). Hookene matcher bare disse sju verktøynavnene og ser ingen andre verktøy. Claude kan aldri starte mikrofonen; bare ditt trykk eller
din snarvei gjør det.

**Filer pluginen skriver:**

- Selvtestresultatet `selvtest-claude-<tidspunkt>.json` i opptaksmappa. Det er
  MCP-serveren som skriver fila (verktøyet `lagre_selvtest`); modden skriver ingen
  filer.
- MCP-SDK-ens venv i pluginens datamappe.
- Kalibreringsriggens opptak og resultater i opptaksmappa, se `/norsk kalibrer`.

Pluginen skriver ingen bygge-, oppstarts-, innstillings- eller instruksjonsfiler.

**Det modden leser og sender:** Den leser ingen miljøvariabler og ingen filer. Den
leser teksten i promptboksen for å sette inn
dikteringen ved markøren, for Angre og for selvtestens sjekk. Den sender aldri inn
prompten. Den eneste nettverkstrafikken under bruk er loopback (`127.0.0.1`): til
`whisper-server` og mellom nettleseren og riggen. Teksten går til Claude først når
du selv sender prompten.

**Hookene:**

- `prompt.submit` stopper Enter mens selvtesten pågår, så ingenting sendes inn.
  Ellers nullstiller den Angre-tilstanden og sender prompten videre uendret.
- `command.run` svarer på `/norsk`.
- `ui.render` tegner båndet over prompten og selvtestpanelet.
- `session.start` registrerer kommandoen.
- `tool.describe`, `tool.check` og `tool.call` er mikrofonvernet beskrevet over.

## What this plugin does

norsk-tale is local Norwegian speech-to-text for Claude Code. This section says what it
writes, what it sends, what it runs and what its hooks see.

**Nothing leaves your machine.** Audio, transcriptions and test reports stay local.
The only network use is a one-time `pip install` of the MCP SDK from PyPI at first
start, pinned to exact versions with SHA256 hashes (`mcp/krav.txt`, `pip install
--require-hashes --only-binary :all:`). While you use the plugin there are no outgoing
connections; the only connections are loopback (`127.0.0.1`), to a local
`whisper-server` and between your browser and the calibration rig. Dictated text is
put into the prompt box and goes to Claude only when you submit the prompt yourself,
like any other text you type.

**Files it writes**

- `selvtest-claude-<timestamp>.json` in the recordings folder (default
  `~/norsk-tale-opptak`, or the folder set in the plugin settings), after
  `/norsk selvtest`. It holds two pass/fail results and the dictated test sentence, no
  audio. It is written by the plugin's MCP server (tool `lagre_selvtest`,
  `mcp/server.py:134`), not by the mod, which writes no files. The server chooses the
  folder and file name and accepts only a valid timestamp. Nothing reads or runs the
  file.
- The MCP SDK's virtual environment in the plugin's data folder (`CLAUDE_PLUGIN_DATA`).
- Calibration recordings and results in the recordings folder, only if you run
  `/norsk kalibrer`.

It writes no build, start-up, settings or instruction files.

**What it runs, and when.** All local programs are started by the plugin's MCP server
(`mcp/server.py`), never by the mod or the skill:

- `pip`, once, at first start, to install the MCP SDK.
- `ffmpeg` and `whisper-cli` (or `whisper-server` when present) when you press the
  button or the shortcut, to record and transcribe.
- `whisper-cli` when you ask Claude to transcribe an audio file (the skill tool
  `transkriber_fil`).
- The environment check for `/norsk oppsett`, and the calibration rig
  (`kalibrering/rigg.py`) with `open` (macOS) or `xdg-open` (Linux) for
  `/norsk kalibrer`.

The mod itself starts no processes and reads no environment variables. It calls the
plugin's own MCP tools (`hooks/register.tsx:228`-`234`, each tool name written out in
the call): `start_opptak` and `stopp_opptak` when you press the button or shortcut,
`status` while recording, `frigjor` for `/norsk av`, `oppsett` for `/norsk oppsett`,
`lagre_selvtest` at the end of `/norsk selvtest`, and `start_kalibrering` for
`/norsk kalibrer`. It reads the prompt box only to insert the dictated text, to undo it
and to check the self-test, and it never submits the prompt. The MCP server is started
with a filtered environment: only `PATH`, `HOME`, `TMPDIR`, locale variables, what
`xdg-open` and Windows need, and `NORSK_TALE_*` reach it. No credentials are read.

### What the mod sends, and where

The mod makes one kind of outgoing call: `$.mcp.call` to the plugin's own MCP server
(`hooks/register.tsx:228`-`234`; the connection is made at line 212). That server is a
local process Claude Code starts from `.mcp.json`, and the call goes to it over stdio
on the same machine. No network is involved. What each call carries:

| Tool | Arguments sent | When |
|---|---|---|
| `start_opptak` | none | you press the button or shortcut |
| `stopp_opptak` | none | you press it again |
| `status` | the number of the last event seen | every 150 ms while recording |
| `frigjor` | none | `/norsk av` |
| `oppsett` | none | `/norsk oppsett` |
| `lagre_selvtest` | the self-test report (JSON) and a timestamp | the end of `/norsk selvtest` |
| `start_kalibrering` | none | `/norsk kalibrer` |

Before these calls the mod reads two things: the prompt box (`prompt.read`) and its
own saved state (`state.get`). Neither is forwarded, with one exception: the
self-test report holds the text that stood in the prompt box during the test (`TEST: `
and the sentence you dictated for it), because checking that text is the test. Your own
draft is never in it, since `/norsk selvtest` refuses to start unless the box is empty.
No conversation text, earlier prompt or file content is sent anywhere.

### The hooks, one by one

All hooks are registered in `hooks/register.tsx` (listed in `hooks/hooks.json`). Each
heading gives the event and matcher as written in the registration, and the line.

#### `on('session.start')` (line 403)

- Sees: the session-start event; it uses none of its data.
- Decides: nothing. It always passes the event on (`next(e)`).
- Changes: registers the slash command `/norsk` (`$.command.register`, line 404).

#### `on('command.run', { command: 'norsk' })` (line 413)

- Sees: the text typed after `/norsk`. The matcher keeps every other command away.
- Decides: which of the plugin's own actions to run (`angre`, `av`, `oppsett`,
  `selvtest`, `selvtest avbryt`, `kalibrer`, or no argument to start or stop
  dictation), and what text to show you. An unknown argument gets a usage message.
- Changes: nothing outside its own command. It answers with `{ text }`.

#### `on('tool.describe', { tool: VERNEDE })` (line 436)

- Sees: the name and description of the plugin's seven internal tools, when Claude's
  tool list is built. The matcher (`VERNEDE`, line 194) keeps every other tool away.
- Decides: that Claude does not get to see those seven tools.
- Changes: replaces their description with a short stub and marks them deferred.
  Nothing else. Only `transkriber_fil` stays visible to Claude.

#### `on('tool.check', { tool: VERNEDE })` (line 442)

- Sees: the name and input of a call to one of the seven tools, and who makes it
  (`next.origin.plugin`). A call made by the model has the origin `engine`.
- Decides: denies the call unless it comes from this mod. This is a permission
  decision, but only for these seven tools. Everything else passes untouched.
- Changes: nothing. It never rewrites the input.

#### `on('tool.call', { tool: VERNEDE })` (line 447)

- Sees: the same calls as `tool.check`, at the moment they would run.
- Decides: refuses (`{ deny }`) a call that does not come from this mod, as a second
  line of defence behind `tool.check`.
- Changes: nothing.

Together the last three are the microphone guard: Claude can never start a recording;
only your press or shortcut does. The test "mikrofonvern" in `tests/norsk.test.ts`
fails if the guard is removed.

#### `on('prompt.submit')` (line 454)

- Sees: the text about to be submitted and whether it is a command.
- Decides: drops the submission only while the self-test runs, so nothing is sent;
  otherwise it lets the prompt through.
- Changes: clears the mod's own undo state. It never edits the prompt text.

#### `on('ui.render', { component: 'Pane', requestId: PANE })` (line 462)

- Sees: the render request for the plugin's own pane, `norsk-selvtest`, and the mod's
  saved self-test state.
- Decides: what the self-test panel shows.
- Changes: draws only that pane.

#### `on('ui.render', { component: 'AbovePrompt' })` (line 473)

- Sees: the render request for the band above the prompt, and the mod's own state. If
  a survey is showing it passes the request on untouched.
- Decides: what the button row and status line show.
- Changes: adds the row with the Norsk, Angre and Avbryt buttons and a status text.
  It does not touch the prompt or any other part of the interface.

There is no hook on `mcp.call`, on network calls or on process calls.

## Til katalogens vurderere

Svar på funnene fra katalogens automatiske sjekk, med fil og linje i
`hooks/register.tsx` slik de står i denne versjonen.

- **Selvtestrapporten (`hooks/register.tsx:79`, kallet på linje 95):** modden skriver
  ingen filer og bruker ikke `$.fs`. `/norsk selvtest` ber MCP-serveren lagre en
  rapport (verktøyet `lagre_selvtest`, `mcp/server.py:134`). Serveren bestemmer mappe
  og filnavn selv, `selvtest-claude-<tidspunkt>.json` i opptaksmappa, og nekter
  alt som ikke er et gyldig tidsstempel. Rapporten er JSON uten lyd og uten
  transkripsjon. Ingen kode leser eller kjører fila. Det er ingen bygge-,
  oppstarts-, innstillings- eller instruksjonsfil.
- **Verktøykall (`hooks/register.tsx:228`–`234`, tilkoblingen på linje 212):** modden
  kaller bare pluginens egne MCP-verktøy, og hvert verktøynavn står som fast tekst
  ved `$.mcp.call`: `start_opptak`, `stopp_opptak`, `status`, `frigjor`, `oppsett`,
  `lagre_selvtest` og `start_kalibrering`. Det skjer bare når du trykker på
  knappen, bruker snarveien eller skriver `/norsk`. Den sender ingenting ut av
  maskinen. Av samtalen leser den bare promptboksen den skriver dikteringen inn i,
  og den sender aldri inn prompten. Den leser ingen miljøvariabler.
- **Hook på tillatelsessjekken (`hooks/register.tsx:442`):** `tool.check` avviser
  modellens kall til de sju verktøyene over (mikrofonvernet) og gjør ingenting
  annet. Alle andre verktøy går forbi urørt.
- **Hooker verktøykall (`hooks/register.tsx:436`, 442 og 447):** modden lytter på
  `tool.describe`, `tool.check` og `tool.call`, hver med en matcher som bare velger de
  sju verktøynavnene over (`VERNEDE`, linje 194). Hooken på `mcp.call` som sto i
  0.2.2, er fjernet. Modden hooker ingen nettverks- eller programkall.
- **`command.run` (`hooks/register.tsx:413`):** hooken har matcheren `{ command: 'norsk' }` og
  svarer bare på pluginens egen kommando `/norsk` (med argumentene `angre`, `av`,
  `oppsett`, `selvtest` og `kalibrer`). Andre kommandoer ser den ikke.
- **Miljøvariabler til MCP-serveren:** `.mcp.json` sender bare fem verdier, alle fra
  pluginens egne innstillinger: `NORSK_TALE_VALGT_MODELLVALG`, `…_MALFORM`,
  `…_MODELL`, `…_WHISPER` og `…_OPPTAK` (`${user_config.*}`). `mcp/start.py` starter
  serveren med et miljø som bare har `PATH`, `HOME`, `TMPDIR`, språkvariablene, de
  variablene `xdg-open` (Linux) og Windows trenger, og `NORSK_TALE_*`. Alt annet i
  miljøet, også eventuelle nøkler, når aldri serveren, ffmpeg eller whisper.
- **Nett:** bare `pip install` av MCP-SDK-en ved første oppstart, låst til eksakte
  versjoner med SHA256-hasher (`mcp/krav.txt`, `pip install --require-hashes
  --only-binary :all:`). Aldri under bruk.
- **«Download-and-run»:** de tre treffene er dokumentasjon og tekst som vises til
  brukeren, ingenting som kjøres: `README.md` (omtale av `curl`),
  `kjerne/kjerne.py:276` (en kommando `/norsk oppsett` viser, men ikke kjører) og
  `tests/test_rigg.py` (en negativkontroll for nettforbudet, uten nedlasting).
- **Ikon:** ikonet i listingen (feltet `icon` i `plugin.json`) er bare et bilde. Ingen kode kjører det.
- **Legitimasjon:** ingen kode leser innloggingsopplysninger, nøkler eller filer
  med slike, og modden leser ingen miljøvariabler. Serveren leser bare `NORSK_TALE_*`
  og, via operativsystemet, `HOME` og `PATH` for å finne mapper og programmer. Riggen
  lager selv et tilfeldig engangstoken for `127.0.0.1`.

## Personvern

Se [PRIVACY.md](PRIVACY.md). Kort sagt samles ingen data inn, og lyden forlater ikke
maskinen. Claude kan aldri starte mikrofonen; bare ditt trykk eller din snarvei gjør
det. Nett brukes én gang ved installasjon (MCP-SDK), aldri under bruk. De eneste
forbindelsene er loopback (`127.0.0.1`): til en lokal `whisper-server` når den
finnes, og mellom nettleseren og kalibreringsriggen når du bruker `/norsk kalibrer`.
Teksten du sender til Claude, går dit som all annen tekst du sender.

Modden leser ingen miljøvariabler. Av miljøet leser MCP-serveren bare `HOME`, `PATH`
(for å finne programmene) og egne `NORSK_TALE_*`-variabler. Ingenting leser
innloggingsopplysninger.
`huggingface.co` står her bare som kilde og kreditering.

## Utvikling

```bash
claude plugin validate --strict .
claude plugin test .
python3 -m pytest tests
```

Beslutningene står i [docs/decisions/](docs/decisions/) (NTA-0001 til NTA-0007).

Tester som trenger modellen og et ekte opptak, hoppes over med begrunnelse. Da må
opptaket ligge utenfor repoet:

```bash
NORSK_TALE_TESTLYD=/sti/til/opptak.m4a NORSK_TALE_MODELL=/sti/til/ggml-model.bin NORSK_TALE_WHISPER=/sti/til/whisper-cli python3 -m pytest tests
```

Utviklerinstrukser (testøkter, autooppdatering) står i [docs/UTVIKLING.md](docs/UTVIKLING.md).

## Kreditering

- NB-Whisper fra Nasjonalbiblioteket, Apache-2.0. Vektene følger ikke med.
  Kummervold mfl. (2024), «Whispering in Norwegian: Navigating Orthographic and
  Dialectic Challenges», arXiv:2402.01917.
- «FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech»,
  Conneau mfl., 2022, Google, https://huggingface.co/datasets/google/fleurs,
  lisensiert CC-BY-4.0. Bare test-splitten for nb_no er brukt i
  standardkalibreringen. Ingen lyd eller fulltekst er publisert.
- NB Tale, NPSC, NST og NB Samtale fra Språkbanken ved Nasjonalbiblioteket, CC0.
  Datasettene er ikke publisert på nytt.
- whisper.cpp av Georgi Gerganov og bidragsytere, MIT.
- Arkitekturen for modden er inspirert av hemanth/voice-mod (MIT). Ingen kode er
  kopiert derfra.

Se [NOTICE](NOTICE).

## Lisens

Apache-2.0. Se [LICENSE](LICENSE).
