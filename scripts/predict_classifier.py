#!/usr/bin/env python3
"""Run the latest pilot classifier on a board crop without starting ROS or Gazebo."""

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--model", choices=["selected", "baseline", "resnet18"], default="selected")
    args = parser.parse_args()
    index = json.loads((ROOT / "data/classifier/latest.json").read_text())
    run = Path(index["results"]).parent
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run(
        [
            str(ROOT / "data/vision/env/bin/python"),
            str(ROOT / "scripts/predict_classifier_worker.py"),
            "--run",
            str(run),
            "--image",
            str(args.image.expanduser().resolve()),
            "--model",
            args.model,
        ],
        env=env,
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
