#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/prepare_compose_env.py
export ROBOINSPECT_ROOT="$PWD" ROBOINSPECT_UID="$(id -u)" ROBOINSPECT_GID="$(id -g)"
bash scripts/stop_cockpit.sh
docker compose -f compose.yaml -f compose.monitoring.yaml down
