#!/usr/bin/env bash
set -e
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source /opt/ros/jazzy/setup.bash
if [[ ! -x "$repo_root/.venv/bin/python" ]]; then
  echo 'Najpierw uruchom: bash scripts/setup_project.sh' >&2
  exit 1
fi
exec "$repo_root/.venv/bin/python" "$repo_root/scripts/cockpit.py" "$@"
