"""Skillene og manifestet: dikteringen kan bare startes av brukeren, ingenting kjører ved
siden av skriptet, og pluginen har ingen mod, ingen MCP-server og ingen kroker."""
import json
import os
import pathlib
import re
import subprocess

ROT = pathlib.Path(__file__).resolve().parents[1]
DIKTER = (ROT / "skills" / "dikter" / "SKILL.md").read_text(encoding="utf-8")
TRANSKRIBER = (ROT / "skills" / "transkriber" / "SKILL.md").read_text(encoding="utf-8")
MANIFEST = json.loads((ROT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


def frontmatter(tekst):
    m = re.match(r"---\n(.*?)\n---\n", tekst, re.S)
    assert m, "mangler frontmatter"
    return dict(l.split(": ", 1) for l in m.group(1).splitlines() if ": " in l)


def test_dikter_kan_ikke_startes_av_modellen():
    fm = frontmatter(DIKTER)
    assert fm["disable-model-invocation"] == "true"
    assert "user-invocable" not in fm or fm["user-invocable"] != "false"


def test_dikter_tillater_bare_skriptet_og_ingenting_annet():
    fm = frontmatter(DIKTER)
    assert fm["allowed-tools"].strip('"') == "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dikter *)"


def test_dikter_kjorer_ett_fast_kommandotekst_med_innstillingene_fra_manifestet():
    kommandoer = re.findall(r"^!`([^`\n]+)`$", DIKTER, re.M)
    assert len(kommandoer) == 1, kommandoer
    k = kommandoer[0]
    assert k.startswith("${CLAUDE_PLUGIN_ROOT}/scripts/dikter ")
    assert not re.search(r"[;&|<>]|\$\(|`|\n", k.replace("${", "").replace("}", "")), k
    for felt in ("modellvalg", "modell", "whisper", "malform"):
        assert f"--{felt} '${{user_config.{felt}}}'" in k, felt     # enkle anførselstegn: uløst plassholder er bare tekst
    assert "$ARGUMENTS" not in DIKTER, "ingen brukertekst skal inn i skallkommandoen"


def test_dikter_sier_at_teksten_er_brukerens_prompt_og_haandterer_statusmeldinger():
    assert "dictated message" in DIKTER and "user's own prompt" in DIKTER
    assert "[norsk-tale]" in DIKTER
    assert "disableSkillShellExecution" in DIKTER


def test_transkriber_kan_bare_kjore_skriptet_i_filmodus():
    fm = frontmatter(TRANSKRIBER)
    assert fm["allowed-tools"].strip('"') == "Bash(${CLAUDE_PLUGIN_ROOT}/scripts/dikter --fil *)"
    assert "disable-model-invocation" not in fm          # Claude skal kunne bruke den på en fil du peker på
    assert "mcp__" not in TRANSKRIBER


def test_hver_innstilling_skillene_bruker_finnes_i_manifestet():
    brukt = set(re.findall(r"\$\{user_config\.(\w+)\}", DIKTER + TRANSKRIBER))
    assert brukt == {"modellvalg", "modell", "whisper", "malform"}
    assert brukt <= set(MANIFEST["userConfig"])
    for navn, felt in MANIFEST["userConfig"].items():
        assert not felt.get("sensitive") and not felt.get("secret"), navn


def test_skriptet_er_kjorbart_og_har_fast_tolker_i_isolert_modus():
    sti = ROT / "scripts" / "dikter"
    assert os.access(sti, os.X_OK)
    assert sti.read_text(encoding="utf-8").startswith("#!/usr/bin/env -S python3 -I\n")


def test_ingen_mod_ingen_mcp_server_og_bare_den_ene_vanlige_kroken():
    sporet = subprocess.run(["git", "-C", str(ROT), "ls-files"], capture_output=True, text=True).stdout.split("\n")
    if sporet != [""]:
        forbudt = [f for f in sporet if f.startswith(("mcp/", "types/")) or f in (".mcp.json", "tsconfig.json")
                   or (f.startswith("hooks/") and f != "hooks/hooks.json")]
        assert forbudt == [], forbudt
    for nokkel in ("hooks", "mcpServers", "types", "commands", "agents"):
        assert nokkel not in MANIFEST, nokkel
    kroker = json.loads((ROT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert list(kroker) == ["hooks"] and list(kroker["hooks"]) == ["PreToolUse"], kroker
    (oppforing,) = kroker["hooks"]["PreToolUse"]
    assert oppforing["matcher"] == "Bash"
    (kommando,) = oppforing["hooks"]
    assert kommando == {"type": "command", "command": '"${CLAUDE_PLUGIN_ROOT}"/scripts/avvis-opptak'}
    assert os.access(ROT / "scripts" / "avvis-opptak", os.X_OK)
    tekst = " ".join(p.read_text(encoding="utf-8", errors="ignore")
                     for p in [ROT / "scripts" / "dikter", ROT / "skills" / "dikter" / "SKILL.md"])
    assert "mcp__" not in tekst and "$.mcp" not in tekst
