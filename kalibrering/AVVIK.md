# Avvik fra prereg-v1

Preregistrering: `METHOD.md`, `manifest.json` og `reproduser.py` ved git-tagg
`prereg-v1`. SHA256 står i `FROZEN.txt`. OSF-registrering: rtbkz,
https://osf.io/rtbkz/, registrert 2026-10-19T08:59:33 UTC, embargo til
2027-04-19.

Hver endring etter frysen føres her før den tas i bruk. Gjelder metode, kode,
data, id-lister, flagg, modeller eller kjøreforhold som kan påvirke resultatet.
Rene kjøreavbrudd fra ressursvakten er ikke avvik (METHOD § 7). Eldre
oppføringer endres aldri. En rettelse føres som en ny oppføring.

| Nr. | Dato | Hva endres (fil, §, felt) | Begrunnelse | Påvirker hvilke celler | Ny SHA256 / commit |
|---|---|---|---|---|---|
| 1 | 2026-10-19 11:14 (før noen resultater er sett; standardkjøringen pauset 11:13:36) | «Kjøringen deles. Fase 1 = FLEURS-ankeret (medium og large, nb, prompt av/på) + NB Tale dialekt (large, nb, prompt på). Resten av preregistrert matrise er fase 2 og kjøres kun ved eksplisitt beslutning. Avgrensningen er bestemt av tid, ikke av resultater. Metoden er ellers uendret.» Teknisk: ny fil `kalibrering/fase1.py` kjører og scorer delmatrisen med de frosne funksjonene i `reproduser.py` (som er uendret, og hele manifestet verifiseres før kjøring). Resultatene skrives i de samme filene som hele matrisen, så fullførte kjøringer gjenbrukes. Komplette tilfeller (METHOD § 7) vurderes innen fase-1-cellene. Allerede fullførte nn-kjøringer for FLEURS/medium hører til fase 2 og brukes ikke i fase 1. | Tid: hele matrisen er beregnet til ≈ 24 t med Metal. | Fase 2 (utsatt): FLEURS nn; NST, NPSC og NB Samtale helt; NB Tale medium og nn. | fase1.py: SHA256 i commit-meldingen |
