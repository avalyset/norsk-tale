# Standardkalibrering – plan (ikke kjørt)

Status: plan. Ingen datasett er lastet ned. Kjøringen starter først etter at
vilkårslisten er godkjent, og datasettene lagres bare på
`/Volumes/Vault/norsk-tale/data/`. Datasettene publiseres aldri på nytt.

## Mål

- **Kvalitet:** WER og CER med NB-Whisper-prosjektets normalisering
  (`norm.py`, port av NbAiLab/nostram `utils/evaluate.py`). Begge rapporteres for
  rå utdata og for utdata etter korrektor.
- **Feilanalyse, ikke score:** tapte og tillagte nektelser (`feilanalyse.py`), og
  eksempler på tallfeil.
- **Sammenligning:** NB-Whispers publiserte tall (arXiv 2402.01917, tabell 4–7:
  FLEURS 6,6, NST 2,2, CV nynorsk 12,6) står side om side med våre. Avvik
  forklares som hypoteser.

## Målformkryss

Hvert bokmålssett kjøres også med `-l nn`, og hvert nynorsksett også med `-l no`.
Da kan en målformfeil skilles fra en hørselsfeil, og vi kan telle nektelser som
forsvinner når målformen ikke stemmer med talen.

| Sett | Talens målform | Fasit | Kjøres med | Merknad |
|---|---|---|---|---|
| FLEURS nb_no (test) | bokmål | bokmål | `nb` (`-l no`), **`nn` (kryss)** | |
| NST (test nor0464, nærmikrofon) | bokmål | bokmål | `nb`, **`nn` (kryss)** | |
| NPSC (test), bokmål | bokmål | `sentence_text` med `sentence_language_code=nb-NO` | `nb`, `nn` (kryss) | Originalspråklig. `transsentence_text` brukes aldri |
| NPSC (test), nynorsk | nynorsk | `sentence_text` med `sentence_language_code=nn-NO` | `nn`, `nb` (kryss) | |
| Common Voice nn-NO (test) | nynorsk | nynorsk | **`nn` og `nb`** | Krever MDC-konto og vilkår, så det venter på aksepten din |
| NB Tale (test-talere `_x`) | bokmål/nynorsk | etter fasitens målform | fasitens målform | Per dialektgruppe, med antall talere |
| NB Samtale (test) | bokmål/nynorsk | `orthography` per segment | segmentets målform | 5 dialektområder. Ikke delt på taler |

Ved kryss beregnes WER mot fasit i talens målform. Målformfeil blir dermed synlige
som WER-økning, og tapte nektelser telles for seg. Begge rapporteres per celle:
antall nektelser i referansen, antall tapt, andel tapt og antall lagt til.

## Kjøring

- **Modeller:** large og medium (begge på Vault, SHA verifisert). small bare hvis
  den lastes ned.
- **Utvalg:** samme delmengde for alle modeller og alle kryss. Full test-splitt der
  tiden tillater, ellers et fast utvalg med oppgitt seed og antall.
- **Ressursvakt:** `vakt.py` avbryter ved under 20 % ledig minne, mer enn 1 GB
  swap-økning fra start eller under 10 GiB intern disk. Kjøringene skjer på CPU
  (`-ng -t 4`), med `nice -n 19`, én om gangen, og bare når `ollama ps` er tom og
  ingen `inspect eval --model ollama/` lever.
- **Rapport:** `kalibrering/resultater/standard_v1.md` og `.json`, uten lyd og
  uten fulltekst fra datasettene utover korte eksempler.
