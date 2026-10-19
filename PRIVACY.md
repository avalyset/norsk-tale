# Personvern

Gjelder norsk-tale 0.1.1.

## Kort

- norsk-tale samler ikke inn data. Det finnes ingen telemetri, analyse eller
  rapportering til utvikleren eller andre.
- Lyden forlater aldri maskinen. Opptaket går fra mikrofonen via ffmpeg til
  whisper.cpp, og alt skjer lokalt.
- Pluginen gjør ingen nettverkskall under transkripsjon. Når `whisper-server` finnes,
  snakker lytteren med den over `127.0.0.1` (loopback), og serveren er bare bundet
  dit. Uten `whisper-server` brukes ingen sockets. Ingenting går ut av maskinen.

## Hva som skjer med lyden

- Mikrofonen åpnes når du trykker «🎙 Norsk» eller skriver `/norsk`, og lukkes når
  opptaket er ferdig: ved et nytt trykk, etter 1,5 s stillhet etter tale, eller
  etter 2 minutter.
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
- Lytteren bruker en kontrollkatalog under `$TMPDIR` med små kommandofiler
  (`start`, `stopp`, `avslutt`) som slettes etter hvert som de leses. Den tomme
  katalogen blir liggende til systemet rydder `$TMPDIR`.
- Modellen ligger der du har lagt den. Standard er `~/.cache/norsk-tale/`.
- `/norsk kalibrer` lagrer opptak (16 kHz wav), transkripsjoner og resultater i
  `~/norsk-tale-opptak/<runde>/` til du sletter dem. Siden har en slette-knapp for
  opptakene. Serveren lytter bare på `127.0.0.1`, krever et tilfeldig token og gjør
  ingen utgående nettverkskall. «Eksporter bidrag» lager en fil med bare tall,
  uten lyd og uten tekst, og bare når du ber om det.
- `/norsk selvtest` lagrer resultatet som `~/norsk-tale-opptak/selvtest-claude-<tidspunkt>.json`:
  det som sto i promptboksen etter dikteringen, og om Angre virket. Ingen lyd.
- Fanen «Selvtest» i `/norsk kalibrer` lagrer `selvtest-<tidspunkt>.json` i samme
  mappe: setningene, teksten som ble transkribert, målingene og scoren. Lyden
  konverteres i en midlertidig katalog som slettes, og lagres ikke.
- Filene blir liggende til du sletter dem.

## Nedlasting

norsk-tale laster ikke ned noe. `/norsk oppsett` viser hva som mangler og hvilken
kommando du kan kjøre selv. Installasjon av pluginen og nedlasting av modellen
skjer over nett, men utføres av henholdsvis Claude Code og deg selv, ikke av
pluginen under bruk.

## Kontakt

Spørsmål kan sendes til Eirik Botten Nicolaysen, EcoDeco AS, eirik@ecodeco.no,
eller som issue på https://github.com/avalyset/norsk-tale/issues.
