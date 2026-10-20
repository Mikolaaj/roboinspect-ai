#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/ruff check src tests deployment/gateway.py deployment/ci_operator.py scripts/kube_common.py scripts/render_kubernetes.py scripts/run_kubernetes.py scripts/forward_kubernetes.py scripts/deploy_kubernetes.py scripts/check_kubernetes.py
.venv/bin/ruff format --check src tests deployment/gateway.py deployment/ci_operator.py scripts/kube_common.py scripts/render_kubernetes.py scripts/run_kubernetes.py scripts/forward_kubernetes.py scripts/deploy_kubernetes.py scripts/check_kubernetes.py
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
