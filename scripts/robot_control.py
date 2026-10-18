#!/usr/bin/python3
"""Bounded manual commands for the simulated robot (not autonomous navigation)."""
import argparse
import time
import rclpy
from rclpy.signals import SignalHandlerOptions
from geometry_msgs.msg import Twist


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['forward', 'forward_left', 'back', 'left', 'right', 'stop'])
    parser.add_argument('--seconds', type=float, default=1.0)
    args = parser.parse_args()
    if not 0 < args.seconds <= 5:
        parser.error('--seconds must be greater than 0 and at most 5')
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node('roboinspect_manual_command')
    pub = node.create_publisher(Twist, '/roboinspect/cmd_vel', 10)
    moving = Twist()
    moving.linear.x = {'forward': 0.2, 'forward_left': 0.2, 'back': -0.2}.get(args.command, 0.0)
    moving.angular.z = {'left': 0.4, 'forward_left': 0.15, 'right': -0.4}.get(args.command, 0.0)
    try:
        deadline = time.monotonic() + 5
        while pub.get_subscription_count() == 0 and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        if pub.get_subscription_count() == 0:
            raise RuntimeError('No ROS bridge subscriber; start scripts/run_robot.sh first')
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            pub.publish(moving)
            rclpy.spin_once(node, timeout_sec=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        # Repeated zero commands cover discovery/transport delays on normal exit/Ctrl+C.
        for _ in range(8):
            pub.publish(Twist())
            rclpy.spin_once(node, timeout_sec=0.05)
        node.destroy_node()
        rclpy.shutdown()
    print('Finished; zero velocity sent. This is manual open-loop control.')


if __name__ == '__main__':
    main()
