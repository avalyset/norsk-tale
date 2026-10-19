"""Kjernen: konfigurasjon, oppsettsjekk, sjekksum-pin, nettverksfrihet, determinisme.

De tunge testene trenger modellen, whisper.cpp og en EKTE norsk lydfil som ligger
UTENFOR repoet. De hoppes over med begrunnelse når noe mangler:

  NORSK_TALE_TESTLYD=/sti/til/opptak.m4a \
  NORSK_TALE_MODELL=/sti/til/ggml-model.bin \
  NORSK_TALE_WHISPER=/sti/til/whisper-cli \
  python3 -m pytest tests/test_kjerne.py

Lyd og vekter ligger aldri i repoet.
"""
import hashlib, json, os, pathlib, shutil, socket, subprocess, sys, urllib.request
import pytest

KJERNE = pathlib.Path(__file__).resolve().parents[1] / "kjerne"
sys.path.insert(0, str(KJERNE))
import kjerne  # noqa: E402

TESTLYD = os.environ.get("NORSK_TALE_TESTLYD")
NOKLER = {"verbatim", "korrigert", "substitusjonslogg", "modell_sha256", "versjon"}


def _klar():
    try:
        o = kjerne.standard_oppsett()
    except Exception:
        return False
    return o.modell.is_file() and o.whisper_cli is not None and o.whisper_server is not None


tung = pytest.mark.skipif(not (TESTLYD and pathlib.Path(TESTLYD).is_file() and _klar()),
                          reason="krever NORSK_TALE_TESTLYD (ekte opptak utenfor repoet), modellen og whisper.cpp")
SANDBOX = shutil.which("sandbox-exec") if sys.platform == "darwin" else None
NETTFORBUD = ["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]


@pytest.fixture
def rent_miljo(monkeypatch):
    for k in ("NORSK_TALE_MODELLVALG", "NORSK_TALE_MODELL", "NORSK_TALE_WHISPER"):
        monkeypatch.delenv(k, raising=False)


def _falsk_whisper(tmp_path):
    d = tmp_path / "bin"
    d.mkdir()
    for navn in ("whisper-cli", "whisper-server"):
        (d / f"{navn}{kjerne.EXE}").write_bytes(b"")
    return d / f"whisper-cli{kjerne.EXE}"


# ---------------------------------------------------------------- konfigurasjon
def test_modellkatalogen_har_tre_valg_med_hf_sha():
    k = kjerne.modellkatalog()
    assert set(k) == {"large", "medium", "small"}
    for v in k.values():
        assert len(v["sha256"]) == 64 and int(v["sha256"], 16) >= 0
        assert v["repo"].startswith("NbAiLab/nb-whisper-") and v["fil"] == "ggml-model.bin"


def test_standardsti_ligger_i_hjemmets_cache(rent_miljo):
    o = kjerne.standard_oppsett(modellvalg="small")
    assert o.modell == pathlib.Path.home() / ".cache" / "norsk-tale" / "nb-whisper-small.bin"
    assert o.sha256 == kjerne.modellkatalog()["small"]["sha256"]


def test_ukjent_modellvalg_er_en_tydelig_feil(rent_miljo):
    with pytest.raises(kjerne.KjerneFeil, match="Ukjent modellvalg"):
        kjerne.standard_oppsett(modellvalg="tiny")


def test_whisper_server_finnes_ved_siden_av_gitt_sti(rent_miljo, tmp_path):
    cli = _falsk_whisper(tmp_path)
    o = kjerne.standard_oppsett(whisper=str(cli))
    assert o.whisper_cli == cli and o.whisper_server == cli.parent / f"whisper-server{kjerne.EXE}"


def test_argument_slaar_miljo(monkeypatch, tmp_path):
    monkeypatch.setenv("NORSK_TALE_MODELLVALG", "medium")
    monkeypatch.setenv("NORSK_TALE_MODELL", str(tmp_path / "fra-miljo.bin"))
    o = kjerne.standard_oppsett(modellvalg="small", modell=str(tmp_path / "fra-arg.bin"))
    assert o.modellvalg == "small" and o.modell == tmp_path / "fra-arg.bin"
    o2 = kjerne.standard_oppsett()
    assert o2.modellvalg == "medium" and o2.modell == tmp_path / "fra-miljo.bin"


def test_sjekk_viser_storrelse_og_laster_ikke_ned(rent_miljo, tmp_path):
    cli = _falsk_whisper(tmp_path)
    modell = tmp_path / "modeller" / "m.bin"
    o = kjerne.standard_oppsett(modellvalg="medium", modell=str(modell), whisper=str(cli))
    r = kjerne.sjekk_oppsett(o)
    assert not r["ok"] and "modell" in r["mangler"]
    assert "1.53 GB" in r["melding"] and "Ingenting lastes ned automatisk" in r["melding"]
    assert "huggingface.co/NbAiLab/nb-whisper-medium/resolve/main/ggml-model.bin" in r["melding"]
    assert not modell.parent.exists()      # sjekken oppretter ingenting


def test_sjekk_uten_whisper_foreslaar_brew(rent_miljo, tmp_path, monkeypatch):
    monkeypatch.setattr(kjerne.sys, "platform", "darwin")
    o = kjerne.standard_oppsett(whisper=str(tmp_path / "finnes-ikke" / "whisper-cli"))
    r = kjerne.sjekk_oppsett(o, verifiser_sha=False)
    assert "whisper-cli" in r["mangler"] and "brew install whisper-cpp ffmpeg" in r["melding"]


def test_cli_sjekk_gir_kode_4_naar_noe_mangler(tmp_path):
    r = subprocess.run([sys.executable, "-I", str(KJERNE / "kjerne.py"), "--sjekk", "--uten-sha",
                        "--modell", str(tmp_path / "ingen.bin"), "--whisper", str(tmp_path / "ingen")],
                       capture_output=True, text=True)
    assert r.returncode == 4
    assert json.loads(r.stdout)["ok"] is False


# ------------------------------------------------------------- sjekksum-pin
def _falsk_oppsett(tmp_path, innhold=b"ikke en modell", sha=None):
    cli = _falsk_whisper(tmp_path)
    modell = tmp_path / "modell.bin"
    modell.write_bytes(innhold)
    ekte = kjerne.standard_oppsett(modellvalg="large")
    return kjerne.Oppsett("large", modell, sha or "0" * 64, len(innhold), ekte.repo,
                          cli, cli.parent / f"whisper-server{kjerne.EXE}", ekte.fasit, ekte.vokabular)


def test_sjekksum_avvik_stopper_for_noe_kjores(tmp_path, monkeypatch):
    kjort = []
    monkeypatch.setattr(kjerne, "_kjor", lambda argv: kjort.append(argv))
    lyd = tmp_path / "x.wav"
    lyd.write_bytes(b"RIFF")
    with pytest.raises(kjerne.ModellAvvik) as e:
        kjerne.transkriber(lyd, _falsk_oppsett(tmp_path))
    assert "avviker fra låst SHA256" in str(e.value)
    assert kjort == []          # verken ffmpeg eller whisper ble startet


def test_sjekksum_treff_godtas(tmp_path):
    innhold = b"riktig innhold"
    o = _falsk_oppsett(tmp_path, innhold, hashlib.sha256(innhold).hexdigest())
    assert kjerne.verifiser_modell(o.modell, o.sha256) == hashlib.sha256(innhold).hexdigest()


def test_manglende_modell_gir_en_tydelig_feil(tmp_path):
    with pytest.raises(kjerne.KjerneFeil, match="Fant ikke modellen"):
        kjerne.verifiser_modell(tmp_path / "finnes-ikke.bin", "0" * 64)


def test_cli_avvik_gir_kode_3_og_melding(tmp_path):
    cli = _falsk_whisper(tmp_path)
    modell = tmp_path / "m.bin"
    modell.write_bytes(b"feil")
    lyd = tmp_path / "x.wav"
    lyd.write_bytes(b"RIFF")
    r = subprocess.run([sys.executable, "-I", str(KJERNE / "kjerne.py"), "--modell", str(modell),
                        "--whisper", str(cli), str(lyd)], capture_output=True, text=True)
    assert r.returncode == 3
    assert "avviker fra låst SHA256" in r.stderr and r.stdout == ""


def test_vokabular_blir_prompt_uten_kommentarer():
    p = kjerne.vokabular_prompt([KJERNE / "vokabular" / "offentlig_no.txt"])
    assert p.startswith("NAV, Skatteetaten") and "#" not in p and p.endswith(".")


def test_spesialtoken_fjernes_ellers_urort():
    raa = " <|nocaptions|> Det er 30 år siden.\n <|nocaptions|>\n Ikke rør <dette>.\n"
    assert kjerne._rens(raa) == "Det er 30 år siden.\nIkke rør <dette>."


# --------------------------------------------------------------- nettverk
class Nettforsok(AssertionError):
    pass


@pytest.fixture
def ingen_nett(monkeypatch):
    """Hver socket-åpning i prosessen kaster. Negativkontroll først: vakten må
    faktisk fange stdlibs egen vei ut, ellers beviser testen ingenting."""
    def kast(*a, **k):
        raise Nettforsok(f"nettverksforsøk: {a!r}")

    class Socket(socket.socket):
        def __init__(self, *a, **k):
            kast(*a)

    monkeypatch.setattr(socket, "socket", Socket)
    for navn in ("create_connection", "getaddrinfo", "socketpair", "fromfd"):
        monkeypatch.setattr(socket, navn, kast)
    with pytest.raises(Nettforsok):
        urllib.request.urlopen("http://127.0.0.1:9/", timeout=1)
    yield


@pytest.fixture
def nettforbud_os(monkeypatch):
    """Underprosessene (ffmpeg, whisper-cli) kjøres under et nettverksforbud på
    OS-nivå. Negativkontroll: en socket-tilkobling under forbudet skal gi EPERM."""
    if not SANDBOX:
        pytest.skip("sandbox-exec finnes bare på macOS; underprosessene ikke dekket her")
    r = subprocess.run([*NETTFORBUD, sys.executable, "-c",
                        "import socket\ntry:\n socket.create_connection(('127.0.0.1', 9), 1)\n"
                        "except OSError as e: print(e.errno)"], capture_output=True, text=True)
    assert r.stdout.strip() == "1", f"forbudet virker ikke: {r.stdout!r} {r.stderr!r}"
    monkeypatch.setattr(kjerne, "PREFIKS", NETTFORBUD)
    yield


@tung
def test_nettverksfri_transkripsjon(ingen_nett, nettforbud_os):
    ut = kjerne.transkriber(TESTLYD)
    assert set(ut) == NOKLER
    assert ut["verbatim"].strip(), "tom transkripsjon"


# ------------------------------------------------------------ determinisme
@tung
def test_determinisme_tre_kjoringer():
    kjoringer = [json.dumps(kjerne.transkriber(TESTLYD), ensure_ascii=False, sort_keys=True)
                 for _ in range(3)]
    assert kjoringer[0] == kjoringer[1] == kjoringer[2]


# ---------------------------------------------------------------- resident
@tung
def test_resident_kun_loopback(monkeypatch):
    """Resident snakker med whisper-server over 127.0.0.1 og ingenting annet."""
    ekte_connect = socket.socket.connect

    def bare_loopback(self, adr):
        if adr[0] not in ("127.0.0.1", "::1"):
            raise Nettforsok(f"ikke-loopback: {adr!r}")
        return ekte_connect(self, adr)

    monkeypatch.setattr(socket.socket, "connect", bare_loopback)
    with kjerne.Resident() as r:
        if shutil.which("lsof"):
            ls = subprocess.run(["lsof", "-nP", "-a", "-p", str(r.proc.pid), "-iTCP"],
                                capture_output=True, text=True).stdout
            lyttere = [ln for ln in ls.splitlines() if "LISTEN" in ln]
            assert lyttere and all("127.0.0.1:" in ln for ln in lyttere), ls
        a = r.transkriber(TESTLYD)
    assert set(a) == NOKLER and a["verbatim"].strip()


@tung
@pytest.mark.xfail(strict=True, reason=(
    "målt 2026-10-18: gjentatte whisper_full-kall i SAMME prosess gir ikke bitidentisk "
    "tekst (reprodusert i ren whisper-cli med -f x -f x -f x, GPU og CPU; ikke fallback, "
    "ikke flash-attn, ikke prompten). Filbanen er deterministisk fordi hver kjøring er en "
    "ny prosess. strict: blir dette grønt, er oppførselen endret."))
def test_resident_gjentatte_kall_er_like():
    with kjerne.Resident() as r:
        a = r.transkriber(TESTLYD)
        b = r.transkriber(TESTLYD)
        c = r.transkriber(TESTLYD)
    assert a == b == c


# ------------------------------------------------------------------ målform
def test_malform_gir_whisper_sprakkode(rent_miljo):
    assert kjerne.standard_oppsett().sprak == "no"
    assert kjerne.standard_oppsett(malform="nn").sprak == "nn"
    assert kjerne.standard_oppsett(malform="auto").sprak == "auto"
    with pytest.raises(kjerne.KjerneFeil, match="Ukjent målform"):
        kjerne.standard_oppsett(malform="sv")


def test_nynorsk_sendes_som_l_nn_og_verifisert_sha_gjenbrukes(tmp_path, monkeypatch):
    innhold = b"modell"
    o = _falsk_oppsett(tmp_path, innhold, hashlib.sha256(innhold).hexdigest())
    o = kjerne.dataclasses.replace(o, malform="nn")
    kjort = []

    def falsk_kjor(argv):
        kjort.append([str(a) for a in argv])
        if "-of" in kjort[-1]:
            pathlib.Path(kjort[-1][kjort[-1].index("-of") + 1] + ".txt").write_text("Eg har ikkje fått svar.\n")

    monkeypatch.setattr(kjerne, "_kjor", falsk_kjor)
    lest = []
    monkeypatch.setattr(kjerne, "verifiser_modell", lambda sti, f: lest.append(sti) or f)
    lyd = tmp_path / "x.wav"
    lyd.write_bytes(b"RIFF")
    ut = kjerne.transkriber(lyd, o, sha=o.sha256)
    whisper = next(a for a in kjort if "-m" in a)
    assert whisper[whisper.index("-l") + 1] == "nn"
    assert lest == []                       # SHA-en var alt verifisert av den som kaller
    assert ut["verbatim"] == "Eg har ikkje fått svar."


# ------------------------------------------------------------ eksternt volum
def test_umontert_volum_stopper_ogsaa_via_symlenke(tmp_path):
    with pytest.raises(kjerne.KjerneFeil, match="ikke montert"):
        kjerne.krev_montert("/Volumes/norsk-tale-finnes-ikke/opptak")
    lenke = tmp_path / "modell.bin"
    lenke.symlink_to("/Volumes/norsk-tale-finnes-ikke/m.bin")
    with pytest.raises(kjerne.KjerneFeil, match="ikke montert"):
        kjerne.verifiser_modell(lenke, "0" * 64)
    assert kjerne.krev_montert(tmp_path) == pathlib.Path(os.path.realpath(tmp_path))


def test_cli_krev_montert(tmp_path):
    k = [sys.executable, "-I", str(KJERNE / "kjerne.py"), "--krev-montert"]
    assert subprocess.run([*k, str(tmp_path)]).returncode == 0
    r = subprocess.run([*k, "/Volumes/norsk-tale-finnes-ikke/x"], capture_output=True, text=True)
    assert r.returncode == 5 and "ikke montert" in r.stderr
