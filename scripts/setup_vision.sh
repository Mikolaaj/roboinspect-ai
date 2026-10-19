#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
mkdir -p data/vision
.venv/bin/uv venv --allow-existing data/vision/env --python .venv/bin/python
.venv/bin/uv pip install --python data/vision/env/bin/python torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128
.venv/bin/uv pip install --python data/vision/env/bin/python -r config/vision-requirements.lock
curl -L --fail --retry 2 https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt -o data/vision/yolo11s.pt
echo '85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5  data/vision/yolo11s.pt' | sha256sum --check
curl -L --fail --retry 2 https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip -o data/vision/coco128.zip
echo '61e5e3028863d8ffc3b81d6a514603954889f0edd5e4b44c4ce60b2da99aeb8e  data/vision/coco128.zip' | sha256sum --check
.venv/bin/python scripts/setup_vision_assets.py

bash scripts/setup_sam.sh
