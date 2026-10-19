# NTA-0005: nb som standard målform

*Skrevet i etterkant, 2026-10-19.*

## Beslutning

Standard målform ble `nb` (whisper `-l no`). `nn` og `auto` kan velges i
innstillingene ([95319c7](https://github.com/avalyset/norsk-tale/commit/95319c7)).

## Grunnlag

- Observert i ett klipp 2026-10-19 (45 s bokmålstale, medium og large på CPU):
  - Med `-l nn` skrev whisper.cpp nynorske former.
  - Med large forsvant én av to nektelser: «Det er ikke sikkert …» ble «Det er
    sikkert …» ([711c382](https://github.com/avalyset/norsk-tale/commit/711c382), [0908c1e](https://github.com/avalyset/norsk-tale/commit/0908c1e)).
- Dette var én observasjon, ikke en måling av hvor ofte det skjer.
- Målformkrysset (Q2) er preregistrert, men ligger i fase 2 og er ikke målt.

## Kan falsifiseres ved

- at fase 2 av standardkalibreringen viser at `nn` på bokmålstale ikke gir tapte
  nektelser utover det `nb` gir. Da faller den sikkerhetsmessige begrunnelsen,
  ikke valget av standard i seg selv.
