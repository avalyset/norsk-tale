# Personvern

Gjelder grenen `feat/uten-mod` (ikke utgitt). Pluginen er her en skill og ett skript,
uten mod, uten MCP-server og uten kroker.

## Kort

- norsk-tale samler ikke inn data. Det finnes ingen telemetri, analyse eller
  rapportering til utvikleren eller andre.
- Lyden forlater aldri maskinen. Opptaket går fra mikrofonen via ffmpeg til
  whisper.cpp, og alt skjer lokalt.
- Pluginen gjør ingen nettverkskall: ingen installasjon fra PyPI, ingen nedlasting av
  modellen, ingenting under bruk. Pluginen bruker bare Pythons standardbibliotek.

## Hva som skjer med lyden

- Mikrofonen åpnes når du selv skriver `/norsk-tale:dikter`, og lukkes når opptaket er
  ferdig: 1,5 s etter at du slutter å snakke, etter 90 s, eller etter 10 s uten tale.
- Claude kan ikke starte mikrofonen: skillen har `disable-model-invocation: true`, og
  bare skriptet `scripts/dikter` er forhåndsgodkjent mens den kjører.
- Opptaket skrives til en midlertidig katalog og slettes når skriptet er ferdig. Blir
  prosessen drept midt i en transkripsjon, kan den midlertidige katalogen bli liggende
  i `$TMPDIR` til systemet rydder der.
- Skillen `transkriber` leser bare lydfila du selv peker på, med `scripts/dikter --fil`,
  som aldri åpner mikrofonen. Den lager ingen kopi utover midlertidige filer (16 kHz-lyd
  og råtekst fra whisper) som slettes etterpå.

## Hva som skjer med teksten

Transkripsjonen settes inn i samtalen som din prompt, og for `transkriber` som svar fra
et verktøy. Derfra gjelder samme regler som for alt annet du skriver i Claude Code: teksten
går til modellen du bruker, vanligvis Anthropics servere. norsk-tale sender aldri inn noe
selv. Claude Code kan lagre prompthistorikk og samtaler lokalt etter sine egne
innstillinger. Merk at det som sies nær mikrofonen mens opptaket pågår, blir en del av
prompten.

## Hva som lagres

- Innstillingene dine (modellvalg, målform, modellsti, whisper-sti) lagres av Claude Code i
  `settings.json`.
- Modellen ligger der du har lagt den. Standard er `~/.cache/norsk-tale/`.
- `scripts/dikter` lagrer ingenting varig: verken lyd, tekst eller logg.
- Kalibreringsriggen (`kalibrering/rigg.py`, startes for hånd) lagrer opptak (16 kHz wav),
  transkripsjoner og resultater i opptaksmappa til du sletter dem. Riggen lytter bare på
  `127.0.0.1`, krever et tilfeldig token og gjør ingen utgående nettverkskall. «Eksporter
  bidrag» lager en fil med bare tall, uten lyd og uten tekst, og bare når du ber om det.

## Nedlasting og nett

Pluginen laster ikke ned noe og bruker ikke nett. Modellen laster du ned selv:
`scripts/dikter` viser hva som mangler og kommandoen du kan kjøre, uten å kjøre den.
Installasjon av selve pluginen gjøres av Claude Code.

## Kontakt

Spørsmål kan sendes til Eirik Botten Nicolaysen, EcoDeco AS, eirik@ecodeco.no,
eller som issue på https://github.com/avalyset/norsk-tale/issues.
