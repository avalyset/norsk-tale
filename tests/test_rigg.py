"""Kalibreringsriggen: sikkerhetsgrenser, livsløp, lagring og eksportformat.

Ingen modell kjøres her. Opptakstesten bruker en generert tone (ffmpeg lavfi),
som bare prøver lagring og konvertering — ikke tale og ikke ASR."""
import http.client, json, os, pathlib, re, shutil, subprocess, sys, time
import pytest

ROT = pathlib.Path(__file__).resolve().parents[1]
RIGG = ROT / "kalibrering" / "rigg.py"
sys.path.insert(0, str(ROT / "kalibrering"))
sys.path.insert(0, str(ROT / "kjerne"))
import rigg as riggmod  # noqa: E402

SANDBOX = shutil.which("sandbox-exec") if sys.platform == "darwin" else None
FFMPEG = shutil.which("ffmpeg")


def start(tmp_path, *ekstra, prefiks=()):
    p = subprocess.Popen([*prefiks, sys.executable, "-I", str(RIGG), "--opptak", str(tmp_path / "opptak"), *ekstra],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    klar = json.loads(p.stdout.readline())
    m = re.match(r"http://127\.0\.0\.1:(\d+)/([^/]+)/$", klar["url"])
    assert m, klar
    return p, int(m.group(1)), m.group(2)


@pytest.fixture
def server(tmp_path):
    p, port, token = start(tmp_path)
    yield p, port, token, tmp_path / "opptak"
    if p.poll() is None:
        p.kill()
        p.wait()


def kall(port, metode, sti, kropp=None, hoder=None, vert=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = {"Host": vert or f"127.0.0.1:{port}"}
    h.update(hoder or {})
    c.request(metode, sti, body=kropp, headers=h)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r, data


def opphav(port):
    return {"Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"}


# ---------------------------------------------------------------- token
def test_uten_eller_med_feil_token_er_404(server):
    _, port, token, _ = server
    assert kall(port, "GET", "/")[0].status == 404
    assert kall(port, "GET", "/api/oppsett")[0].status == 404
    assert kall(port, "GET", "/" + "x" * len(token) + "/")[0].status == 404
    r, data = kall(port, "GET", f"/{token}/")
    assert r.status == 200 and b"Kalibrer for din stemme" in data


def test_feil_host_avvises(server):
    _, port, token, _ = server
    r, _ = kall(port, "GET", f"/{token}/api/oppsett", vert=f"angriper.example:{port}")
    assert r.status == 403


def test_post_krever_riktig_origin(server):
    _, port, token, _ = server
    kropp = json.dumps({"modus": "dialekt"})
    assert kall(port, "POST", f"/{token}/api/runde", kropp, {"Content-Type": "application/json"})[0].status == 403
    assert kall(port, "POST", f"/{token}/api/runde", kropp,
                {"Origin": "https://angriper.example", "Content-Type": "application/json"})[0].status == 403
    r, data = kall(port, "POST", f"/{token}/api/runde", kropp, opphav(port))
    assert r.status == 200 and json.loads(data)["modus"] == "dialekt"


def test_ingen_cors_og_streng_csp(server):
    _, port, token, _ = server
    r, _ = kall(port, "GET", f"/{token}/")
    assert r.getheader("Access-Control-Allow-Origin") is None
    csp = r.getheader("Content-Security-Policy")
    assert "default-src 'none'" in csp and "connect-src 'self'" in csp
    assert r.getheader("Cache-Control") == "no-store"


@pytest.mark.skipif(not shutil.which("lsof"), reason="lsof mangler")
def test_lytter_bare_paa_loopback(server):
    p, port, _, _ = server
    ut = subprocess.run(["lsof", "-nP", "-a", "-p", str(p.pid), "-iTCP", "-sTCP:LISTEN"],
                        capture_output=True, text=True).stdout
    lyttere = [ln for ln in ut.splitlines() if "LISTEN" in ln]
    assert lyttere and all(f"127.0.0.1:{port}" in ln for ln in lyttere), ut


# ------------------------------------------------------------- nettverk
@pytest.mark.skipif(not SANDBOX, reason="sandbox-exec finnes bare på macOS")
def test_virker_under_forbud_mot_utgaaende_nett(tmp_path):
    """Riggen trenger ingen utgående forbindelser. Negativkontroll: forbudet
    stopper en utgående tilkobling fra en prosess i samme profil."""
    profil = ["sandbox-exec", "-p", "(version 1)(allow default)(deny network-outbound (remote ip))"]
    kontroll = subprocess.run([*profil, sys.executable, "-c",
                               "import socket\ntry:\n socket.create_connection(('127.0.0.1', 9), 1)\n"
                               "except OSError as e: print(e.errno)"], capture_output=True, text=True)
    assert kontroll.stdout.strip() == "1", kontroll
    p, port, token = start(tmp_path, prefiks=profil)
    try:
        r, data = kall(port, "GET", f"/{token}/api/oppsett")
        assert r.status == 200 and len(json.loads(data)["manus"]) == 100
        r, _ = kall(port, "POST", f"/{token}/api/runde", json.dumps({"modus": "fullt"}), opphav(port))
        assert r.status == 200
    finally:
        p.kill()
        p.wait()


# --------------------------------------------------------------- livsløp
def test_stopper_ved_inaktivitet(tmp_path):
    p, port, token = start(tmp_path, "--inaktiv-sekunder", "1")
    try:
        assert p.wait(timeout=10) == 0
    finally:
        if p.poll() is None:
            p.kill()


def test_avslutt_stopper_serveren(server):
    p, port, token, _ = server
    r, _ = kall(port, "POST", f"/{token}/api/avslutt", "{}", opphav(port))
    assert r.status == 200
    assert p.wait(timeout=10) == 0


# ----------------------------------------------------------------- runder
def test_dialektkilde_paakrevd_naar_region_er_satt(server):
    _, port, token, _ = server
    sti = f"/{token}/api/runde"
    r, data = kall(port, "POST", sti, json.dumps({"modus": "dialekt", "dialektregion": "Vestlandet"}), opphav(port))
    assert r.status == 400 and "påkrevd" in json.loads(data)["feil"]
    r, data = kall(port, "POST", sti, json.dumps({"modus": "dialekt", "dialektregion": "Vestlandet",
                                                  "dialektkilde": "imitert"}), opphav(port))
    assert r.status == 200 and json.loads(data)["dialektkilde"] == "imitert"
    r, _ = kall(port, "POST", sti, json.dumps({"modus": "fullt", "dialektkilde": "morsmål"}), opphav(port))
    assert r.status == 400


def test_dialektrunde_har_20_setninger_fullt_100(server):
    _, port, token, _ = server
    for modus, antall in (("dialekt", 20), ("fullt", 100)):
        _, data = kall(port, "POST", f"/{token}/api/runde", json.dumps({"modus": modus}), opphav(port))
        rid = json.loads(data)["id"]
        _, data = kall(port, "GET", f"/{token}/api/runde?runde={rid}")
        assert len(json.loads(data)["rader"]) == antall


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg mangler")
def test_opptak_lagres_som_16k_mono_og_kan_slettes(server, tmp_path):
    _, port, token, rot = server
    _, data = kall(port, "POST", f"/{token}/api/runde", json.dumps({"modus": "dialekt"}), opphav(port))
    rid = json.loads(data)["id"]
    tone = tmp_path / "tone.ogg"
    subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-ar", "48000", "-c:a", "libopus" if "libopus" in subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout else "vorbis",
                    "-strict", "-2", str(tone)], check=True)
    hoder = {"Origin": f"http://127.0.0.1:{port}", "Content-Type": "audio/ogg"}
    r, _ = kall(port, "POST", f"/{token}/api/opptak?runde={rid}&id=nb31", tone.read_bytes(), hoder)
    assert r.status == 200
    wav = rot / rid / "opptak" / "nb31.wav"
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels",
                            "-of", "csv=p=0", str(wav)], capture_output=True, text=True).stdout.strip()
    assert probe == "16000,1"
    r, data = kall(port, "GET", f"/{token}/api/opptak?runde={rid}&id=nb31")
    assert r.status == 200 and r.getheader("Content-Type") == "audio/wav" and data[:4] == b"RIFF"
    r, data = kall(port, "POST", f"/{token}/api/slett?runde={rid}", "{}", opphav(port))
    assert json.loads(data)["slettet"] == 1 and not wav.exists()


def test_ukjent_manus_id_og_runde_avvises(server):
    _, port, token, _ = server
    hoder = {"Origin": f"http://127.0.0.1:{port}", "Content-Type": "audio/ogg"}
    r, _ = kall(port, "POST", f"/{token}/api/opptak?runde=../../etc&id=nb01", b"x", hoder)
    assert r.status == 400


# -------------------------------------------------------------------- HTML
def test_siden_refererer_ingen_eksterne_ressurser():
    html = (ROT / "kalibrering" / "side.html").read_text(encoding="utf-8")
    assert not re.search(r"https?:", html, re.I), "http/https i siden"
    assert not re.search(r"""(src|href)\s*=\s*["']//""", html, re.I)
    assert "@import" not in html and "url(" not in html
    assert not re.search(r"<(script|link|img|iframe)[^>]+(src|href)=", html, re.I)


# ------------------------------------------------------- transkripsjon og eksport
def falsk_kjor(wav, oppsett, sha=None):
    tekst = {"nb31": "Helfo har ikke utbetalt de 2000 kronene ennå.",
             "nn31": "Helfo har ikkje betalt ut dei to tusen kronene enno."}.get(wav.stem, "")
    if oppsett.malform == "nb" and wav.stem == "nn31":
        tekst = "Helfo har ikke betalt ut de to tusen kronene ennå."
    return {"verbatim": tekst, "korrigert": tekst, "substitusjonslogg": [], "modell_sha256": "f" * 64, "versjon": "0"}


@pytest.fixture
def rigg_med_resultat(tmp_path, monkeypatch):
    r = riggmod.Rigg(tmp_path / "opptak", {}, inaktiv_s=60)
    runde = r.ny_runde({"modus": "dialekt", "dialektregion": "Vestlandet", "dialektkilde": "morsmål", "malform": "nn"})
    for i in ("nb31", "nn31"):
        r.wav(runde["id"], i).write_bytes(b"RIFF")
    oppsett = r.manus  # bare for å ha noe; erstattes under
    monkeypatch.setattr(riggmod.kjerne, "verifiser_modell", lambda sti, f: f)
    ekte = riggmod.kjerne.standard_oppsett(modell=str(tmp_path / "m.bin"))
    monkeypatch.setattr(riggmod.kjerne, "standard_oppsett", lambda **k: ekte)
    r.start_transkripsjon(runde["id"], kjor=falsk_kjor)
    for _ in range(100):
        if not r.jobb["kjorer"]:
            break
        time.sleep(0.05)
    assert r.jobb["feil"] is None, r.jobb
    return r, runde["id"]


def test_nn_setninger_kjores_med_baade_nb_og_nn(rigg_med_resultat):
    r, rid = rigg_med_resultat
    res = {x["manus_id"]: x for x in r.resultater(rid)["rader"]}
    assert set(res["nb31"]["varianter"]) == {"nb/med", "nb/uten"}
    assert set(res["nn31"]["varianter"]) == {"nb/med", "nb/uten", "nn/med", "nn/uten"}
    assert r.jobb["totalt"] == 6


def test_bidrag_er_bare_tall_aldri_lyd_eller_tekst(rigg_med_resultat, tmp_path):
    r, rid = rigg_med_resultat
    b = r.bidrag(rid)
    assert set(b) == {"norsk_tale_bidrag", "manus", "modell", "dialektregion", "dialektkilde",
                      "malepunkt", "malform", "n_talere", "celler"}
    assert b["dialektregion"] == "Vestlandet" and b["dialektkilde"] == "morsmål" and b["malform"] == "nn"
    tekst = json.dumps(b, ensure_ascii=False)
    for forbudt in (".wav", "RIFF", str(tmp_path), "Helfo har", "kronene", "\"utdata\"", "\"fasit\"", "\"setning\""):
        assert forbudt not in tekst, forbudt
    for c in b["celler"]:
        for k in ("n_setninger", "ord_feil", "ord_ref", "tegn_feil", "tegn_ref"):
            assert isinstance(c[k], int)
    lagret = r.lagre_bidrag(rid)
    assert pathlib.Path(lagret["fil"]).parent == tmp_path / "opptak" / "bidrag"
    assert json.loads(pathlib.Path(lagret["fil"]).read_text(encoding="utf-8")) == b


def test_rapport_skiller_malformfeil_fra_horselsfeil(rigg_med_resultat):
    r, rid = rigg_med_resultat
    rap = r.rapport(rid)
    nn = [x for x in rap["tabell"] if x["malform"] == "nn"]
    assert {x["malform_valgt"] for x in nn} == {"nb", "nn"}
    feil = {x["malform_valgt"]: x["kilder"]["morsmål"]["feil"]["målform"] for x in nn}
    assert feil == {"nb": 1, "nn": 0}
    # den lokale rapporten viser bommen ordrett; den forlater ikke maskinen
    assert any(b["type"] == "målform" and b["malform_valgt"] == "nb" for b in rap["bom"])
    html = riggmod.rapport_html(rap)
    assert "RIFF" not in html and ".wav" not in html
