"""Reglene katalogen (claude.ai/directory/manage) håndhever statisk, sjekket lokalt
så en regresjon fanges før push:

- en .tsx-fil som deklarerer hooks, kan ikke bruke navnene h eller Fragment til noe
  eget (JSX kompileres til h(...))
- modden starter ingen prosesser ($.process.run/spawn), docs/decisions/NTA-0007
- skillen bruker ikke Bash
- modden hooker ingen nettverks-, MCP- eller programkall, og mikrofonvernets
  verktøyhooks har en matcher som bare velger pluginens egne verktøy
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


def test_modden_hooker_ingen_nett_mcp_eller_programkall():
    kode = uten_kommentarer_og_strenger(MODD)
    hendelser = re.findall(r"\bon\(\s*''", kode)
    assert hendelser, "fant ingen hooks"
    navn = re.findall(r"\bon\(\s*'([^']+)'", MODD)
    forbudt = [n for n in navn if n.split('.')[0] in {"mcp", "net", "process", "fetch"} or "*" in n]
    assert forbudt == [], f"hooks på nett/MCP/program eller mønster: {forbudt}"


def test_vernets_verktoyhooks_har_matcher():
    for hendelse in ("tool.describe", "tool.check", "tool.call"):
        assert re.search(rf"on\('{re.escape(hendelse)}', \{{ tool: VERNEDE \}}", MODD), hendelse


def test_modden_skriver_ingen_filer_og_leser_ingen_miljovariabler():
    kode = uten_kommentarer_og_strenger(MODD)
    assert not re.search(r"\$\.fs\.", kode)
    assert not re.search(r"\$\.env\.", kode)


def test_hvert_mcp_kall_har_verktoynavnet_som_fast_tekst():
    kall = re.findall(r"\$\.mcp\.call\(([^)]*)\)", MODD)
    assert kall, "fant ingen $.mcp.call"
    for a in kall:
        assert re.fullmatch(r"\s*\w+,\s*'[a-z_]+'(,\s*\w+)?\s*", a), a

