#!/usr/bin/python3
"""Stop only the manager recorded by this repository's active cockpit."""
import json
import os
from pathlib import Path
import signal
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
        print('Proces kokpitu już nie istnieje.')
        return 0
    if str(ROOT/'scripts/cockpit.py').encode() not in arguments:
        raise RuntimeError('PID nie należy do tego kokpitu; nie wysłano sygnału')
    os.kill(pid,signal.SIGINT)
    for _ in range(200):
        if not runtime.exists():
            print('Kokpit i symulacja zamknięte.')
            return 0
        time.sleep(.2)
    raise RuntimeError('Zamykanie trwa zbyt długo; sprawdź logi kokpitu')

if __name__=='__main__':
    raise SystemExit(main())
