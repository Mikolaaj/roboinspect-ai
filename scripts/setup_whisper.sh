#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo 'Najpierw uruchom: bash scripts/setup_project.sh' >&2
  exit 1
fi
.venv/bin/python scripts/setup_whisper.py
