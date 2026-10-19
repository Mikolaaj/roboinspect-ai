#!/usr/bin/env python3
"""Verify photo-change operation, actual Gazebo mesh assignments and retained reports."""

import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

from roboinspect.banners import assignments

ROOT = Path(__file__).resolve().parents[1]
base = "http://127.0.0.1:8765"


def api(path, data=None, key=None):
    r = Request(
        base + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "Idempotency-Key": key or str(uuid4())},
    )
    with urlopen(r, timeout=5) as response:
        return json.load(response)


deadline = time.monotonic() + 90
while not api("/api/status")["ready"]:
    if time.monotonic() > deadline:
        raise RuntimeError("Startup timeout")
    time.sleep(1)
before = api("/api/status")["warehouse"]
history = api("/api/inspections")
selection = ROOT / "data/vision/selection.json"
oldseed = json.loads(selection.read_text())["seed"] if selection.exists() else 0
old = assignments(oldseed)
key = str(uuid4())
job = api("/api/warehouse/pictures", {}, key)
assert api("/api/warehouse/pictures", {}, key)["id"] == job["id"]
deadline = time.monotonic() + 160
while time.monotonic() < deadline:
    record = next(r for r in api("/api/history") if r["id"] == job["id"])
    if record["status"] in ["failed", "canceled", "interrupted"]:
        raise RuntimeError(record)
    s = api("/api/status")
    if record["status"] == "succeeded" and s["ready"] and len(s["cameras"]) == 3:
        break
    time.sleep(0.5)
else:
    raise RuntimeError("Photo transition timeout")
seed = json.loads(selection.read_text())["seed"]
new = assignments(seed)
assert all(old[p] != new[p] for p in old)
assert s["warehouse"] == before
assert {r["id"] for r in api("/api/inspections")} == {r["id"] for r in history}
runtime = json.loads((ROOT / "artifacts/cockpit-runtime.json").read_text())
env = {**os.environ, "GZ_PARTITION": runtime["gz_partition"]}
scene = subprocess.run(
    [
        "gz",
        "service",
        "-s",
        "/world/roboinspect_hangar/scene/info",
        "--reqtype",
        "gz.msgs.Empty",
        "--reptype",
        "gz.msgs.Scene",
        "--timeout",
        "3000",
        "--req",
        "",
    ],
    env=env,
    capture_output=True,
    text=True,
    timeout=10,
    check=True,
)
mesh_ids = set(re.findall(r"/meshes/([0-9]+)\.obj", scene.stdout))
assert mesh_ids == set(new.values()), (mesh_ids, new)
report = {
    "passed": True,
    "seed": seed,
    "previous": old,
    "current": new,
    "actual_gazebo_meshes": sorted(mesh_ids),
    "retained_reports": len(history),
    "warehouse_preserved": True,
    "job": job["id"],
    "events": record["events"],
}
out = ROOT / "artifacts/inspection-check/banner-change.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
