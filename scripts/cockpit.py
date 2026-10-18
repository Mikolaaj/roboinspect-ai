#!/usr/bin/python3
"""Own and stop the local Gazebo, Nav2 and operator server processes."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
import webbrowser
from rendering import configure

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT/'artifacts/cockpit-runtime.json'


def request(url, data=None):
    req = Request(url, data=None if data is None else json.dumps(data).encode(),
                  headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=3) as response:
        return json.load(response)


def stop(proc):
    # gz's Ruby launcher can exit while its native server remains alive.
    # Remember descendants before asking ROS launch to shut down.
    descendants = {}
    parents = {}
    for entry in Path('/proc').glob('[0-9]*'):
        try:
            fields = (entry/'stat').read_text().rsplit(')',1)[1].split()
            parents[int(entry.name)] = (int(fields[1]),fields[19])
        except (OSError,ValueError,IndexError):
            pass
    owned = {proc.pid}
    while True:
        children = {pid for pid,(parent,_) in parents.items() if parent in owned}
        if children <= owned:
            break
        owned.update(children)
    descendants = {pid:parents[pid][1] for pid in owned-{proc.pid} if pid in parents}
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
    for sig in (signal.SIGTERM,signal.SIGKILL):
        for pid,started in descendants.items():
            try:
                fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
                if fields[19] == started and fields[0] != 'Z':
                    os.kill(pid,sig)
            except (ProcessLookupError,FileNotFoundError):
                pass
        if sig == signal.SIGTERM:
            time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['navigation','mapping'], default='navigation')
    parser.add_argument('--map', type=Path, help='Saved SLAM YAML for navigation')
    parser.add_argument('--scenario',choices=['normal','blocked','unreachable'],default='normal')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--rendering',choices=['auto','gpu','cpu'],default=None)
    parser.add_argument('--gazebo-gui',action='store_true',help='Also open the Gazebo editor')
    parser.add_argument('--log-dir',type=Path,default=ROOT/'artifacts/cockpit')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('--port must be between 1024 and 65535')
    if args.mode == 'mapping' and args.map:
        parser.error('--map is only for navigation; mapping always starts a fresh map')
    if args.map and not args.map.expanduser().is_file():
        parser.error('Map file not found; save it in mapping mode first')
    environment = ROOT/'.venv/bin/python'
    if not environment.exists():
        print('Najpierw uruchom: bash scripts/setup_project.sh', file=sys.stderr)
        return 1
    preflight = subprocess.run([str(environment), '-c',
                               'import roboinspect.api, rclpy, uvicorn'],
                              capture_output=True, text=True)
    if preflight.returncode:
        print('Brak zależności API. Uruchom: bash scripts/setup_project.sh\n'+preflight.stderr,
              file=sys.stderr)
        return 1
    (ROOT/'artifacts').mkdir(exist_ok=True)
    with (ROOT/'artifacts/cockpit.lock').open('w') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('Kokpit już działa. Otwórz jego adres lub zatrzymaj go przez Ctrl+C.',file=sys.stderr)
            return 1
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1',args.port))
            except OSError:
                print(f'Port {args.port} jest zajęty. Użyj --port INNY_PORT.',file=sys.stderr)
                return 1
        try:
            from PIL import Image  # noqa: F401
            from ament_index_python.packages import get_package_share_directory
            packages = ['nav2_bringup','ros_gz_bridge','ros_gz_sim']
            if args.mode == 'mapping':
                packages.append('slam_toolbox')
            for package in packages:
                get_package_share_directory(package)
        except (ImportError,LookupError) as exc:
            print(f'Brak zależności: {exc}. Zobacz docs/cockpit.md.',file=sys.stderr)
            return 1
        try:
            graphics_env, graphics = configure(args.rendering)
        except (ValueError,RuntimeError) as exc:
            print(str(exc),file=sys.stderr)
            return 1
        graphics_env['ROBOINSPECT_MODE'] = args.mode
        graphics_env['ROBOINSPECT_MAP'] = str(args.map.expanduser().resolve()) if args.map else str(ROOT/f'maps/hangar_{args.scenario}.yaml')
        os.environ.clear()
        os.environ.update(graphics_env)
        print(f"Renderowanie: {graphics['mode'].upper()} — {graphics['device']}",flush=True)
        shutdown = threading.Event()
        # Separate runs must never discover native Gazebo servers left by another
        # shell/session. Acceptance tests supply their own partition explicitly.
        os.environ.setdefault('GZ_PARTITION',f'roboinspect_cockpit_{os.getpid()}')
        signal.signal(signal.SIGINT,lambda *_:shutdown.set())
        signal.signal(signal.SIGTERM,lambda *_:shutdown.set())
        processes, files = [],[]
        args.log_dir.mkdir(parents=True,exist_ok=True)
        url = f'http://127.0.0.1:{args.port}'
        code = 0
        def start(name,command):
            log = (args.log_dir/f'{name}.log').open('w')
            files.append(log)
            proc = subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                                    start_new_session=True)
            processes.append((name,proc))
        try:
            start('simulation',['bash',str(ROOT/'scripts/run_robot.sh'),
                                f'scenario:={args.scenario}',
                                f'headless:={str(not args.gazebo_gui).lower()}'])
            if args.mode == 'mapping':
                start('slam',['/usr/bin/python3','/opt/ros/jazzy/bin/ros2','launch',
                              str(ROOT/'robotics/launch/slam.launch.py')])
            else:
                start('navigation',['bash',str(ROOT/'scripts/run_navigation.sh'),
                                    f'scenario:={args.scenario}',
                                    'map:='+os.environ['ROBOINSPECT_MAP']])
            start('operator',[str(ROOT/'.venv/bin/python'),str(ROOT/'operator/server.py'),
                              '--port',str(args.port),'--scenario',args.scenario])
            deadline = time.monotonic()+30
            while not shutdown.is_set():
                failed = [(name,p.returncode) for name,p in processes if p.poll() is not None]
                if failed:
                    raise RuntimeError(f'Proces zakończył się przedwcześnie: {failed}. Logi: {args.log_dir}')
                try:
                    status = request(url+'/api/status')
                    if status.get('service') == 'roboinspect':
                        break
                except (URLError,TimeoutError,ValueError,OSError):
                    pass
                if time.monotonic()>deadline:
                    raise RuntimeError('Serwer kokpitu nie uruchomił się w 30 s')
                shutdown.wait(0.3)
            if not shutdown.is_set():
                RUNTIME.write_text(json.dumps({'pid':os.getpid(),'port':args.port,
                                              'scenario':args.scenario,'rendering':graphics,
                                              'gz_partition':os.environ['GZ_PARTITION'],
                                              'mode':args.mode,'map':os.environ['ROBOINSPECT_MAP'],
                                              'ros_domain_id':os.environ.get('ROS_DOMAIN_ID','0')})+'\n')
                print(f'\nKokpit: {url}/\nSterowanie: {url}/control\nLogi: {args.log_dir}\n'+
                      ('Tryb mapowania: uruchom bash scripts/survey_hangar.sh w drugim terminalu.\n'
                       if args.mode == 'mapping' else 'Poczekaj na trzy obrazy i zielony status Nav2.\n')+
                      'Ctrl+C w tym terminalu zamyka całość.\n',flush=True)
                if not args.no_browser:
                    threading.Thread(target=webbrowser.open,args=(url+'/',),daemon=True).start()
            while not shutdown.wait(0.5):
                failed = [(name,p.returncode) for name,p in processes if p.poll() is not None]
                if failed:
                    raise RuntimeError(f'Proces zakończył się: {failed}. Logi: {args.log_dir}')
        except Exception as exc:
            code = 1
            print(str(exc),file=sys.stderr,flush=True)
        finally:
            print('Zamykanie kokpitu…',flush=True)
            try:
                request(url+'/api/cancel',{})
                deadline = time.monotonic()+4
                while time.monotonic()<deadline and request(url+'/api/status').get('busy'):
                    time.sleep(0.2)
            except (URLError,TimeoutError,ValueError,OSError):
                pass
            for _,proc in reversed(processes):
                stop(proc)
            for file in files:
                file.close()
            if RUNTIME.exists():
                try:
                    if json.loads(RUNTIME.read_text()).get('pid') == os.getpid():
                        RUNTIME.unlink()
                except (ValueError,OSError):
                    pass
        return code

if __name__ == '__main__':
    raise SystemExit(main())
