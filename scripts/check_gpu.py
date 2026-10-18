#!/usr/bin/python3
"""Verify the live cockpit uses NVIDIA, with fresh cameras and a real GPU process."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    def status():
        with urlopen(f'http://127.0.0.1:{args.port}/api/status',timeout=5) as response:
            return json.load(response)
    before=status()
    if not before['ready'] or before.get('rendering',{}).get('mode')!='gpu':
        raise RuntimeError('Start the cockpit with --rendering gpu and wait until ready')
    raw=subprocess.run(['nvidia-smi','-q','-x'],capture_output=True,text=True,check=True,timeout=8).stdout
    xml=ET.fromstring(raw)
    matches=[]
    for gpu in xml.findall('gpu'):
        for process in gpu.findall('processes/process_info'):
            pid=process.findtext('pid')
            try:
                command=Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
                if command.startswith('gz sim ') and str(ROOT/'simulation/worlds') in command:
                    matches.append({'pid':int(pid),'device':gpu.findtext('product_name'),
                                    'memory':process.findtext('used_memory'),
                                    'type':process.findtext('type')})
            except OSError:
                pass
    if not matches:
        raise RuntimeError('No Gazebo process found on NVIDIA GPU')
    renderer_log=Path.home()/'.gz/rendering/ogre.log'
    renderer=[line.strip() for line in renderer_log.read_text(errors='replace').splitlines() if 'GL_RENDERER =' in line]
    if not renderer or 'NVIDIA' not in renderer[-1]:
        raise RuntimeError('OpenGL log does not confirm NVIDIA renderer')
    started=time.monotonic()
    time.sleep(5)
    after=status()
    elapsed=time.monotonic()-started
    fps={name:round((after['cameras'][name]['sequence']-frame['sequence'])/elapsed,2)
         for name,frame in before['cameras'].items()}
    if len(fps)!=3 or min(fps.values())<=0 or not after['ready']:
        raise RuntimeError('Cameras or navigation stopped during GPU check')
    report={'passed':True,'rendering':after['rendering'],'opengl_renderer':renderer[-1],
            'nvidia_gazebo_processes':matches,'camera_fps_wall':fps,
            'realtime_factor':round((after['simulation_s']-before['simulation_s'])/elapsed,2),
            'physics_and_ros':'CPU'}
    target=ROOT/'artifacts/gpu-check'
    target.mkdir(parents=True,exist_ok=True)
    (target/'nvidia-smi.xml').write_text(raw)
    (target/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    main()
