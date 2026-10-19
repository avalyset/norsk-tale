# Standardkalibrering: metode (prereg-v1)

Status: **FROSSET 19.10.2026 som prereg-v1.** Dokumentet er frosset sammen
med `manifest.json` og `reproduser.py` (SHA256 i `FROZEN.txt`, lokal git-tagg
`prereg-v1`) og preregistreres på OSF med embargo. Ingen standardkjøring starter før
frys og OSF-registrering. Endringer etter frysen føres i `AVVIK.md` med dato og
begrunnelse. Dette dokumentet endres ikke etter frysen.

## 1. Spørsmål

**Q1 – Feilrate i vår kjede.** WER og CER for norsk-tale-kjeden (whisper.cpp
med NB-Whisper ggml, Metal), per sett × modell × målform whisper får ×
tekst (rå/korrigert). For FLEURS kommer i tillegg prompt (på/av). Tallene
stilles ved siden av NB-Whispers publiserte tall (arXiv 2402.01917 v1, tabell
4–7) med forbeholdene i § 9.

Hovedsammenligningen er FLEURS, prompt av, målform nb, rå tekst, mot NBs tall
for samme modellstørrelse (tabell 5): large 6,6 og medium 7,2. Q1 er
beskrivende. Vi tester ingen hypotese om at vi er like gode som eller bedre enn
NB.

**Q2 – Målformkryss og nektelser.** For hvert sett og hver modell: antall
nektelser i referansen, antall tapte og antall tillagte, og tapte og tillagte
per 100 ytringer. Dette telles med whisper satt til `nb` og satt til `nn`
(`feilanalyse.py`, § 5). Q2 er beskrivende. Det er ingen terskler og ingen
signifikanstest, og forskjeller omtales ikke som funn ut over tallene.

## 2. Kjede som måles

Kjeden er det produktet faktisk gjør, `kjerne.transkriber`:

1. ffmpeg konverterer til 16 kHz mono PCM s16le (`kjerne.til_wav`).
2. whisper-cli kjøres én gang per ytring og målform, **én prosess per
   ytring**. Det er målt at gjentatte kall i samme prosess ikke er
   deterministiske (whisper.cpp-oppførsel), så det unngås.
3. `_rens` fjerner whisper-spesialtokener (`<|nocaptions|>` m.fl.). Resultatet
   kalles **rå**.
4. `korriger.py` med fasittabellen `kjerne/vokabular/fasit_offentlig.tsv`
   (deterministisk, ingen LLM). Resultatet kalles **korrigert**.

**Vokabularprompt.** I produktet er `kjerne/vokabular/offentlig_no.txt`
`--prompt`.

- FLEURS kjøres med prompt **på** og **av**. Av betyr ingen `--prompt`, og alt
  annet er likt.
- Alle andre sett kjøres med prompt på.
- NB målte uten prompt. Derfor er prompt av hovedcellen for sammenligningen
  med NB (§ 1).

**Korrektormarkører.** Ved en kollisjon substituerer korrektoren ikke, men
skriver `⟦kildeform → korrekt_form?⟧`. Før «korrigert» scores, erstattes hver
markør med kildeformen, altså det opprinnelige ordet fra whisper. Antall
markører per celle rapporteres for seg.

### Backend: Metal

Produktet bruker Metal (GPU) som standard, og det er Metal som fryses som
backend. `-ng` (bare CPU) gir en annen beregningskjede, så CPU er forkastet som
alternativ (§ 10).

### whisper.cpp

- Kildetre `ggml-org/whisper.cpp`, commit
  `4834a2327d008ace3ec5a9ed00f51454bcabbc1c` (`git describe`:
  `v1.9.2-64-g4834a232`), bygget lokalt med Metal. SHA256 for
  `whisper-cli`-binæren ligger i manifestet.
- Eksakte flagg:
  `-l {no|nn} -m <modell> -f <wav> -otxt -of <ut> -np -bs 5 -bo 5 -tp 0.0 [--prompt <vokabular>]`
  - `NORSK_TALE_WHISPER_ARGS` er tom, så det er ingen `-ng` og ingen `-t`.
  - `-l no` brukes for målform `nb` og `-l nn` for `nn`.
- Standardverdier vi lar stå og fører her: `-t 4`, GPU på, flash attention på,
  temperaturfallback på (`-tpi 0.20`, ikke `-nf`), `-et 2.40`, `-lpt -1.00`, og
  ingen `--suppress-nst`.
- Determinisme sjekkes empirisk på Metal (§ 8). Den er ikke antatt.

### Modeller

| Modell | Fil | Bytes | SHA256 |
|---|---|---|---|
| NB-Whisper medium | `nb-whisper-medium.bin` (ggml, HF `NbAiLab/nb-whisper-medium`) | 1 533 763 076 | `f73141401d203ee77fc7ddf7bf97926a8a85fe85faa6066a6920e4815f48a73d` |
| NB-Whisper large | `nb-whisper-large.bin` (ggml, HF `NbAiLab/nb-whisper-large`) | 3 095 033 483 | `0f2f66f22e11a7c7da3c582d8e5c89cb2c0011753ba9c7c9731e320a4ba33e76` |

Filene på disk er hashet, og hashene stemmer med verdiene Hugging Face
publiserer: LFS oid for `ggml-model.bin`, som er lagret lokalt med nytt navn
(`kjerne/modeller.json`). Rekkefølgen er medium for alle sett først, deretter
large.

### Korrektor og øvrig kode

Korrektoren identifiseres ved git-commiten som fryses (`prereg-v1`) og ved
SHA256 for `kjerne/korriger.py`, `kjerne/kjerne.py`, fasittabellen og
vokabularfila. Alle står i manifestet. ffmpeg-versjonen (9.0.1 på
målemaskinen) logges i miljødumpen.

## 3. Data

Ingen lyd, fasittekst eller transkripsjon fra settene legges i git eller
publiseres. I repoet ligger bare id-lister (`kalibrering/utvalg/<sett>.txt`),
seed og SHA-er. Data ligger på `$NORSK_TALE_DATA`, på målemaskinen
`/Volumes/Vault/norsk-tale/data`. SHA256 for hver arkivfil som brukes, står i
manifestet og sjekkes før hver kjøring.

| Sett | Kilde, versjon | Lisens | Splitt | Fasitfelt | Talens/fasitens målform |
|---|---|---|---|---|---|
| FLEURS nb_no | HF `google/fleurs`, `data/nb_no/test.tsv` + `audio/test.tar.gz` (SHA i manifest) | CC-BY-4.0 | test | `raw_transcription` | bokmål |
| NST | HF `NbAiLab/NST`, config `no-close` (nærmikrofon), splitt `test` (SHA i manifest) | Språkbanken: CC0. HF-kort: apache-2.0. Avviket er notert, og CC0 brukes som kildelisens | test (nor0464) | `text` | bokmål |
| NPSC | HF `NbAiLab/NPSC`, `data/test/` (4 møtedager, 16K mp3 + json) | CC0 | test | `normsentence_text` | per ytring: `sentence_language_code` nb-NO / nn-NO |
| NB Tale | Språkbanken sbr-31, `sennheiser_1.tar.gz` + `Annotation.zip` (`part_1.trans`) | CC0 | modul 1, testtalere (`_x`) | ordkolonnen i `part_1.trans` uten `<…>`-merker | opplest bokmålsmanus, dialektuttale |
| NB Samtale | Språkbanken sbr-85, `nb_samtale.zip` | CC0 | korpusets test-splitt | `transcription` i `metadata.jsonl` | per segment (`orthography` bm/nn) |

Common Voice nn er **ikke** med i prereg-v1. Settet krever en MDC-konto, og
vilkårene er ikke akseptert ennå. Det kan bare legges til senere via
`AVVIK.md`, med samme regler som her.

**NB Tale: 12 dialektgrupper, ikke 24.** NB Tale har 24 grupper i alt.

- Modul 1 er gruppe 1–12: 12 regioner med 20 innlesere hver, jevnt fordelt på
  kjønn og to aldersgrupper.
- Modul 2 er gruppe 13–24. Gruppe 13–23 er andrespråkstalere, og gruppe 24 er
  morsmålstalere uten regioninndeling.
- Kilde: `Dokumentasjon/02_NB_Tale_Innleseroversikt.pdf` (versjon 2015-12-21,
  SHA256 `abd41362543a6631629ecdba10b52da5cd1ace5b4e5d0a2d6d8d5e0340f6de79`),
  og `speakerinfo_part_1.txt`, som har 6 testtalere i hver av g01–g12.
- Vilkårslistens «24» telte alle gruppene. Dialektmålingen bruker de 12
  regionene i modul 1.
- Modul 2 (andrespråk) og modul 3 (spontantale) er ikke med. Q1 og Q2 gjelder
  ikke andrespråkstale.
- Regionnavnene står i en tabell på s. 2 i PDF-en. Den er et bilde og er ikke
  lest ut, så rapporten bruker gruppekodene.

**NPSC: `normsentence_text` er originalspråklig.**

- Datasettkortet (HF `NbAiLab/NPSC`, README ved revisjon
  `e906435cc445e38961d86f3ebf53a7b38603b903`, 2024-08-14, SHA256
  `b6608e866272ddf0a6b09bd224e4367a410953da59ff1d16ff8a13d455e6ffb2`)
  definerer feltene slik:
  - `sentence_text` er den manuelle transkripsjonen.
  - `normsentence_text` er den samme transkripsjonen der tall, datoer og
    vanlige forkortelser er skrevet om automatisk med normaliseringsgrammatikker.
  - `transsentence_text` er en maskinoversatt versjon til den andre målformen.
    Det feltet brukes aldri.
- Kontrollert på test-json:
  - For 770 av 828 nn-NO-ytringer er `normsentence_text` lik `sentence_text`.
    I de 58 andre er alle endrede tokener tall eller forkortelser (inneholder
    siffer, punktum, % eller §).
  - Der `normsentence_text` er lik `transsentence_text` (154), er originalen
    selv lik oversettelsen i 152. Det er setninger som er like i begge
    målformer.

### Referanseforbehandling (før normalisering, fastsatt på forhånd)

- **NPSC:**
  - Merkene `<ee>` og `<mm>` (nøling) fjernes fra fasiten.
  - Ytringer der fasiten inneholder `<qq>` (uoppfattet ord) eller
    `<INAUDIBLE>` utelukkes før utvalget, fordi fasiten er ufullstendig.
  - `normsentence_text` er valgt framfor `sentence_text` fordi den skriver tall
    og forkortelser i skriftform (`18`, `f.o.m.`), slik NB-Whisper gjør. Med
    `sentence_text` (tall i ord) ville tallskrivemåte telle som ordfeil.
    `sentence_text` regnes ikke ut.
- **NB Tale:** fasiten er ordene i fjerde kolonne av `part_1.trans` i
  rekkefølge. Tokener i vinkelparentes (`<start>`, `<end>`, `<sil>`,
  `<inhale>`, `<exhale>`, `<fp>`, `<vowel>`, `<nasal>`) fjernes. Linjer uten
  ord (fonemsegmenter) hoppes over.
- **NST:** manuset har opplest tegnsetting som egne tokener (`\Punktum`,
  `\Komma`, `\Spørsmålstegn`, `\Utropstegn`). De byttes med tegnet (`.`, `,`,
  `?`, `!`), som normaliseringen fjerner. Merker i vinkelparentes fjernes. Den
  offentlige testdelen (HF, no-close) har 75 965 ytringer.
- **NB Samtale** følger korpusets egen notasjon («About the corpus» og
  `backslash_notations.txt`):
  - `uttalenær\ordbokform` erstattes med ordbokformen etter skråstreken. Det
    gjelder også akronymer, for eksempel `N_R_K\NRK` → `NRK`.
  - Lydmerkene `%eee`, `%mmm`, `%emm`, `%heh`, `%qqq`, `%ttt`, `%hhh`,
    `%music` og `%noise` fjernes.
  - Avbrutte ord (tokener som slutter på `£`) fjernes.
  - Segmenter med `%unint`, `%overlapping`, `%unk` eller `%foreign` utelukkes
    før utvalget, fordi fasiten er ufullstendig.
  - Testdelen har 1 195 segmenter. 86 er utelukket for slike merker, og 30 har
    tom fasit etter forbehandlingen.
- **Alle sett:** en ytring hvis fasit er tom etter normalisering (§ 5),
  utelukkes før utvalget.

### Utvalgsregel

Utvalget trekkes blant ytringer som er kvalifisert etter forbehandlingen.
Id-ene sorteres leksikografisk, og `random.Random(seed).sample(...)` trekker.
Resultatet sorteres. Seed er **20261019** for alle sett. Hvis utvalget er
stratifisert, trekkes hvert stratum for seg i sortert stratumrekkefølge med
samme `Random`-instans.

| Sett | Id-format | Regel | n |
|---|---|---|---|
| FLEURS | `file_name` (sentence-id gjentas, filnavnet er unikt) | alle | 357 |
| NST | `<pid>/<file>` | seedet, n = 1 500 | 1 500 |
| NPSC | `path` uten `audio/` | nn-NO: alle kvalifiserte (811). nb-NO: seedet n = 800 av 5 394 kvalifiserte | 1 611 |
| NB Tale | filnavn uten `.wav` (`p1_gNN_…_x-…`) | stratifisert på dialektgruppe g01–g12, seedet 40 per gruppe (av 120) | 480 |
| NB Samtale | `file_name` i `metadata.jsonl` | alle kvalifiserte segmenter i test-splitten (794 bm, 285 nn) | 1 079 |

Id-listene genereres med `reproduser.py utvalg` og legges i repoet før frysen.
Manifestet holder SHA256 for hver liste. Ved hver kjøring regenereres listene
fra data og sammenlignes med de frosne, og avvik stopper kjøringen.

### Tallskrivemåte i fasiten (ingen konvertering)

Tall konverteres ikke i noen retning. Et tall whisper skriver med sifre der
fasiten har ord, eller omvendt, teller som ordfeil. Tabellen dokumenterer
utgangspunktet per sett.

- «Sifre» er antall ytringer i utvalget med minst ett siffer i fasiten.
- «Tallord» er antall ytringer med minst ett ord fra listen `tre fire fem seks
  sju syv åtte elleve tolv tretten fjorten femten seksten sytten søtten atten
  nitten tjue tjuge tyve tretti tredve førti femti seksti sytti åtti nitti
  hundre hundrede tusen million millioner milliard milliarder første tredje
  fjerde femte sjette sjuende åttende niende tiende`, eller et ord som ender
  på `hundre`, `tusen`, `og{tjue|tjuge|tretti|førti|femti|seksti|sytti|åtti|nitti}`
  eller `tende`.
- Tvetydige ord (`en`, `ett`, `ei`, `to`, `ni`, `ti`, `andre`) er utelatt, så
  tallord-kolonnen er et nedre anslag.

| Sett (utvalg) | Fasiten skriver tall med | n | Sifre | Tallord |
|---|---|---|---|---|
| FLEURS | blandet: mest sifre, en del ord | 357 | 83 | 32 |
| NST | bare ord (manuset) | 1 500 | 0 | 221 |
| NPSC nb-NO | sifre for tall, datoer og forkortelser (normaliseringsgrammatikk), ord der grammatikken ikke slo til | 800 | 73 | 50 |
| NPSC nn-NO | som over | 811 | 46 | 25 |
| NB Tale | bare ord (manuset) | 480 | 0 | 60 |
| NB Samtale | bare ord (korpusdokumentet: «All numbers are written out with letters») | 1 079 | 0 | 90 |

Tallene over er regnet med regelen i dette avsnittet på id-listene som
`reproduser.py` har generert.

## 4. Kontaminering

Detaljer og kilder står i `kontaminering.md`. Kort sagt: ingen av testsplittene
er dokumentert brukt i gradienttrening av NB-Whisper. Merknadene som følger
tallene i rapporten:

- **FLEURS:** valideringssplitten ble brukt til modellvalg. Testen er holdt
  utenfor.
- **NST:** linje 1501–3000 av NBs interne testfil påvirket modellvalget. Vårt
  utvalg fra den offentlige testen kan overlappe dem, så tallet markeres som
  «mulig optimistisk».
- **NPSC:** testmøtene er holdt utenfor ifølge SSC (sbr-91). Det kan ikke
  verifiseres i det private `ncc_speech`.
- **NB Tale:** status ukjent, trolig ikke brukt.
- **NB Samtale:**
  - Status ukjent, trolig ikke brukt.
  - Testen er ikke delt på taler, så tallet markeres som «mulig optimistisk»
    ved sammenligning med modeller trent på korpuset.
  - **Fasiten er laget ved å rette maskintranskripsjon fra NBs AI-lab**
    (korpusdokumentet: «transcribed automatically using a Norwegian ASR system
    created by the AI-lab at the National Library of Norway», deretter rettet
    manuelt og kontrollest). Det kan gi forankring til NB-modellens
    formuleringer, så tallet markeres som «mulig optimistisk for NB-modeller».
- **Alle sett:** grunnmodellen OpenAI Whisper har ukjente treningsdata.

## 5. Normalisering og mål

- **Normalisering:** NbAiLab/nostram `utils/evaluate.py`, funksjonen
  `normalizer` med standardvalg (`extra_clean=False`, `super_normalize=False`),
  ved commit `448238e9c8d87c7ce1a9d1db24612bed31b6f320` (04.02.2024):
  jiwer `ToLowerCase → RemoveMultipleSpaces → Strip → RemovePunctuation →
  RemoveWhiteSpace(replace_by_space=True)`. Ved `7adfc16a` (HEAD 28.09.2026) er
  transformkjeden identisk med disse valgene.
  - Implementasjonen er `kalibrering/norm.py`, en ren standardbibliotek-port.
  - NB-Whispers eget `eval.py` (NbAiLab/nb-whisper) har ingen normalisering.
    At nostram-fila ga papirets tall, er sannsynlig, men ikke dokumentert.
  - jiwer 4.0.0 brukes bare som kryssjekk (`kryssjekk_jiwer.py`, eget venv) og
    aldri til rapporterte tall.
- **WER:** ord-Levenshtein (S+D+I) summert over ytringene, delt på summen av
  referanseord (korpus-WER). Den beregnes ikke som snitt av ytrings-WER. Tom
  hypotese er gyldig og gir bare slettinger.
- **CER:** det samme på tegnnivå etter normalisering. Mellomrom teller som tegn
  (jiwer `cer`-standard).
- **95 % KI:** prosentil-bootstrap over ytringer, B = 2 000.
  - Indeksene trekkes med `random.Random(f"20261019/{sett}")`, én gang per
    sett, og de samme trekningene brukes for alle celler i settet (paret).
  - Hver trekning gir korpus-WER/CER = Σfeil / Σreferanselengde.
  - Grensene er de sorterte verdiene med indeks 50 og 1 949 (0-basert).
- **Q2, nektelser:** `feilanalyse.py` på normalisert tekst (§ 5,
  normalisering).
  - Hvert ord i ytringen slås opp i denne listen. Formene til venstre telles
    som typen til høyre. Ingen andre former telles, heller ikke dialektformer
    (f.eks. `ikkj`, `itj`, `ente`), `ingi`, `kje` eller sammensetninger.

    | Form i tekst | Type |
    |---|---|
    | `ikke`, `ikkje` | ikke |
    | `aldri` | aldri |
    | `ingen`, `inga`, `intet` | ingen |
    | `ingenting` | ingenting |
    | `verken`, `korkje` | verken |
    | `nei` | nei |

  - «eller» i verken–eller telles ikke for seg.
  - Tellemetode: for hver ytring og hver type *t* teller vi forekomster i
    referansen, ref_t, og i hypotesen, hyp_t. Da er tapt_t = max(0, ref_t −
    hyp_t) og lagt_til_t = max(0, hyp_t − ref_t). Disse summeres over typer og
    over ytringer.
  - Telling per type gjør at en ombytting (f.eks. `ikke` → `aldri`) gir én
    tapt og én lagt til. Den nuller seg ikke ut.
  - Vi rapporterer per celle: referansens nektelser, tapt, lagt til, andel tapt
    (tapt / referansens nektelser), og tapt og lagt til per 100 ytringer. Det
    er ingen KI og ingen test.
  - Korrigert tekst telles etter at markørene er erstattet (§ 2).
- **Korrektormarkører:** antall `⟦…?⟧` per celle (bare korrigert tekst)
  rapporteres for seg.
- **Kjøretid:** veggklokke per ytring logges og rapporteres som median og sum,
  bare beskrivende. Den påvirkes av samtidige jobber og er ikke et kvalitetsmål.

## 6. Celler

| Sett | Modell | Målform til whisper | Prompt | Tekst |
|---|---|---|---|---|
| FLEURS | medium, large | nb, nn | på, av | rå, korrigert |
| NST, NPSC (nb-NO og nn-NO som to delsett), NB Tale, NB Samtale | medium, large | nb, nn | på | rå, korrigert |

Kjøringen med fasitens målform er hovedcellen. Den andre målformen er krysset.
WER i krysset regnes mot den samme fasiten, så målformavvik viser seg som feil.

- **NB Samtale:** fasitens målform er segmentets `orthography`.
- **NB Tale:** rapporteres i tillegg per dialektgruppe (n = 40 per gruppe, med
  6 talere). Gruppetall er beskrivende, og KI-ene blir brede.
- **Antall whisper-kjøringer per modell:** 357·2·2 + 1 500·2 + 1 611·2 +
  480·2 + 1 079·2 = 10 768, altså 21 536 for begge modellene.

## 7. Utelukkelser (fastsatt på forhånd)

| Grunn | Når | Behandling |
|---|---|---|
| Tom fasit etter forbehandling og normalisering | før utvalget | telles per sett og rapporteres. Ytringen inngår ikke i trekningen |
| `<qq>`/`<INAUDIBLE>` i fasiten (NPSC) | før utvalget | som over |
| Lyd mangler i arkivet | ved kjøring | ytringen utelukkes i alle celler for settet, og antallet rapporteres |
| Dekoderfeil (whisper-cli eller ffmpeg avslutter med kode ≠ 0) | ved kjøring | registreres med kode. Én gjentatt kjøring ved feil, ikke flere |
| Tidsgrense: mer enn 600 s veggklokke for én whisper-prosess | ved kjøring | prosessen avbrytes og ytringen registreres som tidsavbrudd |
| Kjøring avbrutt av ressursvakten | ved kjøring | ikke en utelukkelse. Kjøringen gjenopptas der den stoppet |

Ytringer med dekoderfeil eller tidsavbrudd utelukkes, og analysesettet for et
sett er bare ytringene med gyldig resultat **i alle celler** (komplette
tilfeller). Dermed er cellene parede. Antall utelukket per grunn og celle
rapporteres alltid sammen med n. Hvis mer enn 2 % av utvalget i et sett
utelukkes ved kjøring, står det i rapporten. Det endrer ikke metoden.

## 8. Reproduserbarhet

- `kalibrering/manifest.json` holder versjoner, SHA256 for modeller,
  whisper-cli, dataarkiver, id-lister og kode, samt seed, flagg og stier. Stier
  oppgis bare som miljøvariabler: `NORSK_TALE_DATA`, `NORSK_TALE_MODELLER`,
  `NORSK_TALE_ARBEID` og `NORSK_TALE_WHISPER_CLI`.
- `kalibrering/reproduser.py` er det eneste inngangspunktet:
  - Det leser manifestet og verifiserer alle SHA-er. Ved avvik stopper det med
    kode ≠ 0 og navngir fila.
  - Det regenererer og sammenligner id-listene, kjører (gjenopptakbart),
    scorer og skriver resultater og en miljødump (OS, CPU og GPU, Python og
    pakker, whisper-cli-versjon, ffmpeg-versjon).
  - Resultatfilene med transkripsjoner ligger under `$NORSK_TALE_ARBEID` og
    committes aldri. Bare den rene tallrapporten kan legges i repoet.
- **Determinismetest før frys, på Metal:**
  - 5 FLEURS-ytringer (de 5 første id-ene i `utvalg/fleurs.txt`), medium, nb,
    prompt på, kjøres to ganger i hver sin prosess per ytring.
  - Rå og korrigert tekst må være byte-identiske.
  - Resultatet føres i `FROZEN.txt`. Bare SHA256 av utdata føres, ikke
    teksten.
  - Er utdata ikke identiske, stopper frysen, og funnet legges fram før noe
    endres.

## 9. Sammenligning med publiserte tall

NB-Whispers tall er hentet fra arXiv 2402.01917 v1:

| Modell | FLEURS (tabell 5) | NST (tabell 6) | CV nynorsk (tabell 7) |
|---|---|---|---|
| large | 6,6 | 2,2 | 12,6 |
| medium | 7,2 | 2,3 | 17,0 |

**FLEURS er hovedankeret**, sammenlignet med cellen prompt av, nb, rå. Ingen
av våre tall er direkte sammenlignbare, fordi:

- NB kjørte HF transformers/JAX med full presisjon på GPU/TPU. Vi kjører
  whisper.cpp ggml med Metal.
- Vi bruker vokabularprompt i alle sett unntatt FLEURS-hovedcellen. Det gjorde
  ikke NB.
- Normaliseringen er sannsynligvis, men ikke dokumentert, den samme.
- Hvilket FLEURS-felt NB brukte som fasit, er ikke dokumentert. Vi bruker
  `raw_transcription`.
- **NST:** «Ikke direkte sammenlignbart med NB-Whispers publiserte 2,2 %: NB
  brukte de første 1 500 linjene av en intern, renset fil med ukjent
  rekkefølge, som ikke kan gjenskapes. Vårt tall gjelder et seedet utvalg fra
  den offentlige testdelen.»

Avvik fra de publiserte tallene forklares bare som hypoteser.

**Kreditering:** «FLEURS: Few-shot Learning Evaluation of Universal
Representations of Speech», Conneau mfl., 2022, Google,
https://huggingface.co/datasets/google/fleurs, lisensiert CC-BY-4.0. Bare
test-splitten for nb_no er brukt. NST, NPSC, NB Tale og NB Samtale:
Språkbanken ved Nasjonalbiblioteket, CC0.

## 10. Kjøreforhold

Kjøreforholdene påvirker tid, ikke resultat:

- **Backend:** Metal (produktets standard), `-t 4` (standard), én
  whisper-prosess om gangen, serielt, under `nice -n 19`.
- **Oppstart** skjer umiddelbart etter frys (`prereg-v1`) og innsendt
  OSF-preregistrering. Norregels lokale Ollama-fase er avsluttet.
- **Hele kjøringen går under `vakt.py`.** Den avbryter (og kjøringen kan
  gjenopptas) når noe av dette inntreffer:
  - mindre enn 20 % ledig minne (`memory_pressure` «free percentage»)
  - swap økt med mer enn 1 GB fra start
  - mindre enn 10 GiB ledig på intern disk
- Før start og hver 25. ytring: `ollama ps` skal være tom, og ingen
  `inspect eval --model ollama/` skal leve. Hvis ikke, stopper kjøringen rolig
  og gjenopptas når det er ledig igjen. Slik håndteres det om norregel starter
  en lokal fase igjen.
- Data, modeller og resultater ligger på Vault. Hvis Vault ikke er montert,
  stopper kjøringen, og den faller aldri tilbake på intern disk.
- Målemaskin: Apple M1 Pro, 16 GB. Hele miljødumpen følger resultatene.

**Estimert kjøretid** for hele cellematrisen, 10 768 kjøringer per modell
(§ 6):

- Grunnlaget er en tidsprobe 19.10.2026 på 6 NB Tale-treningsytringer (3–18 s
  lyd, utenfor testutvalget), kjørt gjennom kjeden med prompt på.
- Snitt per ytring, med min–maks i parentes:

  | Backend | medium | large | Sum |
  |---|---|---|---|
  | **Metal (valgt)** | 1,93 s (1,54–2,43) → 5,8 t | 6,07 s (5,19–6,81) → 18,2 t | **≈ 24 t (20,1–27,6)** |
  | CPU `-ng -t 4` (forkastet) | 5,19 s (3,63–6,74) → 15,5 t | 12,73 s (10,80–13,94) → 38,1 t | ≈ 53,6 t (43,2–61,9) |

- Tiden per kjøring er dominert av modellinnlasting og avhenger lite av
  lydlengden i dette området.
- Utpakking av arkiver, vaktpauser og samtidige jobber kommer i tillegg.
- CPU er forkastet fordi det er en annen beregningskjede enn produktet, og
  fordi det tar om lag 2,2 ganger så lang tid.

## 11. Forutsetninger før frys

1. NST (HF) og NB Samtale er lastet ned, SHA-ene står i PROVENIENS og
   manifestet, og NB Samtales test-splitt og merkeliste er inspisert og ført
   inn. Tallskrivemåten for NST og NB Samtale er telt (§ 3).
2. Alle id-listene er generert og committet, med SHA i manifestet, og tallene i
   § 3 stemmer med dem.
3. Determinismetesten på Metal (§ 8) er bestått.
4. Eirik har godkjent frysen.

Alle fire var oppfylt ved frysen 19.10.2026. Punkt 4 ble gitt som godkjenning
av bestillingen, uten en egen faktasjekkport (se `FROZEN.txt`).
