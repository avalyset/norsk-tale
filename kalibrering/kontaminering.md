# Kontaminering: ble testsettene brukt til å trene NB-Whisper?

Undersøkt 19.10.2026, bare lesing. Gjelder `NbAiLab/nb-whisper-large` (sha
`8c6249fd`), `-medium` (`0ed074d5`) og `-small` (`e9bb5cb8`), og ggml-filene i de
samme repoene. Treningskjeden for hovedmodellene (v0.8-vad3) er OpenAI Whisper →
release candidate på `ncc_speech_v7` → `ncc_speech_styling_v2_vad3`. Den står i
`stats.md` i HF-repoene og i skriptene under `scream_experiments/` i GitHub
NbAiLab/nb-whisper @ `7eb9d261`.

Selve treningsdatasettene (`ncc_speech*`) er private på HF. Sammensetningen er
derfor lest ut av byggedokumentet `processing_v5.md` i NbAiLab/nostram @
`7adfc16a`. Treningsfilene der er lydbøker (nb/nn), NRK, `nst_train`, `stortinget_train`
og stillhet. Det finnes ingen FLEURS-trening, NPSC, Common Voice, NB Tale eller NB
Samtale i noen treningsoppstilling.

| Sett | Brukt i trening? | Merknad til våre tall |
|---|---|---|
| **FLEURS nb_no, test** | Nei. Testsplitten (357) og valideringen (163) ble brukt til evaluering under trening av release-kandidatene, ikke til gradienttrening (`processing_v5.md`; papiret kaller FLEURS «out-of-domain»). | Valideringen ble brukt til modellvalg, men testen er holdt utenfor. Ingen markering. |
| **NST, test nor0464** | Treningsdelen nor0463 er brukt i trening (260 t i trinn 1 og 490 t i trinn 2, arXiv 2402.01917, tabell 3). Testen er ikke brukt i trening. NB-Whisper evaluerte på linje 1–1500 av nor0464 og brukte linje 1501–3000 til validering. | Linje 1501–3000 påvirket modellvalget. Vi rapporterer NST både for linje 1–1500 (samme utvalg som NB-Whisper) og for resten, og markerer valideringsdelen som mulig optimistisk. Papiret sier at taleroverlapp med treningen ble unngått. |
| **NPSC, test (4 møtedager)** | Ikke i hovedmodellene. NPSC-trening finnes bare i `-verbatim`-variantene. Hovedmodellene trente på Stortinget Speech Corpus (SSC). Ifølge Språkbanken holder SSC NPSCs test- og valideringsmøter utenfor (sbr-91). | At NB-Whispers Stortinget-test er nettopp disse møtene, er sannsynlig, men ikke bevist, siden `ncc_speech` er privat. NPSC-tallet markeres som «test holdt utenfor ifølge SSC; ikke verifiserbart i ncc_speech». |
| **Common Voice nn-NO** | Ikke nevnt noe sted som trening. Utelukkelse er heller ikke uttalt. | Status ukjent, trolig ikke brukt. Grunnmodellen (OpenAI Whisper) har ukjente treningsdata. |
| **NB Tale** | Ikke nevnt noe sted som trening. NbAiLabs senere evalueringsrepo (2026) behandler NB Tale som held-out. Det er bare et indisium. | Status ukjent, trolig ikke brukt. |
| **NB Samtale, test** | Ikke nevnt noe sted som trening. Korpuset ble publisert 18.08.2023, før treningsdataene ble frosset i september 2023, men det finnes ikke i noen pipeline. | Status ukjent, trolig ikke brukt. **Testen er ikke delt på taler**, så samme taler kan opptre i trening og test i korpusets egen inndeling. Tallet markeres som **mulig optimistisk** når det sammenlignes med modeller trent på NB Samtale. For NB-Whisper, som ikke er trent på det, gjelder forbeholdet sammenligninger med andre modeller. |

Forbehold som gjelder alle settene: alle modellene er initialisert fra OpenAI
Whisper, som ikke har oppgitt treningsdataene sine. Kontaminering via
grunnmodellen, for eksempel FLEURS eller Common Voice, kan verken bekreftes eller
utelukkes.

Kilder: modellkortene og `test_results.json` i HF-repoene, arXiv 2402.01917 v1
(seksjon 4–5, tabell 3–7), NbAiLab/nb-whisper `scream_experiments/` @ `7eb9d261`,
NbAiLab/nostram `processing_v5.md` @ `7adfc16a`, Språkbanken sbr-91 (SSC),
sbr-85 og sbr-31.
