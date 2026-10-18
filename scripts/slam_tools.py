#!/usr/bin/env python3
"""Controlled survey and map export for an active mapping cockpit."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import time
from urllib.request import urlopen

import rclpy
from geometry_msgs.msg import Twist
from tf2_ros import Buffer, TransformListener, TransformException
from rclpy.time import Time
from nav_msgs.msg import Odometry, OccupancyGrid
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy, qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan
from slam_toolbox.srv import SerializePoseGraph
from roboinspect.mapping import BASE_OFFSET, write_aligned_map

ROOT = Path(__file__).resolve().parents[1]


def angle(value):
    return math.atan2(math.sin(value), math.cos(value))


class MappingTools(Node):
    def __init__(self):
        super().__init__('roboinspect_mapping_tools')
        self.pose = None
        self.slam_at = 0
        self.grid = None
        self.velocity = (1, 1)
        self.scan = None
        self.odom_at = self.scan_at = self.clock_at = 0
        self.clock_value = None
        self.pub = self.create_publisher(Twist, '/roboinspect/cmd_vel', 10)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer,self)
        self.create_timer(.05,self.update_pose)
        self.create_subscription(Odometry, '/roboinspect/odom', self.odometry, qos_profile_sensor_data)
        self.create_subscription(LaserScan, '/roboinspect/scan', self.laser, qos_profile_sensor_data)
        self.create_subscription(Clock, '/clock', self.clock, qos_profile_sensor_data)
        self.create_subscription(OccupancyGrid, '/map', self.map_received,
                                 QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL,
                                            reliability=ReliabilityPolicy.RELIABLE))

    def map_received(self, msg):
        self.grid = msg

    def clock(self, msg):
        value = (msg.clock.sec,msg.clock.nanosec)
        if value != self.clock_value:
            self.clock_value, self.clock_at = value, time.monotonic()

    def update_pose(self):
        try:
            transform = self.tf_buffer.lookup_transform('map_slam','base_link',Time())
        except TransformException:
            return
        p,q = transform.transform.translation,transform.transform.rotation
        self.pose = (p.x,p.y,math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
        self.slam_at = time.monotonic()

    def odometry(self, msg):
        self.velocity = (msg.twist.twist.linear.x,msg.twist.twist.angular.z)
        self.odom_at = time.monotonic()

    def laser(self, msg):
        self.scan,self.scan_at = msg,time.monotonic()

    def wait_ready(self):
        deadline = time.monotonic()+40
        while time.monotonic()<deadline:
            rclpy.spin_once(self,timeout_sec=.1)
            if self.pose and self.grid and self.scan and self.clock_at:
                return
        raise RuntimeError('Brak mapy, odometrii lub lidaru. Uruchom kokpit --mode mapping.')

    def check_fresh(self):
        if any(time.monotonic()-stamp > 2 for stamp in [self.odom_at,self.scan_at,self.clock_at]):
            raise RuntimeError('Utrata lidaru/odometrii/zegara: zatrzymano przejazd')

    def stop(self):
        for _ in range(8):
            self.pub.publish(Twist())
            rclpy.spin_once(self,timeout_sec=.05)

    def survey(self):
        # A known survey itinerary, NOT exploration or a path planner. Lidar builds the map.
        waypoints = [(-8.5,-4),(-8.5,6),(6,6),(10,6),(6,6),(6,-4),(-8.5,-4),(-11,-7)]
        for index,(wx,wy) in enumerate(waypoints):
            gx,gy = wx-BASE_OFFSET[0],wy-BASE_OFFSET[1]
            deadline = time.monotonic()+120
            while True:
                rclpy.spin_once(self,timeout_sec=.04)
                self.check_fresh()
                if time.monotonic()-self.slam_at > 6:
                    raise RuntimeError('Brak aktualizacji pozycji SLAM podczas jazdy')
                x,y,yaw = self.pose
                distance = math.hypot(gx-x,gy-y)
                if distance < .23:
                    self.stop()
                    print(f'PASS: punkt {index+1}/{len(waypoints)} ({wx}, {wy})',flush=True)
                    break
                if time.monotonic()>deadline:
                    raise RuntimeError('Limit czasu punktu pomiarowego')
                heading = angle(math.atan2(gy-y,gx-x)-yaw)
                cmd = Twist()
                cmd.angular.z = max(-.8,min(.8,2*heading))
                if abs(heading)<.18:
                    rays = [r for i,r in enumerate(self.scan.ranges)
                            if abs(angle(self.scan.angle_min+i*self.scan.angle_increment))<.4
                            and math.isfinite(r) and r>=self.scan.range_min]
                    if rays and min(rays)<.65:
                        raise RuntimeError('Przeszkoda przed robotem: zatrzymano trasę pomiarową')
                    cmd.linear.x = min(.4,max(.08,.8*distance))
                self.pub.publish(cmd)
        deadline = time.monotonic()+20
        while abs(angle(self.pose[2]))>.12:
            rclpy.spin_once(self,timeout_sec=.04)
            self.check_fresh()
            if time.monotonic()>deadline:
                raise RuntimeError('Nie udało się ustawić kierunku w BASE')
            cmd=Twist()
            cmd.angular.z=max(-.6,min(.6,-2*angle(self.pose[2])))
            self.pub.publish(cmd)
        self.stop()
        print('Obchód zakończony. Zapisz mapę: bash scripts/save_slam_map.sh',flush=True)

    def save(self, prefix, overwrite):
        if max(abs(v) for v in self.velocity)>.02:
            raise RuntimeError('Przed zapisem zatrzymaj robota')
        if self.grid.header.frame_id != 'map_slam':
            raise RuntimeError('To nie jest natywna mapa aktywnego SLAM-u')
        if prefix.with_suffix('.yaml').exists() and not overwrite:
            raise RuntimeError('Mapa już istnieje. Podaj --overwrite albo inną --name.')
        prefix.parent.mkdir(parents=True,exist_ok=True)
        client=self.create_client(SerializePoseGraph,'/slam_toolbox/serialize_map')
        if not client.wait_for_service(timeout_sec=5):
            raise RuntimeError('Brak usługi zapisu grafu SLAM')
        request=SerializePoseGraph.Request()
        request.filename=str(prefix)+'-native'
        future=client.call_async(request)
        rclpy.spin_until_future_complete(self,future,timeout_sec=15)
        if not future.done() or future.result().result != 0:
            raise RuntimeError('Zapis grafu SLAM nie powiódł się')
        grid=self.grid
        p,q=grid.info.origin.position,grid.info.origin.orientation
        yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
        info=write_aligned_map(prefix,grid.data,grid.info.width,grid.info.height,
                               grid.info.resolution,(p.x,p.y,yaw))
        manifest={'source':'slam_toolbox /map, lidar only','scenario':'normal',
                  'native_frame':'map_slam','navigation_frame':'map',
                  'native_to_navigation_translation':list(BASE_OFFSET),
                  'initial_world_pose':[-11,-7,0], 'known_cells':sum(v>=0 for v in grid.data),
                  'occupied_cells':sum(v>=65 for v in grid.data),
                  'native_origin':[p.x,p.y,yaw], 'navigation_map':info,
                  'posegraph_frame':'map_slam; do not load as a world-aligned graph'}
        prefix.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(f'Zapisano: {prefix}.yaml (+ PGM, PNG, metadane i graf natywny)',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['survey','save'])
    parser.add_argument('--name',default='hangar_slam')
    parser.add_argument('--overwrite',action='store_true')
    args=parser.parse_args()
    if not args.name.replace('_','').replace('-','').isalnum():
        parser.error('--name: użyj liter, cyfr, _ lub -')
    runtime=json.loads((ROOT/'artifacts/cockpit-runtime.json').read_text())
    if runtime.get('mode') != 'mapping' or runtime['scenario'] != 'normal':
        raise RuntimeError('Uruchom: bash scripts/run_cockpit.sh --mode mapping (normal)')
    os.environ['ROS_DOMAIN_ID']=runtime.get('ros_domain_id','0')
    with urlopen(f'http://127.0.0.1:{runtime["port"]}/api/status',timeout=4) as r:
        state=json.load(r)
    if state.get('mode')!='mapping' or state.get('busy'):
        raise RuntimeError('Kokpit nie jest w bezczynnym trybie mapowania')
    (ROOT/'data').mkdir(exist_ok=True)
    with (ROOT/'data/mapping-control.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Inny przejazd lub zapis SLAM jest w toku') from None
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
        node=MappingTools()
        try:
            node.wait_ready()
            if args.command=='survey':
                if math.hypot(node.pose[0],node.pose[1])>.3 or abs(angle(node.pose[2]))>.15:
                    raise RuntimeError('Obchód musi zaczynać się w BASE, kierunek 0; uruchom nową symulację')
                node.survey()
            else:
                node.save(ROOT/'data/maps'/args.name,args.overwrite)
        except KeyboardInterrupt:
            print('Przerwano: zatrzymywanie robota.',flush=True)
            return 130
        finally:
            node.stop()
            node.destroy_node()
            rclpy.shutdown()


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from None
