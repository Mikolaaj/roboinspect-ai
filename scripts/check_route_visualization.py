#!/usr/bin/env python3
"""Exercise real Nav2 replanning after a temporary obstacle appears on the route."""
import argparse
import json
import math
import os
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--use-active',action='store_true')
    args=parser.parse_args()
    out=ROOT/'artifacts/route-check';out.mkdir(parents=True,exist_ok=True)
    runtime=json.loads((ROOT/'artifacts/cockpit-runtime.json').read_text())
    env={**os.environ,'GZ_PARTITION':runtime['gz_partition']}
    base=f'http://127.0.0.1:{args.port}'
    def api(path='/api/status',data=None):
        req=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=5) as r:return json.load(r)
    def wait(predicate,seconds=40):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            state=api()
            if predicate(state):return state
            time.sleep(.25)
        raise RuntimeError('Timeout while checking route visualization')
    def gz(service,kind,text):
        result=subprocess.run(['gz','service','-s','/world/roboinspect_hangar/'+service,
                               '--reqtype','gz.msgs.'+kind,'--reptype','gz.msgs.Boolean',
                               '--timeout','2000','--req',text],env=env,capture_output=True,text=True,timeout=8,check=True)
        if 'data: true' not in result.stdout:raise RuntimeError(result.stdout+result.stderr)
    created=False
    report={'passed':False}
    try:
        if not args.use_active:
            api('/api/goal',{'goal':'C'})
        before=wait(lambda s:s.get('route',{}).get('status')=='live' and len(s['route']['points'])>20)
        path=before['route']['points']
        distance=0
        point=None
        for a,b in zip(path,path[1:]):
            distance+=math.dist(a,b)
            if distance>=2.0:
                point=b;break
        if point is None:raise RuntimeError('Route too short for a temporary obstacle')
        x,y=point
        sdf=f'<sdf version="1.9"><model name="route_test_obstacle"><static>true</static><pose>{x} {y} 0.4 0 0 0</pose><link name="body"><collision name="box"><geometry><box><size>0.8 0.8 0.8</size></box></geometry></collision><visual name="box"><geometry><box><size>0.8 0.8 0.8</size></box></geometry><material><ambient>0.9 0.25 0.1 1</ambient><diffuse>0.9 0.25 0.1 1</diffuse></material></visual></link></model></sdf>'
        gz('create','EntityFactory','sdf: '+json.dumps(sdf))
        created=True;started=time.monotonic()
        def replanned(state):
            route=state.get('route',{})
            boxes=state.get('observed_obstacles',[])
            observed=any(x-.6 <= (b[0]+b[1])/2 <= x+.6 and y-.6 <= (b[2]+b[3])/2 <= y+.6 for b in boxes)
            return route.get('status')=='live' and route['revision']>before['route']['revision'] and observed and min(math.dist(p,point) for p in route['points'])>.65
        after=wait(replanned,25)
        for camera in ['fpv','follow','overhead']:
            with urlopen(base+f'/api/frame/{camera}.jpg',timeout=5) as response:
                (out/f'{camera}.jpg').write_bytes(response.read())
        (out/'before.json').write_text(json.dumps(before,indent=2)+'\n')
        (out/'after.json').write_text(json.dumps(after,indent=2)+'\n')
        assert after['route_visual']['ready'] and after['route_visual']['fresh']
        report.update(passed=True,obstacle=point,replan_seconds=time.monotonic()-started,
                      before_revision=before['route']['revision'],after_revision=after['route']['revision'],
                      clearance_m=min(math.dist(p,point) for p in after['route']['points']),
                      visual=after['route_visual'])
        print(json.dumps(report,indent=2),flush=True)
    finally:
        api('/api/cancel',{})
        wait(lambda s:not s['busy'] and abs(s.get('velocity',{}).get('linear',1))<.02,20)
        if created:gz('remove','Entity','name: "route_test_obstacle" type: MODEL')
        cleared=wait(lambda s:not s['route']['points'] and s['route']['goal'] is None and s['route_visual'].get('segments_active') is False,10)
        report['cleared_after_cancel']=not cleared['route']['points']
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
