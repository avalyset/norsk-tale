# Personvern

Gjelder norsk-tale 0.2.4.

## Kort

- norsk-tale samler ikke inn data. Det finnes ingen telemetri, analyse eller
  rapportering til utvikleren eller andre.
- Lyden forlater aldri maskinen. Opptaket går fra mikrofonen via ffmpeg til
  whisper.cpp, og alt skjer lokalt.
- Pluginen gjør ingen nettverkskall under bruk. Når `whisper-server` finnes, snakker
  lytteren med den over `127.0.0.1` (loopback), og serveren er bare bundet dit.
  Modden og pluginens MCP-server snakker over stdio, ikke over nett. Nett brukes
  én gang ved installasjon (MCP-SDK), se under.

## Hva som skjer med lyden

- Mikrofonen åpnes når du trykker «🎙 Norsk», bruker snarveien eller skriver `/norsk`,
  og lukkes når opptaket er ferdig: ved et nytt trykk, etter 1,5 s stillhet etter
  tale, eller etter 2 minutter.
- Claude kan aldri starte mikrofonen; bare ditt trykk eller din snarvei gjør det.
  Opptaksverktøyene i pluginens MCP-server er skjult for Claude, og modden avviser
  alle kall til dem som ikke kommer fra modden selv.
- Opptaket skrives til en midlertidig katalog og slettes så snart transkripsjonen
  er ferdig. Blir prosessen drept midt i en transkripsjon, kan den midlertidige
  fila bli liggende i `$TMPDIR` til systemet rydder der.
- Skillen `transkriber` leser bare lydfila du selv peker på. Den lager ingen kopi
  utover midlertidige filer (16 kHz-lyd og råtekst fra whisper) som slettes
  etterpå.

## Hva som skjer med teksten

Transkripsjonen settes inn i promptboksen, eller vises i samtalen når skillen
brukes. Derfra gjelder samme regler som for alt annet du skriver i Claude Code.
Når du sender prompten, eller når skillens svar havner i samtalen, går teksten til
modellen du bruker, vanligvis Anthropics servere. norsk-tale sender aldri inn noe
selv. Claude Code kan lagre prompthistorikk og samtaler lokalt etter sine egne
innstillinger.

## Hva som lagres

- Innstillingene dine (modellvalg, modellsti, whisper-sti) lagres av Claude Code i
  `settings.json`.
- MCP-serveren har et Python-venv med MCP-SDK-en i pluginens datamappe
  (`${CLAUDE_PLUGIN_DATA}`, ca. 50 MB). Det inneholder ingen data om deg.
- Modellen ligger der du har lagt den. Standard er `~/.cache/norsk-tale/`.
- `/norsk kalibrer` lagrer opptak (16 kHz wav), transkripsjoner og resultater i
  `~/norsk-tale-opptak/<runde>/` til du sletter dem. Siden har en slette-knapp for
  opptakene. Serveren lytter bare på `127.0.0.1`, krever et tilfeldig token og gjør
  ingen utgående nettverkskall. «Eksporter bidrag» lager en fil med bare tall,
  uten lyd og uten tekst, og bare når du ber om det.
- `/norsk selvtest` lagrer resultatet som `~/norsk-tale-opptak/selvtest-claude-<tidspunkt>.json`:
  det som sto i promptboksen etter dikteringen, og om Angre virket. Ingen lyd. Fila
  skrives av pluginens MCP-server, ikke av modden.
- Fanen «Selvtest» i `/norsk kalibrer` lagrer `selvtest-<tidspunkt>.json` i samme
  mappe: setningene, teksten som ble transkribert, målingene og scoren. Lyden
  konverteres i en midlertidig katalog som slettes, og lagres ikke.
- Filene blir liggende til du sletter dem.

## Nedlasting og nett

Nett brukes én gang ved installasjon (MCP-SDK), aldri under bruk.

- Første gang pluginen starter, installerer MCP-serveren MCP-Python-SDK-en fra PyPI
  i pluginens datamappe. Versjonene er låst med SHA256-hasher (`mcp/krav.txt`).
  Ingenting om deg sendes med, ut over det en vanlig `pip install` sender til PyPI
  (blant annet IP-adresse og pip-versjon).
- Etter det gjør pluginen ingen nettverkskall. Den eneste forbindelsen er loopback
  (`127.0.0.1`) til en lokal `whisper-server` og til kalibreringsriggen.
- Modellen laster pluginen ikke ned. `/norsk oppsett` viser hva som mangler og
  hvilken kommando du kan kjøre selv.
- Installasjon av selve pluginen gjøres av Claude Code.

## Kontakt

Spørsmål kan sendes til Eirik Botten Nicolaysen, EcoDeco AS, eirik@ecodeco.no,
eller som issue på https://github.com/avalyset/norsk-tale/issues.
