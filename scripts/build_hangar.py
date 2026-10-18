#!/usr/bin/env python3
"""Generate local, asset-free hangar worlds and navigation reference points."""
import json
import copy
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SECTORS = {
    'A': {'label': 'Serwis', 'bounds': [-14, -5, -2, 10], 'color': [0.16, 0.35, 0.50, 1]},
    'B': {'label': 'Inspekcja', 'bounds': [-4, 5, -2, 10], 'color': [0.18, 0.43, 0.35, 1]},
    'C': {'label': 'Magazyn', 'bounds': [6, 14, -2, 10], 'color': [0.48, 0.34, 0.14, 1]},
}
POINTS = {f'P{i}': {'sector': sector, 'panel_xyz': [x, 8.6, 1.2],
                   'observation_pose': [x, 6.6, 1.57079632679]}
          for i, (sector, x) in enumerate([('A', -11), ('A', -7), ('B', -1), ('B', 3), ('C', 10)], 1)}
GLYPHS = {
 'A': ['01110','10001','10001','11111','10001','10001','10001'],
 'B': ['11110','10001','10001','11110','10001','10001','11110'],
 'C': ['01111','10000','10000','10000','10000','10000','01111'],
 'E': ['11111','10000','10000','11110','10000','10000','11111'],
 'S': ['01111','10000','10000','01110','00001','00001','11110'],
 'P': ['11110','10001','10001','11110','10000','10000','10000'],
 '1': ['00100','01100','00100','00100','00100','00100','01110'],
 '2': ['01110','10001','00001','00010','00100','01000','11111'],
 '3': ['11110','00001','00001','01110','00001','00001','11110'],
 '4': ['10010','10010','10010','11111','00010','00010','00010'],
 '5': ['11111','10000','10000','11110','00001','00001','11110'],
}

def sub(parent, tag, text=None, **attrs):
    element = ET.SubElement(parent, tag, attrs)
    if text is not None:
        element.text = str(text)
    return element

def box(link, name, xyz, size, color, collision=True):
    visual = sub(link, 'visual', name=name)
    sub(visual, 'pose', ' '.join(map(str, [*xyz, 0, 0, 0])))
    sub(sub(sub(visual, 'geometry'), 'box'), 'size', ' '.join(map(str, size)))
    material = sub(visual, 'material')
    rgba = ' '.join(map(str, color))
    sub(material, 'ambient', rgba)
    sub(material, 'diffuse', rgba)
    if collision:
        col = sub(link, 'collision', name=f'{name}_collision')
        sub(col, 'pose', ' '.join(map(str, [*xyz, 0, 0, 0])))
        sub(sub(sub(col, 'geometry'), 'box'), 'size', ' '.join(map(str, size)))

def model(world, name):
    m = sub(world, 'model', name=name)
    sub(m, 'static', 'true')
    return sub(m, 'link', name='body')

def solid(world, name, xyz, size, color):
    box(model(world, name), 'shape', xyz, size, color)

def text(world, value, center, scale=0.14):
    link = model(world, f'label_{value}')
    width = (len(value)*6-1)*scale
    for ci, char in enumerate(value):
        for row, bits in enumerate(GLYPHS[char]):
            for col, bit in enumerate(bits):
                if bit == '1':
                    xyz = [center[0]-width/2+(ci*6+col+0.5)*scale,
                           center[1]+(3-row)*scale, 0.023]
                    box(link, f'pixel_{ci}_{row}_{col}', xyz,
                        [scale*0.88, scale*0.88, 0.008], [0.95, 0.97, 1, 1], False)

def world_tree(blocked=False, unreachable=False):
    root = ET.Element('sdf', version='1.9')
    world = sub(root, 'world', name='roboinspect_hangar')
    physics = sub(world, 'physics', name='default', type='ignored')
    sub(physics, 'max_step_size', 0.001)
    sub(physics, 'real_time_factor', 1)
    for filename, name in [('physics', 'Physics'), ('user-commands', 'UserCommands'), ('scene-broadcaster', 'SceneBroadcaster')]:
        sub(world, 'plugin', filename=f'gz-sim-{filename}-system', name=f'gz::sim::systems::{name}')
    scene = sub(world, 'scene')
    sub(scene, 'ambient', '0.65 0.65 0.65 1')
    sub(scene, 'background', '0.12 0.15 0.20 1')
    light = sub(world, 'light', name='hangar_sun', type='directional')
    sub(light, 'pose', '0 0 15 0 0 0')
    sub(light, 'diffuse', '0.9 0.9 0.9 1')
    sub(light, 'specular', '0.2 0.2 0.2 1')
    sub(light, 'direction', '-0.3 0.2 -1')
    sub(light, 'cast_shadows', 'true')
    gui = sub(world, 'gui', fullscreen='false')
    view = sub(gui, 'plugin', filename='MinimalScene', name='Hangar')
    style = sub(view, 'gz-gui')
    sub(style, 'property', 'false', type='bool', key='showTitleBar')
    sub(style, 'property', 'docked', type='string', key='state')
    sub(view, 'engine', 'ogre2')
    sub(view, 'scene', 'scene')
    sub(view, 'camera_pose', '22 -30 30 0 0.68 2.20')
    for filename in ['GzSceneManager', 'InteractiveViewControl', 'CameraTracking']:
        plugin = sub(gui, 'plugin', filename=filename, name=filename)
        ui = sub(plugin, 'gz-gui')
        sub(ui, 'property', 'floating', type='string', key='state')
        sub(ui, 'property', 'false', type='bool', key='showTitleBar')
        sub(ui, 'property', '5', type='double', key='width')
        sub(ui, 'property', '5', type='double', key='height')
    sub(gui, 'plugin', filename='WorldControl', name='World control')
    sub(gui, 'plugin', filename='WorldStats', name='World stats')
    sub(gui, 'plugin', filename='EntityTree', name='Entity tree')
    solid(world, 'floor', [0,0,-0.15], [30,22,0.3], [0.27,0.30,0.35,1])
    for name, xyz, size in [
        ('wall_north',[0,11,1.5],[30.4,0.3,3]),
        ('wall_west',[-15,0,1.5],[0.3,22,3]),
        ('wall_east',[15,0,1.5],[0.3,22,3]),
        ('wall_south_left',[-9,-11,0.6],[12,0.3,1.2]),
        ('wall_south_right',[9,-11,0.6],[12,0.3,1.2]),
    ]:
        solid(world,name,xyz,size,[0.58,0.63,0.69,1])
    # Paint only: these floor markings must never become obstacles.
    for sector, cfg in SECTORS.items():
        x1,x2,y1,y2 = cfg['bounds']
        link = model(world,f'sector_{sector}_paint')
        box(link,'paint',[(x1+x2)/2,(y1+y2)/2,0.006],[x2-x1,y2-y1,0.008],cfg['color'],False)
        text(world,sector,[(x1+x2)/2,3.6],0.28)
    base = model(world,'base_paint')
    box(base,'pad',[-11,-7,0.007],[5,4,0.008],[0.12,0.47,0.58,1],False)
    text(world,'BASE',[-11,-7],0.13)
    lane = model(world,'lane_markings')
    for i,x in enumerate(range(-13,15,2)):
        box(lane,f'dash_{i}',[x,-4.5,0.009],[0.85,0.09,0.01],[0.95,0.75,0.2,1],False)
    for name, p in POINTS.items():
        x,y,z = p['panel_xyz']
        link = model(world, f'panel_{name}')
        box(link,'stand',[x,y,0.45],[0.16,0.18,0.9],[0.3,0.34,0.4,1])
        box(link,'frame',[x,y,z],[1.3,0.22,1.3],[0.09,0.12,0.16,1])
        box(link,'surface',[x,y-0.13,z],[1.12,0.03,1.1],[0.66,0.73,0.78,1])
        text(world,name,[x,7.9],0.09)
        mark=model(world,f'inspection_marker_{name}')
        box(mark,'spot',[x,6.6,0.01],[0.6,0.6,0.01],[0.95,0.78,0.18,1],False)
    # Workbench in A, storage in C, crates in B.
    bench=model(world,'workbench_A')
    box(bench,'top',[-11,0.4,1.0],[2.7,1.3,0.16],[0.45,0.50,0.57,1])
    for i,(x,y) in enumerate([(-12,0),(-10,0),(-12,0.8),(-10,0.8)]):
        box(bench,f'leg_{i}',[x,y,0.45],[0.12,0.12,0.9],[0.23,0.26,0.3,1])
    rack=model(world,'rack_C')
    for i,(x,y) in enumerate([(8,0),(12,0),(8,1.5),(12,1.5)]):
        box(rack,f'post_{i}',[x,y,1.2],[0.12,0.12,2.4],[0.23,0.27,0.32,1])
    for i,z in enumerate([0.25,1.25,2.25]):
        box(rack,f'shelf_{i}',[10,0.75,z],[4.2,1.7,0.12],[0.68,0.45,0.16,1])
    for i,(x,y,s) in enumerate([(0,0.2,1.1),(2,1,0.85),(12,4,0.9),(-7,0,0.75)]):
        solid(world,f'crate_{i}',[x,y,s/2],[s,s,s],[0.60,0.39,0.20,1])
    for i,x in enumerate([-14.4,14.4]):
        solid(world,f'column_{i}',[x,4,1.5],[0.45,0.45,3],[0.74,0.76,0.8,1])
    if blocked:
        # A long pallet obstructs the direct B/C cross-aisle; main southern lane remains free.
        solid(world,'scenario_blocker',[5.5,3,0.6],[1.6,4.0,1.2],[0.8,0.19,0.10,1])
    if unreachable:
        # Known negative test: B lies inside a sealed enclosure, start remains outside.
        for name, xyz, size in [
            ('west',[-1.5,-1,0.8],[0.2,3.2,1.6]),
            ('east',[1.5,-1,0.8],[0.2,3.2,1.6]),
            ('north',[0,0.5,0.8],[3.2,0.2,1.6]),
            ('south',[0,-2.5,0.8],[3.2,0.2,1.6]),
        ]:
            solid(world,f'sealed_B_{name}',xyz,size,[0.8,0.19,0.10,1])
    return root


def main():
    worlds=ROOT/'simulation/worlds'
    worlds.mkdir(parents=True,exist_ok=True)
    for scenario in ['normal', 'blocked', 'unreachable']:
        tree=ET.ElementTree(world_tree(scenario == 'blocked', scenario == 'unreachable'))
        ET.indent(tree, space='  ')
        tree.write(worlds/f'hangar_{scenario}.sdf',encoding='utf-8',xml_declaration=True)
        world = tree.getroot().find('world')
        robot = ET.parse(ROOT/'simulation/models/roboinspect/model.sdf').getroot().find('model')
        world.append(copy.deepcopy(robot))
        # Operator cameras are render-only sensors: no collision or robot mass.
        base = world.find("model[@name='roboinspect']/link[@name='base_link']")
        camera(base, 'follow_camera', '-2.8 -2.8 2.5 0 0.56 0.785398',
               '/roboinspect/cameras/follow', 640, 360, 5, 1.15)
        overhead = model(world, 'monitoring_camera')
        camera(overhead, 'overhead_camera', '0 0 23 0 1.57079632679 1.57079632679',
               '/roboinspect/cameras/overhead', 640, 480, 4, 1.35)
        sensors = sub(world, 'plugin', filename='gz-sim-sensors-system', name='gz::sim::systems::Sensors')
        sub(sensors, 'render_engine', 'ogre2')
        ET.indent(tree, space='  ')
        tree.write(worlds/f'hangar_{scenario}_robot.sdf', encoding='utf-8', xml_declaration=True)
    layout={'frame':'world','units':'meters','floor_bounds':[-15,15,-11,11],
            'base_pose':[-11,-7,0], 'sectors':SECTORS,'inspection_points':POINTS,
            'note':'World reference poses; run build_navigation_maps.py and Nav2 for navigation.'}
    (ROOT/'config/hangar.json').write_text(json.dumps(layout,indent=2,ensure_ascii=False)+'\n')
    print('Generated six hangar worlds (empty/robot) and config/hangar.json')


def camera(link, name, pose, topic, width, height, rate, fov):
    sensor = sub(link, 'sensor', name=name, type='camera')
    sub(sensor, 'pose', pose)
    sub(sensor, 'topic', topic)
    sub(sensor, 'always_on', 'true')
    sub(sensor, 'update_rate', rate)
    spec = sub(sensor, 'camera')
    sub(spec, 'horizontal_fov', fov)
    image = sub(spec, 'image')
    sub(image, 'width', width)
    sub(image, 'height', height)
    sub(image, 'format', 'R8G8B8')
    clip = sub(spec, 'clip')
    sub(clip, 'near', 0.05)
    sub(clip, 'far', 70)

if __name__=='__main__':
    main()
