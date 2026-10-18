#!/usr/bin/env python3
"""Acceptance check against a running cockpit: real Bielik -> durable mission -> Nav2."""
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    with httpx.Client(base_url='http://127.0.0.1:8765', timeout=5, trust_env=False) as client:
        state = client.get('/api/status').json()
        if not state['ready'] or state['busy']:
            raise RuntimeError('Nav2 musi być gotowe i bez aktywnej misji')
        payload = {'text': 'Jedź do sektora A i wróć do bazy'}
        key = str(uuid4())
        first = client.post('/api/chat', json=payload, headers={'Idempotency-Key':key})
        first.raise_for_status()
        record = first.json()
        again = client.post('/api/chat', json=payload, headers={'Idempotency-Key':key})
        assert again.status_code == 200 and again.json()['id'] == record['id']
        deadline = time.monotonic()+120
        while time.monotonic()<deadline:
            row = next(r for r in client.get('/api/chat').json() if r['id']==record['id'])
            if row['status']!='pending': break
            time.sleep(1)
        assert row['status']=='answered', row
        assert row['mission_id'], row
        assert [s['target'] for s in row['mission']['steps']] == ['A','BASE'], row
        mission_id = row['mission_id']
        deadline = time.monotonic()+350
        previous = None
        while time.monotonic()<deadline:
            mission = client.get('/api/missions/'+mission_id).json()
            progress = (mission['status'], mission['message'])
            if progress != previous:
                print(progress, flush=True)
                previous = progress
            if mission['status'] not in ['queued','running','canceling','uncertain']: break
            time.sleep(1)
        assert mission['status']=='succeeded', mission
        state = client.get('/api/status').json()
        assert abs(state['velocity']['linear'])<0.02
        row = next(r for r in client.get('/api/chat').json() if r['id']==record['id'])
        assert row['mission']['status']=='succeeded'
        assert row['run_id'] and not row['tracking_error'], row
        report = {'chat_id': record['id'], 'mission_id':mission_id,
                  'run_id':row['run_id'], 'mission':mission,
                  'final_position':state.get('map_position'), 'passed':True}
        output=ROOT/'artifacts/bielik-navigation.json'
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print('PASS: Bielik -> A -> BASE -> potwierdzony wynik Nav2 i MLflow',flush=True)


if __name__=='__main__':
    main()
