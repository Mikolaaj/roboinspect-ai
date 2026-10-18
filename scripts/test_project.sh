#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
# Keep unrelated system ROS pytest plugins out of application tests.
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest "$@"
