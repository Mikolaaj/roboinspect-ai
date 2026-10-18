#!/usr/bin/python3
"""Launch ROS/Gazebo with the selected GPU or CPU graphics environment."""
import os
from pathlib import Path
import sys
from rendering import configure

if __name__ == '__main__':
    try:
        env, info = configure()
    except (ValueError,RuntimeError) as exc:
        raise SystemExit(str(exc))
    print(f"Renderowanie: {info['mode'].upper()} — {info['device']}",flush=True)
    launch = Path(__file__).resolve().parents[1]/'robotics/launch/hangar_robot.launch.py'
    os.execve('/usr/bin/python3',['/usr/bin/python3','/opt/ros/jazzy/bin/ros2','launch',str(launch),*sys.argv[1:]],env)
