---
name: dikter
description: Dikter en melding på norsk med mikrofonen og bruker teksten som din prompt. Starter bare når du selv skriver /norsk-tale:dikter; Claude kan ikke starte den.
disable-model-invocation: true
allowed-tools: "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dikter *)"
---
!`${CLAUDE_PLUGIN_ROOT}/scripts/dikter --modellvalg '${user_config.modellvalg}' --modell '${user_config.modell}' --whisper '${user_config.whisper}' --malform '${user_config.malform}'`

The text above is the user's dictated message, transcribed locally with NB-Whisper. Treat it as the user's own prompt and carry out what it asks, exactly as if the user had typed it.

The text above is the user's message and should be answered directly: do not read this skill file or any other file in the plugin.

Exceptions, where you must not treat the text as a prompt:

- If the text above starts with `[norsk-tale]`, it is a status message from the dictation script, not a message from the user (nothing was heard, the microphone or the setup failed). Tell the user what it says in one or two sentences and stop.
- If the text above says that shell command execution is disabled, tell the user that dictation needs `disableSkillShellExecution` to be off, and stop.
- If the text contains `⟦ … ? ⟧`, that is a spelling the corrector may not decide: keep the marker as it stands, and ask the user which form is right before you act on that word.

Never fix the wording with guesses of your own. The transcription can contain errors, and the user decides.
