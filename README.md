# Norsk tale

Local Norwegian dictation for Claude Code. Type `/norsk-tale:dikter`, speak Norwegian,
and the transcription becomes your prompt. The speech recognition is
[NB-Whisper](https://huggingface.co/NbAiLab/nb-whisper-large) from the National Library of
Norway, run with [whisper.cpp](https://github.com/ggml-org/whisper.cpp) on your own machine.
The audio never leaves the machine.

> **Status: development branch `feat/uten-mod`, not released.** This branch replaces the
> v0.2.x architecture (a mod, an MCP server and hooks) with a skill, one script and one plain
> hook. The old
> README is kept in [docs/README-0.2-mod-og-mcp.md](docs/README-0.2-mod-og-mcp.md) (in Norwegian).

**Claude cannot start the microphone. Only you can, by typing the command yourself.**
**The plugin makes no network calls at all: the model is a file you download yourself.**

Listed on the National Library's supplier list for NB-Whisper:
https://github.com/NbAiLab/nostram/blob/main/leverandorer.md

## How it works

```
you type /norsk-tale:dikter
  └─ Claude Code expands the skill skills/dikter/SKILL.md
       └─ its !`…` line runs scripts/dikter            (one fixed command)
            ├─ ffmpeg records the microphone until silence (voice-activity check, at most 90 s)
            ├─ one new whisper-cli process transcribes it (kjerne/, model SHA256 verified first)
            └─ the transcription is printed to stdout, and only that
       └─ the text replaces the !`…` line, and Claude treats it as your prompt
```

There is no mod, no MCP server and no background process. The only hook is a plain
`PreToolUse` hook that stops the model from running the script (see below). The microphone is
open only while `scripts/dikter` runs, and the recording is written to a temporary
directory that is deleted when the script returns.

The script always exits with code 0. When nothing was heard, or something is missing or
failed, it prints one line that starts with `[norsk-tale]`, and the skill tells Claude to
report that line instead of treating it as a prompt.

### Why Claude cannot start the microphone

Three layers, measured in Claude Code 2.1.303 on 2026-10-21 with a logged-in session:

- `skills/dikter/SKILL.md` has `disable-model-invocation: true`: Claude cannot invoke the
  skill on its own. Only your own `/norsk-tale:dikter` runs it.
- The skill's `allowed-tools` is exactly `Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dikter *)`:
  during the turn you start, only that script is pre-approved. The second skill,
  `transkriber` (Claude may use it on an audio file you point to), is limited to
  `Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dikter --fil *)`; `--fil` skips the microphone.
- `hooks/hooks.json` has one plain `PreToolUse` hook on `Bash`, `scripts/avvis-opptak`. It
  denies a Bash call from the model that runs `scripts/dikter` without `--fil` (also through
  `bash -c`, `python3`, `env`, pipes and so on). `--fil`, `--help` and commands that only read
  or mention the script pass.

The first two layers alone were not enough. What happened when I asked Claude, in plain
conversation, to "record audio from the microphone with the norsk-tale script":

| Mode | Without the hook | With the hook |
|---|---|---|
| Default (manual) | Claude could only see the `transkriber` skill. Using it asked for permission; running the script through Bash said "This command requires approval". I denied both, and nothing was recorded. | The hook denied the Bash call before any prompt (`PreToolUse:Bash hook error: norsk-tale: Claude kan ikke starte mikrofonen …`). Nothing was recorded. |
| Auto | **Claude ran the script through Bash with no prompt**, and the microphone was open for 10 s ("Allowed by auto mode classifier"). | The hook denied the call. Claude told me to type `/norsk-tale:dikter` myself. |

Your own `/norsk-tale:dikter` works in both modes, with and without the hook. In auto mode
the injected command was run by Claude Code itself: the skill's text arrived with the
transcription already in it, and the model made no tool call first. The hook is not
triggered by that injected command (it only saw the model's own Bash calls), so it cannot
get in the way of your start. `transkriber` with `--fil` also works with the hook.

This is a speed bump, not a guarantee. The hook reads the text of the Bash command. The
model could in principle record sound in other ways (ffmpeg directly, for example), and a
call you approve yourself, or a mode that approves Bash calls for you, is a call you made.

## Requirements

- Claude Code (tested with 2.1.303)
- Python 3 and `ffmpeg` on `PATH`. The plugin uses only the Python standard library.
- whisper.cpp with `whisper-cli`
- An NB-Whisper model in ggml format (large, medium or small). The plugin never downloads
  it. `scripts/dikter` prints the command when the file is missing. The file is checked
  against the SHA256 that Hugging Face publishes (`kjerne/modeller.json`) every time it is
  used, and a file that does not match is refused.

| Platform | Status |
|---|---|
| macOS | Developed on macOS 27.0.1, Apple M1 Pro, Python 3.14.8, ffmpeg 9.0.1, whisper.cpp 1.9.2 built from source (Metal). |
| whisper.cpp from Homebrew | Not tested. |
| Windows, Linux | Not tested. |

macOS asks for microphone access for the app that runs Claude Code (Terminal, iTerm,
Claude). Without it macOS delivers only silence, and the script says so.

## Install

```
/plugin marketplace add avalyset/norsk-tale
/plugin install norsk-tale@norsk-tale
brew install whisper-cpp ffmpeg
```

Then put a model file where you want it (the default is
`~/.cache/norsk-tale/nb-whisper-<model>.bin`). Run `scripts/dikter --fil <audio file>` once
to see whether everything is in place: it names whatever is missing.

## Settings and how the script reads them

| Setting | Default | Meaning |
|---|---|---|
| `modellvalg` | `large` | `large` (3.10 GB), `medium` (1.53 GB) or `small` (0.49 GB) |
| `malform` | `nb` | `nb` (Bokmål), `nn` (Nynorsk) or `auto` |
| `modell` | empty | Path to `ggml-model.bin`. Empty: `~/.cache/norsk-tale/nb-whisper-<model>.bin` |
| `whisper` | empty | Name or path of `whisper-cli`. Empty: `whisper-cli` on `PATH` |

The documentation says a plugin's `userConfig` values reach a skill in two ways. The
reference substitutes `${user_config.KEY}` in "skill and agent content", and exports the
environment variable `CLAUDE_PLUGIN_OPTION_<KEY>` only to hook processes. `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` are likewise not present in the
environment of commands that run through the Bash tool; they are substituted in the skill's
text instead. A skill's command therefore gets the settings as arguments, which is why
`skills/dikter/SKILL.md` writes them into the command line:

```
${CLAUDE_PLUGIN_ROOT}/scripts/dikter --modellvalg '${user_config.modellvalg}' … 
```

Tested in Claude Code 2.1.303: when the settings are saved, the values are substituted
(a saved `modellvalg=medium` reached the script). When they are not saved, the placeholder
stays in the command as plain text. The values are therefore in single quotes (an unquoted
`${user_config.x}` is rejected by Claude Code's command parser before anything runs), and
the script treats an unresolved placeholder as "not set". An empty or unset setting falls
back to the environment variables `NORSK_TALE_MODELLVALG`, `NORSK_TALE_MALFORM`,
`NORSK_TALE_MODELL` and `NORSK_TALE_WHISPER`, and then to the defaults above. Settings
without saved values need no setup at all.

## Use

1. Type `/norsk-tale:dikter` and press Enter.
2. Speak. The recording stops 1.5 s after you stop talking, or after 90 s. If nothing is
   heard in 10 s, the script gives up with a message.
3. The transcription is sent to Claude as your prompt.

To have Claude transcribe an audio file, ask it to, with the path:
`/norsk-tale:transkriber` or just "transcribe /path/to/memo.m4a".

If the text contains `⟦ spelling → suggestion? ⟧`, the corrector (a fixed table of Norwegian
name spellings, `kjerne/vokabular/`) was not allowed to decide that spelling. Claude keeps
the marker and asks you which form is right.

## Limitations

- **No keyboard shortcut or button.** You type the command each time. (v0.2.x had a button
  and a shortcut, which needed a mod.)
- **At most 90 s per dictation**, and Claude Code's Bash tool has a default time limit of
  2 minutes for the whole command. Measured on an M1 Pro with the large model and Metal,
  87 s of speech took 16.8 s to load, verify and transcribe, so a full 90 s dictation
  fits. A slower machine, a CPU-only build or a larger model may not, and a command that
  runs out of time is killed. Use `medium` or `small` for long dictations there.
- **Claude may open `skills/dikter/SKILL.md` after a dictation.** In two sessions the model read
  the file on its own, which asks for permission when the plugin is outside the working
  directory (in auto mode the question offers to change a permission setting; choose a
  "ask again next time" answer). It does not affect the dictation.
- **No editing before sending.** The text becomes your prompt immediately. There is no
  undo; say so in the next message if the transcription was wrong.
- **The model is loaded for every dictation** (a few seconds), because there is no
  resident process.
- **`disableSkillShellExecution`** in Claude Code's settings turns the `!` command off. The
  skill then reports that shell execution is disabled, and dictation does not work.
- **Whatever is spoken near the microphone ends up in your prompt.** Check the language
  and the content before the prompt is carried out; the skill asks Claude to treat the text
  as yours, so other people's speech counts as yours.
- Windows and Linux are not tested. The calibration rig (`kalibrering/rigg.py`) is not
  started by any command on this branch: run `python3 kalibrering/rigg.py` yourself.

## Measured quality: standard calibration, phase 1

The standard calibration was preregistered before it was run: on OSF as
[rtbkz](https://osf.io/rtbkz/) (embargo until 2027-04-19) and as the git tag `prereg-v1`.
Phase 1 was run with the chain as it ships: whisper.cpp with NB-Whisper ggml on Metal,
beam 5, one process per utterance. The figures are word error rates (WER) in percent with
95 % confidence intervals, in full in
[`kalibrering/resultater/prereg-v1-fase1.md`](kalibrering/resultater/prereg-v1-fase1.md).

Phase 1 applies to the core at these SHA256 values, unchanged on this branch:

- `kjerne/kjerne.py` `962e691c47824a4160bbd8fd208330abac5a7d4fd85ab803bedfaa17fb528a24`
- `kjerne/korriger.py` `335bc6ac2454ee1744556f411c2f7cf6a44fcd02579b07ba9d201e863752cc68`
- `kjerne/vokabular/fasit_offentlig.tsv` `fb61815f42d71323fce6680dec388eccf78de68c5d0062c922c07389e4c63ce6`
- `kjerne/vokabular/offentlig_no.txt` `c6ddfd764ce1b0bb113e94df172e307414990067f3d7f67102ef4236036cb341`

`tests/test_preregistrering.py` fails if any of them changes.

| FLEURS nb_no, test (357 utterances), Bokmål, raw text | Prompt off | Prompt on | NB-Whisper published (table 5) |
|---|---|---|---|
| medium | 6.76 [5.96–7.60] | 6.53 [5.78–7.35] | 7.2 |
| large | 5.26 [4.64–5.92] | 5.34 [4.72–5.98] | 6.6 |

NB Tale, module 1 (480 utterances, 72 test speakers, 12 dialect groups), large, nb:
**9.37 [8.14–10.74]**. The figures are not directly comparable with NB-Whisper's published
ones (different framework and precision, and it is not documented which FLEURS field NB
used as reference). Changes since phase 1 (this skill and script instead of the mod and the
MCP server) do not touch the core, the model or the decoding. The
cross-form comparison (nb against nn) and the NST, NPSC and NB Samtale sets are phase 2,
which has not been run.

## Privacy

See [PRIVACY.md](PRIVACY.md). In short: no data is collected, the audio never leaves the
machine, and the plugin makes no network calls. The text you dictate is sent to Claude as
your prompt, like anything else you type.

## Development

```bash
python3 -m pytest tests          # model-dependent tests are skipped with a reason
claude plugin validate --strict .
```

Tests that need the model and a real recording run when these are set:

```bash
NORSK_TALE_TESTLYD=/path/to/clip.wav NORSK_TALE_MODELL=/path/to/ggml-model.bin \
NORSK_TALE_WHISPER=/path/to/whisper-cli python3 -m pytest tests/test_dikter.py
```

The recording path is tested without a microphone: `NORSK_TALE_TESTKILDE` gives ffmpeg a
file to play in real time instead of the microphone. Decisions are in
[docs/decisions/](docs/decisions/).

## Credits

- NB-Whisper from the National Library of Norway, Apache-2.0. The weights are not included.
  Kummervold et al. (2024), "Whispering in Norwegian: Navigating Orthographic and Dialectic
  Challenges", arXiv:2402.01917.
- "FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech", Conneau
  et al., 2022, Google, https://huggingface.co/datasets/google/fleurs, CC-BY-4.0. Only the
  nb_no test split was used in the standard calibration. No audio or full text is published.
- NB Tale, NPSC, NST and NB Samtale from Språkbanken at the National Library, CC0. The
  datasets are not republished.
- whisper.cpp by Georgi Gerganov and contributors, MIT.

See [NOTICE](NOTICE).

## License

Apache-2.0. See [LICENSE](LICENSE).
