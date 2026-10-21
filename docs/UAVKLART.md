# Uavklart

Funn som er kjent, men ikke rettet. Rettes senere på `main`, ikke på `feat/uten-mod`.

- **`tests/test_kjede.py::test_kjede_fra_trykk_til_tekst[0]` (feil i testoppsettet, 2026-10-21):** testen
  forutsetter et opptak med mindre enn 1,5 s stillhet på slutten, slik at kilden slutter før
  stillhetsvakten. FLEURS-klippet som ble brukt, har omtrent 1,8 s (8,3 s; 6,5 s når slutten
  er trimmet), så opptaket ender på «stillhet» og ikke på «kilden sluttet». Med det trimmede
  klippet består begge parametre. Feiler likt på `main` (`9994232`).
- **`tests/test_kjerne.py::test_resident_gjentatte_kall_er_like` (feil i testoppsettet, 2026-10-21):**
  `xfail(strict=True)` på at gjentatte kall i samme prosess ikke er bitidentiske gjelder lange
  opptak: målt med large og Metal ga 87 s tale tre ulike tekster (`a8144ab6`, `abeb026d`,
  `caec19c7`), mens fire korte FLEURS-klipp (omtrent 8 s) ga identisk tekst tre ganger, så testen
  gir XPASS. Retting: bruk et langt testklipp, eller ta bort `strict`. Feiler likt på `main`.
