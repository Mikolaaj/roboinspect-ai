#!/usr/bin/env python3
"""Verify a real warehouse transition through the same API as the operator buttons."""
import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.request import Request,urlopen
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
MOVABLE={'workbench_A','rack_C','crate_0','crate_1','crate_2','crate_3','column_0','column_1'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['standard','clear','random'])
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args();base=f'http://127.0.0.1:{args.port}'
    def api(path='/api/status',data=None,key=None):
        request=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','Idempotency-Key':key or str(uuid4())})
        with urlopen(request,timeout=5) as response:return json.load(response)
    key=str(uuid4());job=api('/api/warehouse/'+args.mode,{},key)
    duplicate=api('/api/warehouse/'+args.mode,{},key)
    assert job['id']==duplicate['id'] and job['layout_seed']==duplicate['layout_seed']
    deadline=time.monotonic()+160
    while time.monotonic()<deadline:
        state=api();record=next(r for r in api('/api/history') if r['id']==job['id'])
        if record['status'] in ['failed','canceled','interrupted']:raise RuntimeError(record)
        if record['status']=='succeeded' and state['ready'] and len(state['cameras'])==3 and state.get('map_position'):
            break
        time.sleep(.5)
    else:raise RuntimeError('Warehouse transition timeout')
    overview=api('/api/hangar')
    assert state['warehouse']['mode']==args.mode
    assert state['warehouse']['layout_id']==overview['layout_id']
    assert not state['busy'] and abs(state['map_position']['x']+11)<.4 and abs(state['map_position']['y']+7)<.4
    runtime=json.loads((ROOT/'artifacts/cockpit-runtime.json').read_text())
    env={**os.environ,'GZ_PARTITION':runtime['gz_partition']}
    scene=subprocess.run(['gz','service','-s','/world/roboinspect_hangar/scene/info','--reqtype','gz.msgs.Empty','--reptype','gz.msgs.Scene','--timeout','3000','--req',''],env=env,capture_output=True,text=True,timeout=10,check=True)
    names=set(re.findall(r'name: "([^"]+)"',scene.stdout))
    present=sorted(MOVABLE & names)
    assert len(present)==(0 if args.mode=='clear' else 8),(present,scene.stderr)
    assert 'roboinspect' in names and 'panel_P1' in names
    out=ROOT/'artifacts/warehouse-check';out.mkdir(parents=True,exist_ok=True)
    for camera in ['fpv','follow','overhead']:
        with urlopen(base+f'/api/frame/{camera}.jpg',timeout=5) as response:
            (out/f'{args.mode}-{camera}.jpg').write_bytes(response.read())
    report={'passed':True,'mode':args.mode,'warehouse':state['warehouse'],'actual_models':present,
            'static_obstacle_boxes':len(overview['obstacles']),'operation_id':job['id'],
            'position':state['map_position'],'history':record}
    (out/f'{args.mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='history'},ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
