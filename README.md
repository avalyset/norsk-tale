# Norsk tale

Lokal norsk diktering i Claude Code. Trykk «🎙 Norsk» over prompten eller skriv
`/norsk`, snakk norsk, og teksten settes inn der markøren står. Transkripsjonen
gjøres av [NB-Whisper](https://huggingface.co/NbAiLab/nb-whisper-large) fra
Nasjonalbiblioteket, kjørt med [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
på din egen maskin. Lyden forlater ikke maskinen.

Pluginen har tre deler:

- **Knappen og `/norsk`** (en mod) for diktering inn i promptboksen.
- **Skillen `transkriber`**, som lar Claude transkribere en lydfil du peker på.
- **Kjernen** (`kjerne/`): whisper.cpp med språket låst til norsk, et offentlig
  vokabular som whisper-prompt, og en fasittabell som retter kjente feilstavinger av
  etater uten å bruke noen språkmodell.

## Krav

- Claude Code v2.1.287 eller nyere (testet med 2.1.299)
- Python 3 og ffmpeg på PATH
- whisper.cpp med `whisper-cli`. `whisper-server` er valgfri: med den holdes modellen
  lastet mellom opptakene, uten den lastes modellen for hvert opptak
- En NB-Whisper-modell i ggml-format (large, medium eller small)

| Plattform | Status |
|---|---|
| macOS | Utviklet på macOS 27.0.1, Apple M1 Pro, Python 3.14.8, ffmpeg 9.0.1 og whisper.cpp 1.9.2 bygget fra kilde. Installasjon, `/norsk oppsett` og knappen er prøvd i en ny økt. Transkripsjon er prøvd med opptak spilt av som mikrofon. **Ekte mikrofon er ikke testet ennå.** |
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
| `malform` | `nb` | Målformen whisper skal skrive: `nb` (bokmål, `-l no`), `nn` (nynorsk, `-l nn`) eller `auto` (whisper velger språk). Om `-l nn` faktisk gir nynorsk i whisper.cpp, er ikke målt ennå |
| `modell` | tom | Sti til `ggml-model.bin`. Tom betyr `~/.cache/norsk-tale/nb-whisper-<modellvalg>.bin` |
| `whisper` | tom | Navn eller sti til `whisper-cli`. Tom betyr `whisper-cli` på PATH. En eventuell `whisper-server` letes etter i samme mappe, eller på PATH når bare navnet er gitt |
| `opptak` | tom | Mappe for kalibreringsopptak og selvtest-resultater. Tom betyr `NORSK_TALE_OPPTAK`, ellers `~/norsk-tale-opptak`. Ligger mappa på et eksternt volum (`/Volumes/…`) som ikke er montert, stopper norsk-tale i stedet for å skrive til intern disk. Det samme gjelder modellfila, også via symlenke |

### Modell og opptak på et eksternt volum

Modell, datasett og opptak kan ligge på en ekstern disk, for eksempel
`/Volumes/Vault/norsk-tale/`. Pek `modell` og `opptak` (eller `NORSK_TALE_MODELL`
og `NORSK_TALE_OPPTAK`) dit. Er disken ikke montert, får du en tydelig feilmelding,
og ingenting skrives til intern disk i stedet.

`kalibrering/vakt.py` kjører tunge jobber (for eksempel whisper på CPU) med
`nice -n 19`. Den avbryter jobben når ledig minne faller under 20 %, målt med
`memory_pressure -Q` som norregels minnevakt, eller når intern disk har mindre enn
10 GiB ledig. Den sjekker hvert 5. sekund og logger hver sjekk og hvert avbrudd.

### Modellvalg og minnebruk

| Modell | Filstørrelse (HF) | Målt toppminne |
|---|---|---|
| large | 3,10 GB | ca. 4,1 GB (`whisper-cli`, 42 s talememo, M1 Pro; `whisper-server` ikke målt separat) |
| medium | 1,53 GB | ikke målt |
| small | 0,49 GB | ikke målt |

Med `whisper-server` lastes modellen ved første trykk og frigjøres etter 10
minutter uten bruk. `/norsk av` frigjør den med en gang. Uten `whisper-server`
lastes modellen for hvert opptak og frigjøres så snart teksten er klar. Kvaliteten til medium og small på norsk er ikke
målt i dette prosjektet.

### Mikrofontillatelse

macOS spør om mikrofontilgang for appen som kjører Claude Code: Terminal, iTerm
eller Claude. Har du sagt nei, gir du tilgang under Systeminnstillinger →
Personvern og sikkerhet → Mikrofon, og starter appen på nytt. Gir mikrofonen bare
null-signal i ett sekund, sier norsk-tale fra og ber deg sjekke tilgangen.

## Bruk

- **Trykk** «🎙 Norsk» eller skriv `/norsk`. Mikrofonen er lukket til du trykker.
  Modellen lastes først når du trykker, og det tar noen sekunder.
- **Stopp** med et nytt trykk. Opptaket stopper også av seg selv etter 1,5 sekunder
  stillhet etter tale, og senest etter 2 minutter. 0,5 sekunder før taleinnsatsen
  beholdes, så første stavelse ikke klippes.
- **Teksten** settes inn ved markøren. Det du alt har skrevet står urørt, og
  pluginen sender aldri inn prompten for deg.
- **Angre:** knappen «Angre» eller `/norsk angre` setter prompten tilbake slik den
  var før dikteringen. **Esc virker ikke**, fordi en mod ikke kan se Esc-tasten når
  det står tekst i promptboksen.
- **Skrivemåter** korrektoren ikke har lov til å avgjøre, vises som
  `⟦feilform → forslag?⟧`. Da velger du selv.
- **Skillen:** be Claude om å transkribere en lydfil, for eksempel «transkriber
  ~/Opptak/møte.m4a». Den bruker den samme kjernen. Hvert kall laster modellen på
  nytt.

## Sjekk at det virker: `/norsk selvtest`

Selvtesten prøver hele dikteringsveien på din maskin: samme mikrofon,
stillhetsvakt, modell, korrektor og innsetting som ved vanlig bruk.

1. Tøm promptboksen og skriv `/norsk selvtest`.
2. Over prompten vises én setning om gangen, seks i alt, der den siste er på
   nynorsk. Trykk «🎙 Norsk», les setningen og vent til opptaket stopper av seg
   selv.
3. Til slutt ber testen deg trykke «Angre».

Før hvert opptak setter testen `TEST-N: ` i promptboksen. Etter innsettingen leser
den boksen og sjekker:

- at nektelser, tall og etatsnavn kom med (tall som sifre eller ord)
- at første ord ikke er klippet bort
- at prefikset står urørt foran teksten
- at Angre gir tilbake `TEST-6: `

Den rapporterer også hvor lenge det gikk fra siste tale til opptaket stoppet (målet
er 1,5 s), og fra stopp til tekst i boksen. Kom den nynorske setningen ut på
bokmål, står det som et funn, ikke som en feil.

Mens testen pågår, sendes ingenting inn. Trykker du Enter, blir det stoppet.
Resultatet vises i panelet «norsk-tale selvtest» og lagres som
`~/norsk-tale-opptak/selvtest-<tidspunkt>.json`. Fila inneholder teksten som ble
transkribert, men ingen lyd. «Avbryt test» eller `/norsk selvtest avbryt` stopper
underveis og lagrer det som er gjort. Scoringen (`kalibrering/score.py`) er
deterministisk og bruker ingen språkmodell.

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

### Kjent begrensning

Når samme lyd transkriberes flere ganger mens modellen ligger lastet i
`whisper-server`, kan teksten variere i enkeltord mellom kallene. Det er målt med
NORSKRIBER-kjernen som `kjerne/` er kopiert fra, og kan reproduseres i ren
whisper.cpp. Med samme kjerne ga filbanen (ny prosess per fil, som skillen bruker)
samme tekst i tre kjøringer av samme fil.

## Når innebygd `/voice` er et bedre valg

- Du vil ha trykk-og-hold på mellomromstasten, eller avbrudd med Esc.
- Du dikterer på andre språk enn norsk, eller vil ha automatisk innsending.
- Du har ikke plass til en modell på 0,5–3,1 GB, eller ikke minne til den.
- Du er logget inn med en claude.ai-konto og har ikke noe imot at lyden strømmes til
  Anthropic. Den innebygde dikteringen sender opptaket til Anthropics servere for
  transkripsjon og krever en claude.ai-konto
  ([dokumentasjon](https://code.claude.com/docs/en/voice-dictation)).

## Personvern

Se [PRIVACY.md](PRIVACY.md). Kort sagt samles ingen data inn, lyden forlater ikke
maskinen, og pluginen gjør ingen nettverkskall under transkripsjon. Den eneste
forbindelsen er loopback (`127.0.0.1`) til en lokal `whisper-server`, når den
finnes. Teksten du sender til Claude, går dit som all annen tekst du sender.

## Utvikling

```bash
claude plugin validate --strict .
claude plugin test .
python3 -m pytest tests
```

Tester som trenger modellen og et ekte opptak, hoppes over med begrunnelse. Da må
opptaket ligge utenfor repoet:

```bash
NORSK_TALE_TESTLYD=/sti/til/opptak.m4a NORSK_TALE_MODELL=/sti/til/ggml-model.bin NORSK_TALE_WHISPER=/sti/til/whisper-cli python3 -m pytest tests
```

## Kreditering

- NB-Whisper fra Nasjonalbiblioteket, Apache-2.0. Vektene følger ikke med.
- whisper.cpp av Georgi Gerganov og bidragsytere, MIT.
- Arkitekturen for modden er inspirert av hemanth/voice-mod (MIT). Ingen kode er
  kopiert derfra.

Se [NOTICE](NOTICE).

## Lisens

Apache-2.0. Se [LICENSE](LICENSE).
