#!/usr/bin/env bash
set -e
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source /opt/ros/jazzy/setup.bash
for scenario in normal blocked unreachable; do
  /usr/bin/python3 "$repo_root/scripts/check_cockpit.py" --scenario "$scenario"
done
