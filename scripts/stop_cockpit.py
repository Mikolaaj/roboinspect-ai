#!/usr/bin/python3
"""Stop only the manager recorded by this repository's active cockpit."""
import json
import os
from pathlib import Path
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def main():
    runtime=ROOT/'artifacts/cockpit-runtime.json'
    if not runtime.exists():
        print('Brak aktywnego kokpitu.')
        return 0
    recorded=json.loads(runtime.read_text())
    pid=int(recorded['pid'])
    try:
        arguments=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    except FileNotFoundError:
        if runtime.exists() and json.loads(runtime.read_text()).get('pid') == pid:
            runtime.unlink()
        print('Proces kokpitu już nie istnieje. Usunięto stary wpis.')
        return 0
    if str(ROOT/'scripts/cockpit.py').encode() not in arguments:
        raise RuntimeError('PID nie należy do tego kokpitu; nie wysłano sygnału')
    try:
        os.kill(pid,signal.SIGINT)
    except ProcessLookupError:
        print('Proces kokpitu już się zakończył.')
        return 0
    print('Zamykanie kokpitu, symulacji, YOLO, Bielika i MLflow… Poczekaj na potwierdzenie.',flush=True)
    deadline=time.monotonic()+120
    progress=time.monotonic()+5
    while time.monotonic()<deadline:
        if not runtime.exists():
            print('Kokpit i symulacja zamknięte.')
            return 0
        if time.monotonic()>=progress:
            print('Zamykanie nadal trwa…',flush=True)
            progress=time.monotonic()+5
        time.sleep(.2)
    raise RuntimeError('Zamykanie trwa zbyt długo; sprawdź logi kokpitu')

def cli():
    try:
        return main()
    except KeyboardInterrupt:
        print('\nPrzerwano oczekiwanie. Kokpit może nadal się zamykać. '
              'Ponów: bash scripts/stop_cockpit.sh',file=sys.stderr)
        return 130
    except (RuntimeError,OSError,ValueError,KeyError) as exc:
        print(str(exc),file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(cli())
