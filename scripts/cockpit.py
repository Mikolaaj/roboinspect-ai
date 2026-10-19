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
from uuid import uuid4
from roboinspect.store import MissionStore
from roboinspect.mapping_runner import MappingRunner, MappingCanceled
from roboinspect.warehouse import read_selection, view, prepare_layout, persist_selection
from rendering import configure
from roboinspect.banners import decorate, assignments

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT/'artifacts/cockpit-runtime.json'


def open_operator_views(url):
    """Open both operator views from the single cockpit command."""
    webbrowser.open_new_tab(url + '/')
    webbrowser.open_new_tab(url + '/control')


def request(url, data=None, token=None):
    req = Request(url, data=None if data is None else json.dumps(data).encode(),
                  headers={'Content-Type':'application/json',**({'X-Runtime-Token':token} if token else {})})
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


class RuntimeManager:
    def __init__(self, args, start, stop_named, shutdown, token):
        self.root=ROOT
        self.log_dir=args.log_dir
        self.scenario=args.scenario
        self.args=args
        self.start=start
        self.stop_named=stop_named
        self.shutdown=shutdown
        self.token=token
        self.mode=args.mode
        self.map_path=Path(os.environ['ROBOINSPECT_MAP'])
        self.selection=read_selection(ROOT) if self.scenario == 'normal' else None
        self.warehouse=view(self.selection)
        self.world_path=Path(self.selection['world']) if self.selection else ROOT/f'simulation/worlds/hangar_{self.scenario}_robot.sdf'
        self.default_map=Path(self.selection['map']) if self.selection else ROOT/f'maps/hangar_{self.scenario}.yaml'
        if self.selection and args.map is None:
            self.map_path=self.default_map
        self.environment()
        self.generation=0
        self.stop=stop

    def environment(self):
        os.environ['ROBOINSPECT_WORLD']=str(self.world_path)
        os.environ['ROBOINSPECT_WAREHOUSE']=json.dumps(self.warehouse)
        os.environ['ROBOINSPECT_MAP']=str(self.map_path)

    def change_warehouse(self, mode, seed, canceled):
        selection=prepare_layout(mode,seed,ROOT)
        if canceled():raise MappingCanceled()
        old=(self.selection,self.warehouse,self.world_path,self.default_map,self.map_path)
        self.selection=selection
        self.warehouse=view(selection)
        self.world_path=Path(selection['world'])
        self.default_map=Path(selection['map'])
        try:
            self.switch('navigation',self.default_map)
            if canceled():raise MappingCanceled()
            persist_selection(selection,ROOT)
        except Exception:
            self.selection,self.warehouse,self.world_path,self.default_map,self.map_path=old
            if not self.shutdown.is_set():
                self.switch('navigation',self.map_path)
            raise
        return selection

    def change_pictures(self, mode, seed, canceled):
        path=ROOT/'data/vision/selection.json'
        old=path.read_text() if path.exists() else None
        previous=assignments(json.loads(old)['seed'] if old else 0)
        for _ in range(100):
            selected=assignments(seed)
            if all(selected[p]!=previous[p] for p in previous):break
            seed+=1
        else:raise RuntimeError('Nie udało się dobrać nowych zdjęć')
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'seed':seed}))
        temporary.replace(path)
        try:
            if canceled():raise MappingCanceled()
            self.switch('navigation', self.map_path)
            if canceled():raise MappingCanceled()
        except Exception:
            if old is None:path.unlink(missing_ok=True)
            else:path.write_text(old)
            if not self.shutdown.is_set():self.switch('navigation',self.map_path)
            raise
        return self.warehouse

    def write_runtime(self):
        RUNTIME.write_text(json.dumps({'pid':os.getpid(),'port':self.args.port,
            'scenario':self.scenario,'mode':self.mode,'map':str(self.map_path),
            'world':str(self.world_path),'warehouse':self.warehouse,
            'rendering':{'mode':os.environ.get('ROBOINSPECT_RENDERING'),
                         'device':os.environ.get('ROBOINSPECT_RENDER_DEVICE')},
            'gz_partition':os.environ['GZ_PARTITION'],
            'ros_domain_id':os.environ.get('ROS_DOMAIN_ID','0')})+'\n')

    def switch(self, mode, map_path):
        url=f'http://127.0.0.1:{self.args.port}'
        request(url+'/api/internal/runtime',{'mode':self.mode,'transitioning':True,
                                            'map_file':str(self.map_path)},self.token)
        for name in ['route-visualizer','navigation','slam','simulation']:
            self.stop_named(name)
        if self.shutdown.is_set():
            raise RuntimeError('Kokpit jest zamykany')
        self.generation+=1
        os.environ['GZ_PARTITION']=f'roboinspect_cockpit_{os.getpid()}_{self.generation}'
        self.mode=mode
        self.map_path=Path(map_path) if map_path else self.default_map
        os.environ['ROBOINSPECT_MODE']=mode
        self.environment()
        os.environ['ROBOINSPECT_MAP']=str(self.map_path)
        request(url+'/api/internal/runtime',{'mode':mode,'transitioning':False,
                                            'map_file':str(self.map_path),
                                            'world_file':str(self.world_path),'warehouse':self.warehouse},self.token)
        self.write_runtime()
        self.start_stack()
        deadline=time.monotonic()+60
        while not self.shutdown.wait(.3):
            state=request(url+'/api/status')
            ready=state.get('mapping_ready') if mode=='mapping' else state.get('runtime_ready')
            expected_frame='map_slam' if mode=='mapping' else 'map'
            if ready and state.get('map',{}).get('frame')==expected_frame and state.get('robot_marker'):
                return
            if time.monotonic()>deadline:
                raise RuntimeError('Nowy tryb nie uzyskał gotowości; sprawdź logi kokpitu')
        raise RuntimeError('Przełączenie przerwane przez zamknięcie kokpitu')

    def start_stack(self):
        self.start('route-visualizer',[str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/route_visualizer.py')])
        seed_file=ROOT/'data/vision/selection.json'
        banner_seed=json.loads(seed_file.read_text())['seed'] if seed_file.exists() else 0
        runtime_world,_=decorate(self.world_path,banner_seed)
        self.start('simulation',['bash',str(ROOT/'scripts/run_robot.sh'),
                     f'scenario:={self.scenario}',f'headless:={str(not self.args.gazebo_gui).lower()}',
                     f'world:={runtime_world}'])
        if self.mode=='mapping':
            self.start('slam',['/usr/bin/python3','/opt/ros/jazzy/bin/ros2','launch',
                              str(ROOT/'robotics/launch/slam.launch.py')])
        else:
            self.start('navigation',['bash',str(ROOT/'scripts/run_navigation.sh'),
                                    f'scenario:={self.scenario}',f'map:={self.map_path}'])


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
    selection=ROOT/'data/current-map.json'
    if args.mode=='navigation' and args.map is None and selection.exists():
        chosen=json.loads(selection.read_text())
        active_warehouse=read_selection(ROOT) if args.scenario=='normal' else None
        current_layout=view(active_warehouse)['layout_id']
        if chosen.get('scenario')==args.scenario and chosen.get('layout_id','standard')==current_layout and Path(chosen['map']).is_file():
            args.map=Path(chosen['map'])
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
            print('Kokpit działa lub nadal się zamyka. Poczekaj na zakończenie: bash scripts/stop_cockpit.sh',file=sys.stderr)
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
        token=uuid4().hex
        graphics_env['ROBOINSPECT_RUNTIME_TOKEN']=token
        os.environ.clear()
        os.environ.update(graphics_env)
        print(f"Renderowanie: {graphics['mode'].upper()} · {graphics['device']}",flush=True)
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
        def stop_named(name):
            for item in list(processes):
                if item[0]==name:
                    stop(item[1])
                    processes.remove(item)
        database=os.environ.get('ROBOINSPECT_DATABASE_URL',f'sqlite:///{ROOT / "data/missions.sqlite3"}')
        store=MissionStore(database)
        store.interrupt_operations()
        manager=RuntimeManager(args,start,stop_named,shutdown,token)
        runner=MappingRunner(manager,store)
        try:
            ollama=ROOT/'data/ollama-runtime/bin/ollama'
            if ollama.exists():
                os.environ.update(OLLAMA_HOST='127.0.0.1:11435',
                    OLLAMA_MODELS=str(ROOT/'data/ollama-models'),
                    OLLAMA_MAX_LOADED_MODELS='1', OLLAMA_NUM_PARALLEL='1',
                    OLLAMA_CONTEXT_LENGTH='4096', OLLAMA_NO_CLOUD='true')
                start('ollama',[str(ollama),'serve'])
                if (ROOT/'data/rag/index.json').exists():
                    saved_host=os.environ['OLLAMA_HOST']
                    os.environ['OLLAMA_HOST']='127.0.0.1:11436'
                    saved_cuda=os.environ.get('CUDA_VISIBLE_DEVICES')
                    os.environ['CUDA_VISIBLE_DEVICES']='-1'
                    start('rag-embeddings',[str(ollama),'serve'])
                    os.environ['OLLAMA_HOST']=saved_host
                    if saved_cuda is None: os.environ.pop('CUDA_VISIBLE_DEVICES',None)
                    else: os.environ['CUDA_VISIBLE_DEVICES']=saved_cuda
                else:
                    print('RAG: przygotuj bash scripts/setup_rag.sh',flush=True)
            else:
                print('Czat: najpierw wykonaj bash scripts/setup_bielik.sh',flush=True)
            start('mlflow',[str(ROOT/'.venv/bin/mlflow'),'server',
                '--backend-store-uri',f'sqlite:///{ROOT / "data/mlflow.db"}',
                '--default-artifact-root',str(ROOT/'data/mlflow-artifacts'),
                '--host','127.0.0.1','--port','5001','--workers','1'])
            vision=ROOT/'data/vision/env/bin/python'
            if vision.exists() and (ROOT/'data/vision/yolo11s.pt').exists():
                os.environ['ROBOINSPECT_VISION_URL']='http://127.0.0.1:8766'
                start('vision',[str(vision),str(ROOT/'scripts/vision_worker.py'),'--operator-port',str(args.port)])
            else:
                print('Detekcja: przygotuj bash scripts/setup_vision.sh',flush=True)
            manager.start_stack()
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
                manager.write_runtime()
                print(f'\nKokpit: {url}/\nSterowanie: {url}/control\nLogi: {args.log_dir}\n'+
                      ('Tryb mapowania: steruj mapowaniem z panelu /control.\n'
                       if args.mode == 'mapping' else 'Poczekaj na trzy obrazy i zielony status Nav2.\n')+
                      'Ctrl+C w tym terminalu zamyka całość.\n',flush=True)
                if not args.no_browser:
                    threading.Thread(target=open_operator_views,args=(url,),daemon=True).start()
            while not shutdown.wait(0.5):
                runner.tick()
                failed = [(name,p.returncode) for name,p in processes if p.poll() is not None]
                if failed:
                    raise RuntimeError(f'Proces zakończył się: {failed}. Logi: {args.log_dir}')
        except Exception as exc:
            code = 1
            print(str(exc),file=sys.stderr,flush=True)
        finally:
            print('Zamykanie kokpitu…',flush=True)
            runner.close()
            try:
                request(url+'/api/cancel',{})
                deadline = time.monotonic()+4
                while time.monotonic()<deadline and request(url+'/api/status').get('busy'):
                    time.sleep(0.2)
            except (URLError,TimeoutError,ValueError,OSError):
                pass
            stop_named('operator')
            for _,proc in reversed(processes):
                stop(proc)
            for file in files:
                file.close()
            store.close()
            if RUNTIME.exists():
                try:
                    if json.loads(RUNTIME.read_text()).get('pid') == os.getpid():
                        RUNTIME.unlink()
                except (ValueError,OSError):
                    pass
        return code

if __name__ == '__main__':
    raise SystemExit(main())
