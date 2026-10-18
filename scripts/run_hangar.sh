#!/usr/bin/env bash
set -e
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
scenario="${1:-normal}"
if [ "$#" -gt 0 ]; then shift; fi
case "$scenario" in normal|blocked|unreachable) ;; *) printf 'Usage: bash scripts/run_hangar.sh [normal|blocked|unreachable] [Gazebo arguments...]\n' >&2; exit 2;; esac
if [ ! -r /opt/ros/jazzy/setup.bash ]; then
  printf 'ROS 2 Jazzy setup is missing. See docs/environment.md\n' >&2
  exit 1
fi
source /opt/ros/jazzy/setup.bash
exec gz sim -r -v 3 "$repo_root/simulation/worlds/hangar_${scenario}.sdf" "$@"
