#!/usr/bin/python3
"""End-to-end acceptance test through the same local API as the operator buttons."""
import argparse
from io import BytesIO
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',choices=['normal','blocked','unreachable'],default='normal')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--goals',nargs='+',choices=['A','B','C','BASE','P1','P2','P3','P4','P5'])
    parser.add_argument('--existing',action='store_true',help='Use an already running cockpit')
    args = parser.parse_args()
    out = args.output_dir or ROOT/'artifacts'/f'cockpit-check-{args.scenario}'
    out.mkdir(parents=True,exist_ok=True)
    (out/'result.json').unlink(missing_ok=True)
    env = os.environ.copy()
    if not args.existing:
        env['ROS_DOMAIN_ID'] = str(100+os.getpid()%90)
        env['GZ_PARTITION'] = f'cockpit_acceptance_{os.getpid()}'
    else:
        runtime_file = ROOT/'artifacts/cockpit-runtime.json'
        if runtime_file.exists():
            runtime = json.loads(runtime_file.read_text())
            env['GZ_PARTITION'] = runtime.get('gz_partition',
                                            f"roboinspect_cockpit_{runtime['pid']}")
    url = f'http://127.0.0.1:{args.port}'
    proc, log = None,None
    report = {'passed':False,'scenario':args.scenario,'routes':[]}
    goals = json.loads((ROOT/'config/navigation-goals.json').read_text())['poses']

    def api(path='/api/status',data=None,expected=200,extra_headers=None):
        headers = {'Content-Type':'application/json',**(extra_headers or {})}
        req = Request(url+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
        try:
            response = urlopen(req,timeout=6)
        except HTTPError as exc:
            response = exc
        with response:
            result = json.load(response)
            if response.code != expected:
                raise RuntimeError(f'{path}: expected HTTP {expected}, got {response.code}: {result}')
            return result

    def wait(predicate,timeout,label):
        deadline = time.monotonic()+timeout
        while time.monotonic()<deadline:
            if proc is not None and proc.poll() is not None:
                raise RuntimeError(f'Cockpit exited unexpectedly: {proc.returncode}')
            try:
                state = api()
                if predicate(state):
                    return state
            except (URLError,TimeoutError,ConnectionError):
                pass
            time.sleep(0.4)
        raise RuntimeError(f'Timeout: {label}')

    def truth():
        data = subprocess.run(['gz','topic','-e','-t','/world/roboinspect_hangar/dynamic_pose/info',
                               '--json-output','-n','1'],env=env,capture_output=True,
                              text=True,timeout=12,check=True)
        pose = next(p for p in json.loads(data.stdout)['pose'] if p.get('name')=='roboinspect')
        return [pose['position'].get('x',0.0),pose['position'].get('y',0.0)]

    def stopped(state):
        v = state.get('velocity',{})
        return abs(v.get('linear',1))<0.02 and abs(v.get('angular',1))<0.02

    try:
        if not args.existing:
            log = (out/'launcher.log').open('w')
            proc = subprocess.Popen(['bash',str(ROOT/'scripts/run_cockpit.sh'),'--no-browser',
                                     '--scenario',args.scenario,'--port',str(args.port),
                                     '--log-dir',str(out/'processes')],cwd=ROOT,env=env,
                                    stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        state = wait(lambda s:s['ready'] and len(s['cameras'])==3 and
                     all(f['age_s']<4 for f in s['cameras'].values()),90,'startup and all cameras')
        if state['scenario'] != args.scenario:
            raise RuntimeError('Wrong simulation scenario')
        report['cameras'] = state['cameras']
        if all('sequence' in f for f in state['cameras'].values()):
            measured_at = time.monotonic()
            time.sleep(2)
            later = api()
            elapsed = time.monotonic()-measured_at
            report['camera_fps_wall'] = {name:round((later['cameras'][name]['sequence']-frame['sequence'])/elapsed,2)
                                         for name,frame in state['cameras'].items()}
            report['simulation_realtime_factor'] = round((later['simulation_s']-state['simulation_s'])/elapsed,2)
            report['camera_lag_sim_s'] = {name:round(max(0,later['simulation_s']-frame['stamp_s']),3)
                                          for name,frame in later['cameras'].items()}
            if min(report['camera_fps_wall'].values()) <= 0:
                raise RuntimeError('One of the cameras stopped updating')
        for name in ['fpv','follow','overhead']:
            with urlopen(url+f'/api/frame/{name}.jpg',timeout=5) as response:
                data = response.read()
            (out/f'{name}.jpg').write_bytes(data)
            image = Image.open(BytesIO(data))
            if max(ImageStat.Stat(image).stddev)<5:
                raise RuntimeError(f'Camera {name} is blank')
        print('PASS: startup and three rendered cameras',flush=True)
        api('/api/goal',{'goal':'INVALID'},expected=400)
        if not args.existing:
            api('/api/goal',{'goal':'A'},expected=403,extra_headers={'Host':'invalid.example'})
            api('/api/goal',{'goal':'A'},expected=415,extra_headers={'Content-Type':'text/plain'})
        api('/api/goal',{'goal':'A'},expected=403,extra_headers={'Origin':'http://example.org'})
        # Cancellation must interrupt real movement, not merely a queued goal.
        api('/api/goal',{'goal':'A'},expected=202)
        api('/api/goal',{'goal':'C'},expected=409)
        wait(lambda s: s['busy'] and (abs(s.get('velocity',{}).get('linear',0))>0.03 or
                                     abs(s.get('velocity',{}).get('angular',0))>0.1),30,'robot moving')
        api('/api/cancel',{},expected=202)
        state = wait(lambda s:not s['busy'] and s['state']=='canceled' and stopped(s),15,'cancellation and stop')
        before = truth()
        time.sleep(1)
        report['cancel_drift_m'] = math.dist(before,truth())
        if report['cancel_drift_m']>0.03:
            raise RuntimeError('Robot drifted after cancellation')
        print('PASS: duplicate rejection, moving-goal cancellation and stop',flush=True)
        route = {'normal':['A','B','P3','C','BASE'], 'blocked':['B','C','BASE'], 'unreachable':['B']}[args.scenario]
        route = args.goals or route
        for name in route:
            start = time.monotonic()
            api('/api/goal',{'goal':name},expected=202)
            print(f'RUN: {args.scenario} -> {name}',flush=True)
            state = wait(lambda s:not s['busy'] and s['state'] in ['succeeded','failed','canceled'],
                         300,f'goal {name}')
            state = wait(lambda s:stopped(s),10,'stop after navigation')
            position = truth()
            error = math.dist(position,goals[name][:2])
            report['routes'].append({'goal':name,'state':state['state'],'world_xy':position,
                                     'error_m':error,'seconds':round(time.monotonic()-start,1)})
            if args.scenario=='unreachable':
                if state['state']!='failed':
                    raise RuntimeError('Sealed B must report failure')
            elif state['state']!='succeeded' or error>0.5:
                raise RuntimeError(f'Goal {name}: {state["state"]}, world error {error:.3f} m')
            print(f'PASS: {name}, {state["state"]}, error={error:.3f} m',flush=True)
        report['final_status'] = api()
        report['passed'] = True
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        if proc is not None:
            proc.send_signal(signal.SIGINT) if proc.poll() is None else None
            try:
                proc.wait(timeout=45)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGTERM)
                proc.wait(timeout=10)
            report['launcher_exit_code'] = proc.returncode
            if proc.returncode != 0:
                report['passed'] = False
            leftovers = []
            for cmdline in Path('/proc').glob('[0-9]*/cmdline'):
                try:
                    command = cmdline.read_bytes().replace(b'\0',b' ').decode(errors='replace')
                    if command.startswith('gz sim ') and str(ROOT/'simulation/worlds') in command:
                        process_env = (cmdline.parent/'environ').read_bytes().split(b'\0')
                        if ('GZ_PARTITION='+env['GZ_PARTITION']).encode() in process_env:
                            leftovers.append(cmdline.parent.name)
                except OSError:
                    pass
            report['remaining_native_servers'] = leftovers
            if leftovers:
                report['passed'] = False
        if log:
            log.close()
        (out/'result.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        print(f'Result: {out}/result.json; passed={report["passed"]}',flush=True)
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
