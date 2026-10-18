#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# ROS Jazzy binaries require Python 3.12, including the API adapter.
if [[ ! -x .venv/bin/python ]]; then
  /usr/bin/python3 -m venv .venv
fi
if [[ ! -x .venv/bin/uv ]]; then
  .venv/bin/python -m pip install 'uv==0.13.1'
fi
.venv/bin/uv sync --frozen --python /usr/bin/python3
