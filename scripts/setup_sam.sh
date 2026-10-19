#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x data/vision/env/bin/python ]]; then
  echo 'Najpierw wykonaj bash scripts/setup_vision.sh'
  exit 1
fi
mkdir -p data/vision
expected=3c1e81ca9b037dd39d70a014ddb9a813d6c4c4e12555420db7eaff31689bd4e3
if ! echo "$expected  data/vision/sam2.1_t.pt" | sha256sum --check --status; then
  curl -fL --retry 2 https://github.com/ultralytics/assets/releases/download/v8.3.0/sam2.1_t.pt -o data/vision/sam2.1_t.pt
fi
echo "$expected  data/vision/sam2.1_t.pt" | sha256sum --check
printf 'SAM 2.1 Tiny gotowy. Uruchamiaj standardowo bash scripts/run_cockpit.sh.\n'
