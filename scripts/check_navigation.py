#!/usr/bin/python3
"""Isolated real-simulation test: Nav2 startup, goal A, Gazebo ground truth and stop."""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
ROOT = Path(__file__).resolve().parents[1]

def main():
    env = os.environ.copy()
    env['ROS_DOMAIN_ID'] = str(100 + os.getpid() % 90)
    env['GZ_PARTITION'] = f'roboinspect_nav_{os.getpid()}'
    out = ROOT / 'artifacts/navigation-check'
    out.mkdir(parents=True, exist_ok=True)
    (out/'result.json').unlink(missing_ok=True)
    processes, logs = [], []
    report = {'passed':False, 'goal':'A'}
    def start(script, *args):
        log = (out / f'{script}.log').open('w')
        logs.append(log)
        proc = subprocess.Popen(['bash',str(ROOT/'scripts'/script),*args], cwd=ROOT,
                                env=env, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        processes.append(proc)
    def run(script, *args, timeout=40):
        res = subprocess.run(['/usr/bin/python3',str(ROOT/'scripts'/script),*args],
                             cwd=ROOT,env=env,capture_output=True,text=True,timeout=timeout)
        if res.returncode:
            raise RuntimeError(res.stdout + res.stderr)
        return res.stdout
    try:
        start('run_robot.sh','headless:=true')
        report['before'] = json.loads(run('robot_status.py','--timeout','30'))
        start('run_navigation.sh')
        output = run('go_to.py','A','--timeout','150',timeout=230)
        (out/'goal-A.log').write_text(output)
        time.sleep(1)
        report['after'] = json.loads(run('robot_status.py','--timeout','15'))
        report['odom_error_m'] = math.dist(report['after']['odom_xy'],[2,6])
        truth = subprocess.run(['gz','topic','-e','-t',
                                '/world/roboinspect_hangar/dynamic_pose/info',
                                '--json-output','-n','1'], env=env, capture_output=True,
                               text=True, timeout=15, check=True)
        (out/'ground-truth.json').write_text(truth.stdout)
        poses = json.loads(truth.stdout)['pose']
        pose = next(item for item in poses if item.get('name') == 'roboinspect')
        position = pose['position']
        report['world_xy'] = [position.get('x',0.0), position.get('y',0.0)]
        report['world_error_m'] = math.dist(report['world_xy'],[-9,-1])
        if report['world_error_m'] > 0.4:
            raise RuntimeError('Action succeeded but Gazebo ground truth is too far from A')
        if abs(report['after']['velocity']['linear']) > 0.02 or abs(report['after']['velocity']['angular']) > 0.02:
            raise RuntimeError('Robot is still moving after success')
        report['passed'] = True
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        for proc in reversed(processes):
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGTERM)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid,signal.SIGKILL)
                        proc.wait()
        for log in logs:
            log.close()
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)

if __name__ == '__main__':
    main()
