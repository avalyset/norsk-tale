#!/usr/bin/env python3
"""norsk-tale — vakthund for tunge kjøringer (whisper) ved siden av andre jobber.

Kjører én kommando med `nice -n 19` og sjekker hvert 5. sekund:

  minne  samme mål som norregels run_v2.sh (memory_guard):
           memory_pressure -Q | grep -i 'free percentage' → siste heltall
         under --min-minne prosent (standard 20) → avbryt
  disk   ledig plass på intern disk (/System/Volumes/Data, ellers /)
         under --min-disk-gib (standard 10) → avbryt
  swap   brukt swap (sysctl vm.swapusage, «used») økt mer enn --maks-swap-okning-mb
         (standard 1024) siden kjøringen startet → avbryt

Avbrudd stopper hele prosessgruppen til kommandoen (SIGTERM, så SIGKILL etter
5 s) og logges med tidspunkt og målt verdi. Hver sjekk logges også. Vakten rører
ingen andre prosesser.

  vakt.py --logg /Volumes/Vault/norsk-tale/vakt.log -- whisper-cli -ng -t 4 ...
"""
import argparse
import datetime
import os
import re
import shutil
import signal
import subprocess
import sys
import time

INTERN = "/System/Volumes/Data" if os.path.isdir("/System/Volumes/Data") else "/"


def ledig_minne_prosent():
    """Nøyaktig som run_v2.sh: linja med «free percentage», siste tall i den."""
    try:
        ut = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    linje = next((l for l in ut.splitlines() if "free percentage" in l.lower()), "")
    tall = re.findall(r"[0-9]+", linje)
    return int(tall[-1]) if tall else None


def ledig_disk_gib(sti=INTERN):
    return shutil.disk_usage(sti).free / 2**30


def brukt_swap_mb():
    """«used» fra sysctl vm.swapusage, i MB. None hvis det ikke kan leses."""
    try:
        ut = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"used\s*=\s*([0-9.]+)([MG])", ut)
    if not m:
        return None
    return float(m.group(1)) * (1024 if m.group(2) == "G" else 1)


def tid():
    return datetime.datetime.now().isoformat(timespec="seconds")


def kjor(argv, logg, min_minne=20, min_disk_gib=10.0, intervall=5.0, maks_swap_okning_mb=1024.0,
         maal_minne=ledig_minne_prosent, maal_disk=ledig_disk_gib, maal_swap=brukt_swap_mb):
    """Returnerer (kode, grunn). grunn er None når kommandoen gikk ferdig selv."""
    def skriv(tekst):
        with open(logg, "a", encoding="utf-8") as fh:
            fh.write(f"{tid()} {tekst}\n")

    # Sjekk før start: ingenting startes hvis grensene alt er brutt.
    m, d, swap0 = maal_minne(), maal_disk(), maal_swap()
    if m is None or swap0 is None:
        skriv(f"STOPP før start: mangler måling (minne {m}, swap {swap0})")
        return 3, "måling mangler"
    if m < min_minne or d < min_disk_gib:
        skriv(f"STOPP før start: minne {m} % (grense {min_minne}), disk {d:.1f} GiB (grense {min_disk_gib})")
        return 3, "grense brutt før start"
    skriv(f"START minne {m} % disk {d:.1f} GiB swap {swap0:.0f} MB: {' '.join(argv)}")
    p = subprocess.Popen(["nice", "-n", "19", *argv], start_new_session=True)
    grunn = None
    while p.poll() is None:
        time.sleep(intervall)
        if p.poll() is not None:
            break
        m, d, swap = maal_minne(), maal_disk(), maal_swap()
        okning = None if swap is None else swap - swap0
        skriv(f"sjekk minne {m} % disk {d:.1f} GiB swap {swap if swap is None else round(swap)} MB"
              f" (+{okning if okning is None else round(okning)} MB)")
        if m is None or m < min_minne:
            grunn = f"minne {m} % < {min_minne} %"
        elif d < min_disk_gib:
            grunn = f"disk {d:.1f} GiB < {min_disk_gib} GiB"
        elif okning is None or okning > maks_swap_okning_mb:
            grunn = f"swap økt {okning if okning is None else round(okning)} MB > {maks_swap_okning_mb:.0f} MB siden start"
        if grunn:
            skriv(f"AVBRYTER: {grunn}")
            try:
                os.killpg(p.pid, signal.SIGTERM)
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            except ProcessLookupError:
                pass
            break
    kode = p.wait()
    skriv(f"SLUTT kode {kode}" + (f" (avbrutt: {grunn})" if grunn else ""))
    return kode, grunn


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--logg", required=True)
    ap.add_argument("--min-minne", type=int, default=20)
    ap.add_argument("--min-disk-gib", type=float, default=10.0)
    ap.add_argument("--intervall", type=float, default=5.0)
    ap.add_argument("--maks-swap-okning-mb", type=float, default=1024.0)
    ap.add_argument("kommando", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    kommando = a.kommando[1:] if a.kommando[:1] == ["--"] else a.kommando
    if not kommando:
        ap.error("kommando mangler")
    kode, grunn = kjor(kommando, a.logg, a.min_minne, a.min_disk_gib, a.intervall, a.maks_swap_okning_mb)
    if grunn:
        print(f"vakt: avbrutt ({grunn}), se {a.logg}", file=sys.stderr)
        return 4
    return kode


if __name__ == "__main__":
    sys.exit(main())
