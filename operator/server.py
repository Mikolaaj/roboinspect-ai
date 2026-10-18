#!/usr/bin/python3
"""Local operator UI. HTTP threads enqueue work; one ROS executor owns navigation."""
import argparse
from collections import deque
from functools import partial
from io import BytesIO
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue
import threading
import time

from PIL import Image as PILImage
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import qos_profile_sensor_data
from action_msgs.msg import GoalStatus, GoalStatusArray
from action_msgs.srv import CancelGoal
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from rclpy.executors import ExternalShutdownException
import uvicorn
from roboinspect.adapter import RosRobot
from roboinspect.api import create_app
from roboinspect.missions import MissionService
from roboinspect.store import MissionStore
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry, OccupancyGrid
from roboinspect.mapping import grid_image, BASE_OFFSET
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'operator/web'
CAMERAS = {'fpv':'/roboinspect/camera/image',
           'follow':'/roboinspect/cameras/follow',
           'overhead':'/roboinspect/cameras/overhead'}


class Operator(Node):
    def __init__(self, scenario):
        super().__init__('roboinspect_operator')
        self.goals = json.loads((ROOT/'config/navigation-goals.json').read_text())['poses']
        self.lock = threading.RLock()
        self.frames_changed = threading.Condition(self.lock)
        self.frames = {}
        self.commands = Queue(maxsize=32)
        self.events = deque(maxlen=30)
        self.state = {'scenario':scenario, 'state':'idle', 'message':'Oczekiwanie na nawigację',
                      'goal':None, 'busy':False, 'distance_m':None, 'map_position':None,
                      'rendering':{'mode':os.environ.get('ROBOINSPECT_RENDERING','unknown'),
                                   'device':os.environ.get('ROBOINSPECT_RENDER_DEVICE','unknown')}}
        self.mode = os.environ.get('ROBOINSPECT_MODE','navigation')
        self.state.update(mode=self.mode, map_file=os.environ.get('ROBOINSPECT_MAP'))
        self.map_png = None
        self.last_map = 0
        self.map_updates = 0
        self.create_subscription(OccupancyGrid, '/map', self.map_received,
                                 QoSProfile(depth=1,durability=DurabilityPolicy.TRANSIENT_LOCAL,
                                            reliability=ReliabilityPolicy.RELIABLE))
        if self.mode == 'mapping':
            self.create_subscription(PoseWithCovarianceStamped, '/pose', self.slam_position, 10)
        self.active = False
        self.last_odom = 0
        self.last_clock = 0
        self.clock_value = None
        self.goal_handle = None
        self.request_id = 0
        self.cancel_requested = False
        self.cancel_future = None
        self.goal_started = None
        self.lifecycle_future = None
        self.lifecycle = self.create_client(GetState, '/bt_navigator/get_state')
        self.nav = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.recovery = self.create_client(CancelGoal, '/navigate_to_pose/_action/cancel_goal')
        self.state.update(remote_active=False, recovery_state=None, execution_id=None)
        self.create_subscription(GoalStatusArray, '/navigate_to_pose/_action/status',
                                 self.action_status, QoSProfile(depth=1,
                                 durability=DurabilityPolicy.TRANSIENT_LOCAL,
                                 reliability=ReliabilityPolicy.RELIABLE))
        self.zero = self.create_publisher(Twist, '/roboinspect/cmd_vel', 10)
        for name, topic in CAMERAS.items():
            self.create_subscription(Image, topic, partial(self.image, name), qos_profile_sensor_data)
        self.create_subscription(Odometry, '/roboinspect/odom', self.odometry, qos_profile_sensor_data)
        self.create_subscription(Clock, '/clock', self.clock, qos_profile_sensor_data)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.position, 10)
        self.create_timer(0.05, self.process_commands)
        self.create_timer(1.0, self.monitor)

    def event(self, message):
        self.state['message'] = message
        self.events.append({'time':time.strftime('%H:%M:%S'), 'message':message})
        self.get_logger().info(message)

    def image(self, name, msg):
        try:
            modes = {'rgb8':('RGB','RGB'), 'bgr8':('RGB','BGR'),
                     'rgba8':('RGBA','RGBA'), 'bgra8':('RGBA','BGRA')}
            mode, raw = modes[msg.encoding]
            picture = PILImage.frombytes(mode, (msg.width,msg.height), bytes(msg.data),
                                         'raw', raw, msg.step, 1).convert('RGB')
            output = BytesIO()
            picture.save(output, format='JPEG', quality=80)
            with self.frames_changed:
                previous = self.frames.get(name, {})
                self.frames[name] = {'jpeg':output.getvalue(), 'time':time.monotonic(),
                                     'sequence':previous.get('sequence',0)+1,
                                     'stamp_s':msg.header.stamp.sec+msg.header.stamp.nanosec/1e9,
                                     'width':msg.width, 'height':msg.height}
                self.frames_changed.notify_all()
        except (KeyError, ValueError) as exc:
            self.get_logger().error(f'Camera {name}: {exc}')

    def map_received(self, msg):
        image = grid_image(msg.data, msg.info.width, msg.info.height)
        output = BytesIO()
        image.save(output, format='PNG')
        with self.lock:
            self.last_map = time.monotonic()
            self.map_updates += 1
            self.map_png = output.getvalue()
            self.state['map'] = {'width':msg.info.width, 'height':msg.info.height,
                                 'resolution':msg.info.resolution,
                                 'known_cells':sum(v >= 0 for v in msg.data),
                                 'occupied_cells':sum(v >= 65 for v in msg.data),
                                 'frame':msg.header.frame_id, 'updates':self.map_updates}

    def slam_position(self, msg):
        with self.lock:
            self.state['map_position'] = {'x':msg.pose.pose.position.x+BASE_OFFSET[0],
                                          'y':msg.pose.pose.position.y+BASE_OFFSET[1]}

    def odometry(self, msg):
        with self.lock:
            self.last_odom = time.monotonic()
            self.state['velocity'] = {'linear':msg.twist.twist.linear.x,
                                      'angular':msg.twist.twist.angular.z}

    def clock(self, msg):
        value = (msg.clock.sec,msg.clock.nanosec)
        with self.lock:
            if value != self.clock_value:
                self.clock_value = value
                self.last_clock = time.monotonic()

    def position(self, msg):
        with self.lock:
            self.state['map_position'] = {'x':msg.pose.pose.position.x,
                                          'y':msg.pose.pose.position.y}

    def ready(self):
        now = time.monotonic()
        return (self.active and self.nav.server_is_ready() and
                now-self.last_odom < 4 and now-self.last_clock < 4)

    def snapshot(self):
        with self.lock:
            now = time.monotonic()
            return {**self.state, 'service':'roboinspect', 'ready':self.ready(), 'goals':list(self.goals),
                    'mapping_ready':self.mode == 'mapping' and now-self.last_map < 5 and now-self.last_odom < 2 and now-self.last_clock < 2,
                    'map_age_s':None if not self.last_map else round(now-self.last_map,2),
                    'simulation_s':None if self.clock_value is None else self.clock_value[0]+self.clock_value[1]/1e9,
                    'events':list(self.events),
                    'cameras':{name:{'age_s':round(now-frame['time'],2),
                                     'sequence':frame['sequence'], 'stamp_s':frame['stamp_s'],
                                     'width':frame['width'], 'height':frame['height']}
                               for name,frame in self.frames.items()}}

    def process_commands(self):
        for _ in range(8):
            try:
                kind, data, reply, done, expires = self.commands.get_nowait()
            except Empty:
                break
            with self.lock:
                try:
                    if time.monotonic() > expires:
                        reply.update(code=503, error='Polecenie wygasło przed wykonaniem')
                    elif kind == 'goal':
                        reply.update(self.start_goal(data['target'], data['execution_id']))
                    elif kind == 'recover':
                        reply.update(self.recover())
                    else:
                        reply.update(self.cancel())
                except Exception as exc:
                    reply.update(code=500, error=str(exc))
                finally:
                    done.set()

    def start_goal(self, name, execution_id):
        if name not in self.goals:
            return {'code':400, 'error':'Nieznany cel'}
        if self.state['busy']:
            return {'code':409, 'error':'Najpierw zakończ lub anuluj bieżący przejazd'}
        if not self.ready():
            return {'code':409, 'error':'Nawigacja lub symulacja nie jest jeszcze gotowa'}
        self.request_id += 1
        identity = self.request_id
        self.cancel_requested = False
        self.cancel_future = None
        self.goal_handle = None
        self.goal_started = time.monotonic()
        self.state.update(state='dispatching',goal=name,busy=True,distance_m=None,execution_id=execution_id)
        self.event(f'Wysyłanie celu {name}')
        x,y,yaw = self.goals[name]
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.pose.position.x, goal.pose.pose.position.y = float(x), float(y)
        goal.pose.pose.orientation.z = math.sin(yaw/2)
        goal.pose.pose.orientation.w = math.cos(yaw/2)
        future = self.nav.send_goal_async(goal, feedback_callback=partial(self.feedback, identity))
        future.add_done_callback(partial(self.accepted, identity))
        return {'code':202, 'accepted':True, 'goal':name}

    def accepted(self, identity, future):
        with self.lock:
            if identity != self.request_id:
                return
            try:
                self.goal_handle = future.result()
                if not self.goal_handle.accepted:
                    self.state.update(state='failed',busy=False)
                    self.event('Nav2 odrzuciło cel')
                    return
                self.state['state'] = 'navigating'
                self.event(f"Jazda do {self.state['goal']}")
                self.goal_handle.get_result_async().add_done_callback(partial(self.finished, identity))
                if self.cancel_requested:
                    self.send_cancel()
            except Exception as exc:
                self.state.update(state='failed',busy=False)
                self.event(f'Błąd wysyłania celu: {exc}')

    def feedback(self, identity, msg):
        with self.lock:
            if identity == self.request_id:
                self.state['distance_m'] = round(msg.feedback.distance_remaining,2)

    def finished(self, identity, future):
        with self.lock:
            if identity != self.request_id:
                return
            try:
                result = future.result()
                states = {GoalStatus.STATUS_SUCCEEDED:('succeeded','Dotarł do celu'),
                          GoalStatus.STATUS_CANCELED:('canceled','Przejazd anulowany')}
                detail = result.result.error_msg.strip()
                failure = f'Przejazd nieudany: {detail}' if detail else 'Nie udało się dojechać do celu'
                state, message = states.get(result.status, ('failed',failure))
                self.state.update(state=state,busy=False,distance_m=None)
                self.event(f"{message} · {self.state['goal']}")
            except Exception as exc:
                self.state.update(state='failed',busy=False)
                self.event(f'Błąd wyniku nawigacji: {exc}')
            self.goal_handle = None
            self.cancel_future = None
            self.goal_started = None

    def cancel(self):
        if not self.state['busy']:
            return {'code':200, 'accepted':True, 'message':'Brak aktywnego przejazdu'}
        if not self.cancel_requested:
            self.cancel_requested = True
            self.state['state'] = 'canceling'
            self.event('Anulowanie przejazdu…')
        if self.goal_handle is not None:
            self.send_cancel()
        return {'code':202, 'accepted':True}

    def send_cancel(self):
        if self.cancel_future is None:
            self.state['state'] = 'canceling'
            self.cancel_future = self.goal_handle.cancel_goal_async()
            self.cancel_future.add_done_callback(partial(self.cancel_acknowledged, self.request_id))

    def cancel_acknowledged(self, identity, future):
        with self.lock:
            if identity != self.request_id:
                return
            try:
                if not future.result().goals_canceling and self.state['busy']:
                    self.event('Nav2 nie potwierdziło anulowania; oczekiwanie na wynik')
                    self.cancel_future = None
            except Exception as exc:
                self.cancel_future = None
                self.event(f'Błąd anulowania: {exc}')

    def monitor(self):
        with self.lock:
            if self.lifecycle_future is None and self.lifecycle.service_is_ready():
                self.lifecycle_future = self.lifecycle.call_async(GetState.Request())
                self.lifecycle_future.add_done_callback(self.lifecycle_result)
            if self.state['state'] == 'idle' and self.ready() and self.state['message'] == 'Oczekiwanie na nawigację':
                self.event('Gotowy do przejazdu. Wybierz cel w panelu sterowania.')
            if self.cancel_requested and self.state['busy'] and self.goal_handle and self.cancel_future is None:
                self.send_cancel()

    def action_status(self, msg):
        with self.lock:
            self.state['remote_active'] = any(item.status in (1, 2, 3) for item in msg.status_list)

    def recover(self):
        if not self.recovery.service_is_ready():
            return {'code':409, 'error':'Oczekiwanie na usługę zatrzymania Nav2'}
        self.state['recovery_state'] = 'pending'
        self.recovery.call_async(CancelGoal.Request()).add_done_callback(self.recovered)
        return {'code':202, 'accepted':True}

    def recovered(self, future):
        with self.lock:
            try:
                self.state['recovery_state'] = 'succeeded' if future.result().return_code == 0 else 'failed'
            except Exception:
                self.state['recovery_state'] = 'failed'

    def lifecycle_result(self, future):
        with self.lock:
            try:
                self.active = future.result().current_state.id == 3
            except Exception:
                self.active = False
            self.lifecycle_future = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--scenario', choices=['normal','blocked','unreachable'], default='normal')
    args = parser.parse_args()
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    operator = Operator(args.scenario)
    def spin():
        try:
            rclpy.spin(operator)
        except ExternalShutdownException:
            pass
    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    def shutdown():
        if rclpy.ok():
            for _ in range(5):
                operator.zero.publish(Twist())
                time.sleep(0.05)
            rclpy.shutdown()
        thread.join(timeout=3)
        operator.destroy_node()
    try:
        store = MissionStore(os.environ.get('ROBOINSPECT_DATABASE_URL',
                             f'sqlite:///{ROOT / "data/missions.sqlite3"}'))
        service = MissionService(store, RosRobot(operator), args.scenario,
                                 Path(os.environ.get('ROBOINSPECT_OWNER_LOCK',
                                      str(ROOT / 'data/mission-owner.lock'))))
        app = create_app(service, operator, args.port)
        uvicorn.run(app, host='127.0.0.1', port=args.port, workers=1,
                    timeout_graceful_shutdown=3, access_log=False)
    finally:
        shutdown()

if __name__ == '__main__':
    main()
