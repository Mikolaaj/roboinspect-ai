#!/usr/bin/env python3
"""Rasterize the project's axis-aligned static SDF collisions into Nav2 maps.

This is a geometry-derived map, not a SLAM recording. A 2-D connectivity check
is a planning precheck, not proof that Nav2 or robot localization works.
"""
from collections import deque
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RES = 0.05
XMIN, XMAX, YMIN, YMAX = -16, 16, -12, 12
WIDTH, HEIGHT = round((XMAX-XMIN)/RES), round((YMAX-YMIN)/RES)


def pose(node):
    values = list(map(float, node.findtext('pose', '0 0 0 0 0 0').split()))
    if len(values) != 6 or any(abs(v) > 1e-9 for v in values[3:]):
        raise ValueError('Map generator only supports 6-value axis-aligned static poses')
    return values[:3]


def obstacles(world):
    boxes = []
    for model in world.findall('model'):
        if model.findtext('static') != 'true':
            raise ValueError(f'Unexpected nonstatic model: {model.get("name")}')
        mp = pose(model)
        for link in model.findall('link'):
            lp = pose(link)
            for collision in link.findall('collision'):
                cp = pose(collision)
                size = collision.findtext('geometry/box/size')
                if size is None:
                    raise ValueError('Only box collisions are supported in hangar maps')
                sx, sy, sz = map(float, size.split())
                x, y, z = (mp[i]+lp[i]+cp[i] for i in range(3))
                if z+sz/2 > 0.05:
                    boxes.append((x-sx/2,x+sx/2,y-sy/2,y+sy/2))
    return boxes


def cell(x, y):
    return math.floor((x-XMIN)/RES), math.floor((YMAX-y)/RES)


def main():
    target_dir=ROOT/'maps'
    target_dir.mkdir(exist_ok=True)
    layout=json.loads((ROOT/'config/hangar.json').read_text())
    goals={'BASE': layout['base_pose'],
           **{sector: zone['pose'] for sector, zone in layout['inspection_zones'].items()}}
    goals.update({k:v['observation_pose'] for k,v in layout['inspection_points'].items()})
    target_data={'frame_id':'map','units':'meters and radians', 'poses':goals,
                 'note':'map uses hangar world coordinates; run navigation.launch.py for AMCL map->odom'}
    (ROOT/'config/navigation-goals.json').write_text(json.dumps(target_data,indent=2)+'\n')
    for scenario in ['normal','blocked','unreachable']:
        world=ET.parse(ROOT/f'simulation/worlds/hangar_{scenario}.sdf').getroot().find('world')
        boxes=obstacles(world)
        # Keep the mapped robot workspace on the physical floor, including at the open door.
        boxes += [(XMIN,-15,YMIN,YMAX),(15,XMAX,YMIN,YMAX),
                  (XMIN,XMAX,YMIN,-11),(XMIN,XMAX,11,YMAX)]
        pixels=bytearray([254])*(WIDTH*HEIGHT)
        inflated=bytearray(WIDTH*HEIGHT)
        for occupancy, margin in [(pixels,0.0),(inflated,0.40)]:
            for x1,x2,y1,y2 in boxes:
                c1,r1=cell(x1-margin,y2+margin)
                c2,r2=cell(x2+margin,y1-margin)
                for r in range(max(0,r1),min(HEIGHT-1,r2)+1):
                    start=r*WIDTH+max(0,c1)
                    end=r*WIDTH+min(WIDTH-1,c2)+1
                    occupancy[start:end]=bytes([0 if margin==0 else 1])*(end-start)
        start=cell(*goals['BASE'][:2])
        seen=bytearray(WIDTH*HEIGHT)
        start_idx=start[1]*WIDTH+start[0]
        if inflated[start_idx]:
            raise ValueError('Base intersects conservative robot footprint')
        seen[start_idx]=1
        queue=deque([start_idx])
        while queue:
            i=queue.popleft()
            r,c=divmod(i,WIDTH)
            for dr,dc in [(1,0),(-1,0),(0,1),(0,-1)]:
                nr,nc=r+dr,c+dc
                if 0<=nr<HEIGHT and 0<=nc<WIDTH:
                    j=nr*WIDTH+nc
                    if not seen[j] and not inflated[j]:
                        seen[j]=1
                        queue.append(j)
        for name,(x,y,yaw) in goals.items():
            c,r=cell(x,y)
            reachable = 0<=c<WIDTH and 0<=r<HEIGHT and bool(seen[r*WIDTH+c])
            if scenario == 'unreachable' and name == 'B':
                if reachable:
                    raise ValueError('Negative test broken: B must be sealed off')
            elif not reachable:
                raise ValueError(f'{scenario}: unreachable goal in conservative grid: {name}')
        pgm=target_dir/f'hangar_{scenario}.pgm'
        pgm.write_bytes(f'P5\n# Generated static hangar geometry\n{WIDTH} {HEIGHT}\n255\n'.encode()+pixels)
        (target_dir/f'hangar_{scenario}.yaml').write_text(
            f'image: hangar_{scenario}.pgm\nmode: trinary\nresolution: {RES}\n'
            f'origin: [{XMIN}.0, {YMIN}.0, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n')
        print(f'{scenario}: {WIDTH}x{HEIGHT}, {RES} m/pixel; '
              + ('B intentionally unreachable' if scenario == 'unreachable'
                 else f'{len(goals)} connected goals with 0.40 m clearance margin'))
        # Standalone vector overview for documentation; this is not a Gazebo camera image.
        svg=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="720" viewBox="0 0 900 720">',
             '<rect width="900" height="720" fill="#f5f7fa"/>',
             f'<text x="40" y="30" font-family="sans-serif" font-size="22">RoboInspect · mapa geometrii ({scenario})</text>',
             '<text x="40" y="55" font-family="sans-serif" font-size="13">Schemat mapy do nawigacji; nie jest obrazem kamery ani wynikiem SLAM.</text>']
        def xy(x,y): return 50+(x-XMIN)*25,80+(YMAX-y)*25
        svg.append('<rect x="50" y="80" width="800" height="600" fill="#e1e7ed"/>')
        for sector,data in layout['sectors'].items():
            x1,x2,y1,y2=data['bounds']; x,y=xy(x1,y2)
            colors={'A':'#a7d2ed','B':'#a4ddc7','C':'#ebd09e'}
            svg.append(f'<rect x="{x}" y="{y}" width="{(x2-x1)*25}" height="{(y2-y1)*25}" fill="{colors[sector]}"/>')
            svg.append(f'<text x="{x+8}" y="{y+22}" font-family="sans-serif" font-size="18">{sector}</text>')
        for x1,x2,y1,y2 in boxes:
            x,y=xy(x1,y2)
            svg.append(f'<rect x="{x}" y="{y}" width="{(x2-x1)*25}" height="{(y2-y1)*25}" fill="#414955"/>')
        for sector,zone in layout['inspection_zones'].items():
            x,y,_=zone['pose']; w,h=zone['size']; px,py=xy(x-w/2,y+h/2)
            svg.append(f'<rect x="{px}" y="{py}" width="{w*25}" height="{h*25}" fill="#e34149" fill-opacity="0.3" stroke="#c63332"/>')
        for name,(x,y,yaw) in goals.items():
            px,py=xy(x,y)
            svg.append(f'<circle cx="{px}" cy="{py}" r="5" fill="#c63332"/><text x="{px+7}" y="{py-7}" font-family="sans-serif" font-size="13">{name}</text>')
        svg.append('</svg>')
        (target_dir/f'hangar_{scenario}_overview.svg').write_text('\n'.join(svg)+'\n')


if __name__=='__main__':
    main()
