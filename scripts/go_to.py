#!/usr/bin/env python3
"""Send a named map goal to Nav2; cancel on timeout or Ctrl+C."""
import argparse
import json
import math
import time
from pathlib import Path
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus
from lifecycle_msgs.srv import GetState

def main():
    goals = json.loads((Path(__file__).resolve().parents[1] / 'config/navigation-goals.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('goal', choices=goals['poses'])
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    rclpy.init()
    node = Node('roboinspect_named_goal')
    client = ActionClient(node, NavigateToPose, '/navigate_to_pose')
    handle = None
    result = None
    try:
        state_client = node.create_client(GetState, '/bt_navigator/get_state')
        deadline = time.monotonic() + 60
        active = False
        while time.monotonic() < deadline:
            if not state_client.wait_for_service(timeout_sec=1):
                continue
            state = state_client.call_async(GetState.Request())
            rclpy.spin_until_future_complete(node, state, timeout_sec=2)
            if state.done() and state.result().current_state.id == 3:
                active = True
                break
            rclpy.spin_once(node, timeout_sec=0.5)
        if not active:
            raise RuntimeError('Nav2 did not become active within 60 seconds; check navigation logs.')
        if not client.wait_for_server(timeout_sec=10):
            raise RuntimeError('Nav2 action unavailable. Start simulation and run_navigation.sh first.')
        x,y,yaw = goals['poses'][args.goal]
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = goals['frame_id']
        # Zero stamp requests the latest available map transform.
        goal.pose.pose.position.x = float(x)
        goal.pose.pose.position.y = float(y)
        goal.pose.pose.orientation.z = math.sin(yaw/2)
        goal.pose.pose.orientation.w = math.cos(yaw/2)
        future = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, future, timeout_sec=15)
        if not future.done():
            raise RuntimeError('Goal acceptance timed out')
        handle = future.result()
        if not handle.accepted:
            raise RuntimeError('Goal rejected')
        print(f'Navigating to {args.goal}: x={x}, y={y}, yaw={yaw}', flush=True)
        result = handle.get_result_async()
        deadline = time.monotonic() + args.timeout
        while not result.done() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
        if not result.done():
            raise RuntimeError('Navigation timed out')
        status = result.result().status
        print(f'Nav2 status: {status}; result: {result.result().result}', flush=True)
        return 0 if status == GoalStatus.STATUS_SUCCEEDED else 1
    except (KeyboardInterrupt, RuntimeError) as exc:
        print(f'Stopping: {exc}', flush=True)
        return 1
    finally:
        if handle is not None and (result is None or not result.done()):
            cancel = handle.cancel_goal_async()
            rclpy.spin_until_future_complete(node, cancel, timeout_sec=5)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    raise SystemExit(main())
