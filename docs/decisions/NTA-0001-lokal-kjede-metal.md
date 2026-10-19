# NTA-0001: Lokal kjede på Metal

*Skrevet i etterkant, 2026-10-19.*

## Beslutning

All transkripsjon skjedde på brukerens maskin med whisper.cpp og NB-Whisper i
ggml-format, med Metal som standard backend på Apple Silicon. Standardkalibreringen
(prereg-v1) frøs Metal som backend. CPU (`-ng`) ble forkastet.

## Grunnlag

- Lyden skulle ikke forlate maskinen. Kjernen åpnet ingen nettverksforbindelse.
  Testen `test_nettverksfri_transkripsjon` kjørte whisper under et nettverksforbud
  på OS-nivå (sandbox-exec) og ble bestått 2026-10-19.
- Tidsprobe 2026-10-19, M1 Pro, 6 NB Tale-treningsytringer (METHOD.md § 10):
  - Metal: 1,93 s per ytring med medium og 6,07 s med large.
  - CPU med `-ng -t 4`: 5,19 s med medium og 12,73 s med large.
- CPU ga dessuten en annen beregningskjede enn produktet bruker.
- Metal var deterministisk med én prosess per ytring:
  - 5 av 5 byte-identiske i determinismetesten før frysen (`kalibrering/FROZEN.txt`)
  - 10 av 10 i gjenskapingstesten etter fase 1 (`kalibrering/AVVIK.md` nr. 2)

## Kan falsifiseres ved

- en transkripsjon som åpner en ikke-lokal forbindelse
- en gjentatt fase-1-kjøring på Metal med samme binær og modell som gir annen rå
  tekst

## Lenker

- Tag [prereg-v1](https://github.com/avalyset/norsk-tale/releases/tag/prereg-v1), METHOD.md § 2 og § 10
- OSF-registrering rtbkz (embargo til 2027-04-19): https://osf.io/rtbkz/
