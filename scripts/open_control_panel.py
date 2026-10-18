#!/usr/bin/python3
"""Open controls for the running cockpit without starting a second ROS stack."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen
import webbrowser

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int)
    args = parser.parse_args()
    try:
        port = args.port
        if port is None:
            runtime = Path(__file__).resolve().parents[1]/'artifacts/cockpit-runtime.json'
            port = json.loads(runtime.read_text())['port']
        if not isinstance(port,int) or not 1024 <= port <= 65535:
            raise ValueError('Nieprawidłowy port')
        url = f'http://127.0.0.1:{port}'
        with urlopen(url+'/api/status',timeout=3) as response:
            if json.load(response).get('service') != 'roboinspect':
                raise ValueError('To nie jest serwer RoboInspect')
    except (OSError,ValueError,KeyError) as exc:
        print(f'Najpierw uruchom bash scripts/run_cockpit.sh. Szczegóły: {exc}')
        return 1
    print(url+'/control')
    webbrowser.open(url+'/control')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
