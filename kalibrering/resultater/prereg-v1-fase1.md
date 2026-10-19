# Standardkalibrering prereg-v1, fase 1: resultater

Fase 1 etter AVVIK.md nr. 1: FLEURS × {medium, large} × nb × prompt {på, av}, og NB Tale × large × nb × prompt på. Scoret etter METHOD.md § 5 med `fase1.py scor` (de frosne funksjonene i `reproduser.py`). Tallene står i `prereg-v1-fase1.json`. Ingen lyd og ingen tekst fra datasettene er med.

- Kjørt 19.10.2026 fra 11:14:44 til 13:11:18 med Metal under `vakt.py`. Estimatet før start var 2,33 t, og faktisk tid ble 1,94 t.
- Ingen utelukkelser ved kjøring. Analysesettet er komplett i alle celler: FLEURS 357 av 357, NB Tale 480 av 480.
- WER og CER i prosent, med 95 % KI fra paret prosentil-bootstrap (B = 2 000).

## FLEURS nb_no (test, n = 357)

| Modell | Prompt | WER rå [95 % KI] | CER rå [95 % KI] | WER korrigert | Nektelser i ref. | Tapt / lagt til | Tapt per 100 | Markører | Median s/ytring |
|---|---|---|---|---|---|---|---|---|---|
| medium | av | 6,76 [5,96–7,60] | 2,83 [2,31–3,44] | 6,76 | 77 | 2 / 0 | 0,56 | 0 | 1,988 |
| medium | på | 6,53 [5,78–7,35] | 2,64 [2,20–3,18] | 6,53 | 77 | 2 / 0 | 0,56 | 0 | 2,058 |
| large | av | 5,26 [4,64–5,92] | 1,96 [1,66–2,29] | 5,26 | 77 | 0 / 0 | 0,0 | 0 | 4,666 |
| large | på | 5,34 [4,72–5,98] | 1,93 [1,65–2,23] | 5,34 | 77 | 0 / 0 | 0,0 | 0 | 4,759 |

### Mot NB-Whispers publiserte tall (hovedcellen: prompt av, nb, rå)

NBs tall er verifisert 19.10.2026 mot tabell 5 i arXiv 2402.01917v1 (HTML-SHA256 `485104c4d7bbd9a07a9fd3707f37a0f593d4cc67e7003a38455ed7df5571aa9e`, hentet 09:21:25Z): NB-Whisper medium 7,2 og large 6,6.

| Modell | NB (tabell 5) | Vår kjede [95 % KI] |
|---|---|---|
| medium | 7,2 | 6,76 [5,96–7,60] |
| large | 6,6 | 5,26 [4,64–5,92] |

Forbehold fra METHOD § 9 gjelder, og tallene er ikke direkte sammenlignbare:

- NB brukte HF transformers/JAX med full presisjon. Vi bruker whisper.cpp ggml med Metal, beam 5.
- Normaliseringen er sannsynligvis den samme, men det er ikke dokumentert.
- Det er ikke dokumentert hvilket FLEURS-felt NB brukte. Vi bruker `raw_transcription`.
- Avvikene forklares bare som hypoteser: vektversjon (ggml-fila nå mot sjekkpunktet NB evaluerte), dekoding (beam og fallback), og fasitfeltet.
- FLEURS-valideringen ble brukt til modellvalg hos NB. Testen er holdt utenfor (METHOD § 4).

## NB Tale, modul 1 (testtalere, large, nb, prompt på)

Samlet n = 480: WER 9,37 [8,14–10,74], CER 4,06 [3,38–4,84]. Nektelser i referansen: 29, tapt 0, lagt til 0. Markører: 0. Rå = korrigert.

Opplest bokmålsmanus med dialektuttale. Status for kontaminering er ukjent, trolig ikke brukt (METHOD § 4).

Per dialektgruppe har hver gruppe n = 40 ytringer fra 6 talere, så KI-ene er brede og gruppetallene beskrivende. Regionene er NB Tales egen inndeling: hovedspesifikasjon (fylke) og underspesifikasjon, gjengitt ordrett fra tabellen «Spesifikasjon av gruppene» i `Dokumentasjon/02_NB_Tale_Innleseroversikt.pdf`, s. 2 (versjon 2015-12-21, SHA256 `abd41362543a6631629ecdba10b52da5cd1ace5b4e5d0a2d6d8d5e0340f6de79`). Fylkesnavnene er de fra 2015. Regionnavnene er lagt til etter frysen, bare som presentasjon (*eksplorativ, ikke preregistrert*; AVVIK.md nr. 3).

| Gruppe | Region (NB Tale) | WER [95 % KI] | CER [95 % KI] | Nektelser ref. / tapt |
|---|---|---|---|---|
| g01 | Finnmark (+ Nord-Troms) | 9,00 [5,48–12,74] | 3,40 [1,96–4,94] | 1 / 0 |
| g02 | Troms (+ Narvik-området i Nordland) | 8,36 [4,49–12,57] | 3,66 [1,94–5,60] | 2 / 0 |
| g03 | Nordland: Bodø-området + Mo i Rana-området | 10,88 [6,66–15,60] | 4,34 [2,32–6,84] | 2 / 0 |
| g04 | Nordland + Trøndelag + Møre og Romsdal: Brønnøysundområdet, Ytre Trøndelag, Nordmøre | 8,60 [5,20–12,62] | 3,08 [1,77–4,69] | 3 / 0 |
| g05 | Trøndelag | 11,81 [6,87–17,49] | 4,94 [3,03–7,13] | 3 / 0 |
| g06 | Møre og Romsdal: Romsdal og Sunnmøre | 9,24 [5,89–12,90] | 3,61 [1,98–5,36] | 3 / 0 |
| g07 | Sogn og Fjordane | 7,54 [3,91–11,73] | 2,38 [1,21–3,65] | 3 / 0 |
| g08 | Rogaland + Hordaland: hele Rogaland + hele Hordaland | 9,85 [4,19–17,20] | 7,98 [3,18–14,56] | 1 / 0 |
| g09 | Rogaland + Hordaland: hele Rogaland + Bergensområdet av Hordaland | 8,47 [4,78–12,45] | 3,61 [2,02–5,26] | 3 / 0 |
| g10 | Vest-Agder + Aust-Agder | 10,16 [6,56–13,97] | 4,09 [2,31–6,16] | 0 / 0 |
| g11 | Oppland, Hedmark, Telemark, Østfold, Vestfold, Buskerud | 9,69 [4,93–15,15] | 4,37 [1,53–8,04] | 6 / 0 |
| g12 | Oslo og Akershus | 8,79 [5,38–12,25] | 3,05 [1,66–4,57] | 2 / 0 |

## Merknader

- **Rå = korrigert i alle fase-1-celler, 0 markører.** Fasittabellen (`fasit_offentlig.tsv`) har 13 målrettede feilformer for navn som Innovasjon Norge, ORCID og IIIF. Ingen av dem forekommer i FLEURS- eller NB Tale-utdata. Kontrollert per ytring i resultatfilene etter scoring (*eksplorativ, ikke preregistrert*; AVVIK.md nr. 3).
- **Q2 (målformkryss nb mot nn) er ikke besvart i fase 1**, fordi fase 1 bare kjører nb. Krysset ligger i fase 2. Nektelsestallene over gjelder bare nb.
- Ingen andre analyser enn METHOD § 5 er gjort.
