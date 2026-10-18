#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")/.."
source /opt/ros/jazzy/setup.bash
set -u
exec .venv/bin/python scripts/slam_tools.py save "$@"
