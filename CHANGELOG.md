# Endringslogg

Formatet følger [Keep a Changelog](https://keepachangelog.com/no/1.1.0/), og
versjonene følger semantisk versjonering.

## [0.1.0] – 2026-10-19

### Lagt til

- Lokal norsk diktering i promptboksen: knappen «🎙 Norsk» og `/norsk`, med NB-Whisper
  og whisper.cpp på egen maskin. Lyden forlater ikke maskinen.
- Tastatursnarvei: `ctrl+x tab` og så `n` (start og stopp), `a` (Angre) og `x`
  (Avbryt test). Virker også med tekst i promptboksen og uten mus.
- Angre-knapp og `/norsk angre`.
- Skillen `transkriber` for lokale lydfiler.
- `/norsk oppsett`: sjekker ffmpeg, whisper.cpp og modellen (SHA256 mot Hugging Face).
  Laster ikke ned noe.
- Målform `nb`, `nn` eller `auto` (whisper `-l no`, `-l nn` eller `auto`).
- `/norsk selvtest`: én diktering som sjekker innsetting etter prefikset og Angre.
- `/norsk kalibrer`: lokal kalibreringsrigg på `127.0.0.1` med token. Fanen
  «Selvtest» har seks kjente setninger med scoring av nektelse, tall, navn, første
  ord og målform, pluss stopp-tider. Bidrag kan eksporteres med bare tall.
- Standardkalibrering preregistrert på OSF (rtbkz, embargo til 2027-04-19). Fase 1
  er kjørt og scoret: `kalibrering/resultater/prereg-v1-fase1.md`.
- ADR-er i `docs/decisions/` (NTA-0001 til NTA-0006) og `CITATION.cff`.

### Endret

- Kjernen er utgått fra NORSKRIBER. Den håndskrevne MCP-serveren fra første utkast
  er erstattet av skillen (NTA-0003).
- Seks-setningstesten er flyttet fra `/norsk selvtest` til riggens fane
  «Selvtest».
- Riggen leser hele POST-kroppen før ruting. Ruter som ikke brukte kroppen, ga
  HTTP 501 på neste forespørsel over samme tilkobling.

### Kjente begrensninger

- Testet bare på macOS (Apple M1 Pro). Ikke testet på Windows eller Linux.
- FLEURS, fase 1: medium mistet 2 av 77 nektelser (begge prompt-cellene). Large
  mistet ingen.
- Korrektoren (fasittabellen) ga 0 treff i FLEURS og NB Tale. Den retter bare 13
  kjente feilformer av navn.
- Med en resident `whisper-server` er gjentatte transkripsjoner av samme lyd ikke
  bitidentiske. Filbanen er deterministisk (NTA-0002).
- Chrome spør om mikrofontilgang hver gang riggen startes, fordi porten er
  tilfeldig og tillatelsen gjelder per port.
- Målformkrysset (nb mot nn) og de øvrige testsettene (NST, NPSC, NB Samtale) er
  fase 2 og ikke kjørt.

[0.1.0]: https://github.com/avalyset/norsk-tale/releases/tag/v0.1.0
