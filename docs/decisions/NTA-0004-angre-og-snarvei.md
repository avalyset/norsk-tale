# NTA-0004: Angre-knapp og tastatursnarvei, fordi Esc ikke når mods

*Skrevet i etterkant, 2026-10-19.*

## Beslutning

Angre ble en knapp i båndet over prompten og kommandoen `/norsk angre`, ikke Esc.
For terminaler som ikke sender museklikk fikk knappene hurtigtaster: `n`
(🎙 Norsk), `a` (Angre) og `x` (Avbryt test). De nås med Claude Codes egen
`ctrl+x tab`, som flytter fokus til båndet ([8581d12](https://github.com/avalyset/norsk-tale/commit/8581d12)).

## Grunnlag

- En mod så ikke Esc-tasten når det sto tekst i promptboksen. Derfor kunne Esc
  ikke brukes til å angre en diktering.
- I mod-API-et (Claude Code 2.1.303) virket `hotkey` bare når pluginens sted hadde
  fokus. `action` krevde en eksisterende motorhandling.
- Ingen ledig motorhandling ga én akkord fra prompten uten kollisjon.
  `voice:pushToTalk` lå på mellomrom i Chat-konteksten og ble forkastet.
- Ingen bokstaver var bundet i AbovePrompt-konteksten, så `n`, `a` og `x`
  kolliderte ikke.
- Livetest 2026-10-19 i tmux:
  - `/norsk selvtest`, så `ctrl+x tab` og `n` sendt med tmux send-keys
  - en FLEURS-ytring spilt gjennom høyttaleren til mikrofonen
  - teksten sto etter «TEST: », og `a` ga «TEST: » tilbake (2 av 2 sjekker)

## Kan falsifiseres ved

- en Claude Code-versjon der en bokstav i båndet er bundet av motoren
- en terminal der `ctrl+x tab` ikke når båndet
