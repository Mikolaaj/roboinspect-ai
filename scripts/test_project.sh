#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
node --check operator/web/vision.js
node --check operator/web/activity.js
node --check operator/web/app.js
node --check operator/web/voice.js
node --check operator/web/route-map.js
for test_file in tests/web/*.test.cjs; do
  node "$test_file"
done
# Keep unrelated system ROS pytest plugins out of application tests.
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest "$@"
