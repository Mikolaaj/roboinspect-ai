#!/usr/bin/env bash
set -e
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source /opt/ros/jazzy/setup.bash
exec /usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch "$repo_root/robotics/launch/navigation.launch.py" "$@"
