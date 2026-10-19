# NTA-0006: Preregistrering på OSF og fasedeling

*Skrevet i etterkant, 2026-10-19.*

## Beslutning

Standardkalibreringen ble frosset før kjøring:
- `METHOD.md`, `manifest.json` og `reproduser.py` fikk SHA256 i `FROZEN.txt`.
- Den lokale git-taggen er [prereg-v1](https://github.com/avalyset/norsk-tale/releases/tag/prereg-v1).
- Kalibreringen ble preregistrert på OSF som rtbkz (Open-Ended Registration), med
  embargo til 2027-04-19.

Etter start ble kjøringen delt i to (AVVIK nr. 1, [0339421](https://github.com/avalyset/norsk-tale/commit/0339421)):
- **Fase 1:** FLEURS med medium og large, nb, prompt av og på; NB Tale med large, nb,
  prompt på.
- **Fase 2:** resten av matrisen. Den kjøres bare etter en uttrykkelig beslutning.

## Grunnlag

- Beslutningene om metode skulle ligge fast før noen resultater fantes.
- AVVIK nr. 1 ble ført kl. 11:14, før noen resultater var sett. Avgrensningen var
  bestemt av tid: hele matrisen var beregnet til ca. 24 t med Metal, og fase 1 til
  2,3 t (faktisk 1,94 t).
- De frosne filene har vært uendret siden prereg-v1. Alt som er gjort etter
  frysen, står i `kalibrering/AVVIK.md` (nr. 1–3).

## Kan falsifiseres ved

- en endring i `METHOD.md`, `manifest.json` eller `reproduser.py` etter prereg-v1.
  `reproduser.py verifiser` stopper da med kode 2.
- et resultat i fase-1-rapporten som ikke kan gjenskapes med kommandoen i AVVIK
  nr. 2

## Lenker

- OSF-registrering: https://osf.io/rtbkz/ (embargo til 2027-04-19)
- [kalibrering/AVVIK.md](https://github.com/avalyset/norsk-tale/blob/main/kalibrering/AVVIK.md),
  [kalibrering/resultater/prereg-v1-fase1.md](https://github.com/avalyset/norsk-tale/blob/main/kalibrering/resultater/prereg-v1-fase1.md)
