#!/usr/bin/env python3
"""Render Nav2 telemetry in Gazebo without putting transport calls on the control executor."""
import json
import select
import subprocess
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from roboinspect.routes import clean_path, route_fingerprint, visual_message

ROOT = Path(__file__).resolve().parents[1]


class Visualizer(Node):
    def __init__(self):
        super().__init__('roboinspect_route_visualizer')
        self.route = {'points': [], 'goal': None}
        self.received = 0
        self.fingerprint = None
        self.last_send = 0
        self.client = subprocess.Popen([str(ROOT/'artifacts/bin/route_pose_client')],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       text=True, bufsize=1)
        self.status = self.create_publisher(String, '/roboinspect/route_visual_status', 1)
        self.create_subscription(String, '/roboinspect/visual_route', self.update, 1)
        self.create_timer(.4, self.tick)

    def update(self, message):
        try:
            data = json.loads(message.data)
            goal = data.get('goal')
            if goal is not None:
                if len(goal) != 2 or not all(isinstance(v,(float,int)) and abs(v)<32 for v in goal):
                    return
            points = clean_path(data.get('points', []), goal) if goal else []
            self.route = {'points': points, 'goal': goal}
            self.received = time.monotonic()
        except (ValueError, TypeError, KeyError):
            pass

    def tick(self):
        route = self.route if time.monotonic()-self.received < 2 else {'points': [], 'goal': None}
        fingerprint = route_fingerprint(route)
        if fingerprint == self.fingerprint and time.monotonic()-self.last_send < 2:
            return
        error = None
        try:
            if self.client.poll() is not None:
                raise RuntimeError('Proces transportu Gazebo zakończył się')
            self.client.stdin.write(visual_message(route)+'\n')
            self.client.stdin.flush()
            readable, _, _ = select.select([self.client.stdout], [], [], 2)
            if not readable or self.client.stdout.readline().strip() != 'OK':
                raise RuntimeError('Brak potwierdzenia wizualizacji Gazebo')
            self.fingerprint = fingerprint
        except (OSError, RuntimeError) as exc:
            error = str(exc)
        self.last_send = time.monotonic()
        self.status.publish(String(data=json.dumps({'ready':error is None, 'error':error,
                                                   'segments_active':len(route['points'])>1})))

    def close(self):
        if self.client.poll() is None:
            self.client.stdin.close()
            try:
                self.client.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.client.terminate()
                self.client.wait(timeout=2)


def main():
    rclpy.init()
    node=Visualizer()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():rclpy.shutdown()


if __name__=='__main__':
    main()
