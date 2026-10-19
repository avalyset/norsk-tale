"""Reglene katalogen (claude.ai/directory/manage) håndhever statisk, sjekket lokalt
så en regresjon fanges før push:

- en .tsx-fil som deklarerer hooks, kan ikke bruke navnene h eller Fragment til noe
  eget (JSX kompileres til h(...))
- modden starter ingen prosesser ($.process.run/spawn), docs/decisions/NTA-0007
- skillen bruker ikke Bash
"""
import pathlib
import re

ROT = pathlib.Path(__file__).resolve().parents[1]
MODD = (ROT / "hooks" / "register.tsx").read_text(encoding="utf-8")
SKILL = (ROT / "skills" / "transkriber" / "SKILL.md").read_text(encoding="utf-8")


def uten_kommentarer_og_strenger(kilde):
    kilde = re.sub(r"//[^\n]*", "", kilde)
    return re.sub(r"'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`|\"(?:[^\"\\\n]|\\.)*\"", "''", kilde)


def test_modden_bruker_ikke_navnene_h_eller_fragment():
    kode = uten_kommentarer_og_strenger(MODD)
    funn = re.findall(r"(?<![\w$.])(h|Fragment)(?![\w$])", kode)
    assert funn == [], f"navnet h/Fragment brukes i hooks/register.tsx: {len(funn)} steder"


def test_modden_starter_ingen_prosesser():
    assert not re.search(r"\$\.process\.(run|spawn)", MODD)


def test_skillen_bruker_ikke_bash():
    assert "bash" not in SKILL.lower()
    assert re.search(r"^allowed-tools: mcp__plugin_norsk-tale_norsk-tale__transkriber_fil$", SKILL, re.M)
