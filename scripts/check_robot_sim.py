#!/usr/bin/python3
"""Isolated integration test: real simulated sensors, short drive, and stop."""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    artifacts = ROOT / 'artifacts/robot-smoke'
    artifacts.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['ROS_DOMAIN_ID'] = str(100 + os.getpid() % 90)
    env['GZ_PARTITION'] = f'roboinspect_smoke_{os.getpid()}'
    log = (artifacts / 'gazebo.log').open('w')
    proc = subprocess.Popen(['bash', str(ROOT / 'scripts/run_robot.sh'), 'headless:=true'], cwd=ROOT,
                            env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    report = {'passed': False}

    def status(image=False):
        cmd = ['/usr/bin/python3', str(ROOT / 'scripts/robot_status.py'), '--timeout', '25']
        if image:
            cmd += ['--image', str(artifacts / 'camera.png')]
        res = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=35)
        if res.returncode:
            raise RuntimeError(f'Sensor check failed: {res.stdout}\n{res.stderr}')
        return json.loads(res.stdout)

    try:
        report['before'] = status(image=True)
        res = subprocess.run(['/usr/bin/python3', str(ROOT / 'scripts/robot_control.py'), 'forward', '--seconds', '1.5'],
                             cwd=ROOT, env=env, capture_output=True, text=True, timeout=12)
        if res.returncode:
            raise RuntimeError(f'Command failed: {res.stdout}\n{res.stderr}')
        report['after'] = status()
        before, after = report['before']['odom_xy'], report['after']['odom_xy']
        distance = math.dist(before, after)
        report['displacement_m'] = distance
        if not 0.10 < distance < 0.70:
            raise RuntimeError(f'Unexpected forward displacement: {distance}')
        time.sleep(0.7)
        report['stopped'] = status()
        report['stop_drift_m'] = math.dist(after, report['stopped']['odom_xy'])
        if report['stop_drift_m'] > 0.025 or abs(report['stopped']['velocity']['linear']) > 0.02:
            raise RuntimeError('Robot did not remain stopped')
        report['passed'] = True
        print(json.dumps(report, indent=2), flush=True)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        try:
            # ROS launch propagates SIGINT to its children itself.
            # Sending to the whole group would interrupt Gazebo twice.
            proc.send_signal(signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
        log.close()
        report['launch_exit_code'] = proc.returncode
        log_text = (artifacts / 'gazebo.log').read_text(errors='replace')
        report['shutdown_needed_sigterm'] = 'escalating to' in log_text
        report['shutdown_segfault'] = 'Segmentation fault' in log_text
        (artifacts / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'Artifacts: {artifacts}', flush=True)


if __name__ == '__main__':
    main()
