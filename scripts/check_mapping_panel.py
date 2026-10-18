#!/usr/bin/python3
"""Live API acceptance of the panel's full mapping lifecycle (moves the robot)."""
import json
import math
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:8765'


def api(path='/api/status',data=None,key=None,expected=200):
    request=Request(URL+path,data=None if data is None else json.dumps(data).encode(),
                    headers={'Content-Type':'application/json',**({'Idempotency-Key':key} if key else {})})
    try:
        response=urlopen(request,timeout=8)
    except HTTPError as exc:
        response=exc
    with response:
        result=json.load(response)
        assert response.code==expected,(path,response.code,result)
        return result


def wait(predicate,seconds=90):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        state=api()
        if predicate(state):
            return state
        time.sleep(.5)
    raise RuntimeError('Timeout waiting for panel operation')


def operation(kind):
    key=str(uuid4())
    record=api('/api/mapping/'+kind,{},key,202)
    duplicate=api('/api/mapping/'+kind,{},key)
    assert record['id']==duplicate['id']
    state=wait(lambda s:(s.get('operation') or {}).get('id')==record['id'] and not s['operation_busy'],650)
    result=state['operation']
    assert result['status']=='succeeded',result
    print('PASS:',kind,result['message'],flush=True)
    return result


def main():
    start_state=api()
    assert start_state['mode']=='mapping' and start_state['mapping_ready']
    first=operation('save')
    assert Path(first['saved_map']).is_file()
    reset=operation('reset')
    assert Path(first['saved_map']).is_file(),'Reset deleted a saved version'
    key=str(uuid4())
    start=api('/api/mapping/start',{},key,202)
    assert api('/api/mapping/start',{},key)['id']==start['id']
    moving=wait(lambda s:s['mode']=='mapping' and abs(s['velocity']['linear'])>.03 and s['robot_marker'])
    before=moving['robot_marker']
    api('/api/goal',{'goal':'A'},expected=409)
    api('/api/mapping/save',{},str(uuid4()),409)
    time.sleep(2)
    after=api()['robot_marker']
    assert math.dist([before['x'],before['y']],[after['x'],after['y']])>1
    print('PASS: robot marker moves; navigation and save blocked during survey',flush=True)
    state=wait(lambda s:not s['operation_busy'],650)
    assert state['operation']['id']==start['id'] and state['operation']['status']=='succeeded',state['operation']
    survey=state['operation']
    assert any('8/8' in e['message'] for e in survey['events'])
    print('PASS: full survey completed, all 8 waypoints in durable events',flush=True)
    saved=operation('save')
    finished=operation('finish')
    state=wait(lambda s:s['ready'] and s['mode']=='navigation' and s['robot_marker'])
    assert state['map_file']==finished['saved_map']
    history=api('/api/history?limit=100')
    ids={row['id'] for row in history}
    records=[first,reset,survey,saved,finished]
    assert {r['id'] for r in records}<=ids
    assert Path(first['saved_map']).is_file()
    report={'passed':True,'operations':records,'final_marker':state['robot_marker'],
            'selected_map':state['map_file'],'history_ids':[r['id'] for r in records]}
    target=ROOT/'artifacts/mapping-panel/result.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print('PASS: finish selected saved map, Nav2 ready; all operations in history',flush=True)
    print(target,flush=True)


if __name__=='__main__':
    main()
