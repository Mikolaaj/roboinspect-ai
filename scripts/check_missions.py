#!/usr/bin/python3
"""Live acceptance: sequence, duplicate request, cancellation and durable audit."""
import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    base = f'http://127.0.0.1:{args.port}'

    def api(path, data=None, key=None, expected=200):
        headers = {'Content-Type': 'application/json'}
        if key:
            headers['Idempotency-Key'] = key
        request = Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                          headers=headers)
        try:
            with urlopen(request, timeout=8) as response:
                assert response.status == expected, (response.status, expected)
                return json.load(response)
        except HTTPError as exc:
            assert exc.code == expected, (exc.code, expected, exc.read())
            return json.load(exc)

    def wait(predicate, limit=300):
        deadline = time.monotonic() + limit
        while time.monotonic() < deadline:
            state = api('/api/status')
            if predicate(state):
                return state
            time.sleep(.4)
        raise RuntimeError('Timed out waiting for mission state')

    wait(lambda s: s['ready'] and not s['busy'], 40)
    key = str(uuid4())
    payload = {'name': 'Test sekwencji A i BASE', 'steps': [{'target': 'A'}, {'target': 'BASE'}]}
    record = api('/api/missions', payload, key, 202)
    duplicate = api('/api/missions', payload, key)
    assert duplicate['id'] == record['id']
    api('/api/missions', {'steps': [{'target': 'B'}]}, expected=409)
    print('PASS: duplicate returns same mission; concurrent request rejected', flush=True)
    state = wait(lambda s: not s['busy'])
    assert state['state'] == 'succeeded', state['message']
    result = api('/api/missions/' + record['id'])
    assert [s['status'] for s in result['steps']] == ['succeeded', 'succeeded']
    events = api('/api/missions/' + record['id'] + '/events')
    assert any('1/2' in e['message'] for e in events)
    assert any('2/2' in e['message'] for e in events)
    print('PASS: A -> BASE executed in order', flush=True)
    cancel = api('/api/missions', {'name': 'Test anulowania sekwencji',
                                  'steps': [{'target': 'A'}, {'target': 'B'}, {'target': 'BASE'}]},
                 str(uuid4()), 202)
    wait(lambda s: s['busy'] and abs(s.get('velocity', {}).get('linear', 0)) > .03, 30)
    api('/api/missions/' + cancel['id'] + '/cancel', {})
    state = wait(lambda s: not s['busy'], 30)
    assert state['state'] == 'canceled'
    canceled = api('/api/missions/' + cancel['id'])
    assert [s['status'] for s in canceled['steps']] == ['canceled', 'skipped', 'skipped']
    assert abs(state['velocity']['linear']) < .02
    assert abs(state['velocity']['angular']) < .02
    report = {'passed': True, 'sequence': result, 'events': events, 'cancel': canceled}
    target = ROOT / 'artifacts/phase5-missions/result.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('PASS: canceled sequence stopped; B and BASE skipped', flush=True)
    print(target, flush=True)


if __name__ == '__main__':
    main()
