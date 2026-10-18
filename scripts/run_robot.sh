#!/usr/bin/env bash
set -e
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [ ! -r /opt/ros/jazzy/setup.bash ]; then
  printf 'ROS 2 Jazzy is missing. See docs/environment.md\n' >&2
  exit 1
fi
source /opt/ros/jazzy/setup.bash
exec /usr/bin/python3 "$repo_root/scripts/launch_robot.py" "$@"
