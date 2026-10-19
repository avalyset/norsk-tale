# NTA-0002: Filbane der reproduserbarhet kreves; resident bare for diktering

*Skrevet i etterkant, 2026-10-19.*

## Beslutning

Skillen, standardkalibreringen og selvtest-fanen i riggen brukte filbanen: én ny
`whisper-cli`-prosess per fil. Dikteringen brukte en resident `whisper-server`
når den fantes, fordi modellen da ikke lastes for hvert opptak. Uten
`whisper-server` brukte dikteringen også filbanen.

## Grunnlag

- Målt 2026-10-18:
  - Gjentatte kall i samme whisper.cpp-prosess ga ikke bitidentisk tekst.
  - Det ble reprodusert i ren `whisper-cli` med `-f x -f x -f x`, både på GPU og CPU.
  - Det skyldtes verken temperaturfallback, flash attention eller prompten.
  - Testen `test_resident_gjentatte_kall_er_like` er merket `xfail(strict=True)`.
- Filbanen ga samme tekst i tre kjøringer av samme fil
  (`test_determinisme_tre_kjoringer`, bestått 2026-10-19).
- Standardkalibreringen kjørte derfor én prosess per ytring (METHOD.md § 2).
  Gjenskapingstesten ga 10 av 10 identiske.

## Kan falsifiseres ved

- at `test_resident_gjentatte_kall_er_like` blir grønn. Da er oppførselen i
  whisper.cpp endret, og den strenge xfail-merkingen feiler.
- at filbanen gir ulik tekst for samme fil, binær og modell

## Lenker

- [README, Kjente begrensninger](https://github.com/avalyset/norsk-tale#kjente-begrensninger)
- Tag [prereg-v1](https://github.com/avalyset/norsk-tale/releases/tag/prereg-v1)
