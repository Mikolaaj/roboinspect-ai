#!/usr/bin/env python3
"""Apply a mixed training scene and collect real robot-camera observations of all boards."""

import json
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
base = "http://127.0.0.1:8765"


def api(path, data=None, key=None):
    request = Request(
        base + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "Idempotency-Key": key or str(uuid4())},
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


deadline = time.monotonic() + 100
while True:
    try:
        if api("/api/status")["ready"]:
            break
    except URLError:
        pass
    if time.monotonic() > deadline:
        raise RuntimeError("Startup timeout")
    time.sleep(1)
key = str(uuid4())
operation = api("/api/banners/condition", {"mode": "mixed", "split": "train", "collect": True}, key)
assert (
    api("/api/banners/condition", {"mode": "mixed", "split": "train", "collect": True}, key)["id"]
    == operation["id"]
)
deadline = time.monotonic() + 150
while time.monotonic() < deadline:
    state = api("/api/status")
    if not state.get("operation_busy"):
        assert state["operation"]["status"] == "succeeded", state["operation"]
        break
    time.sleep(0.5)
else:
    raise RuntimeError("Condition operation timeout")
scene = state["banner_scene"]
assert len({p["condition"] for p in scene["panels"].values()}) == 5
print(
    "Nowa scena:",
    scene["id"],
    [(p, v["condition"]) for p, v in scene["panels"].items()],
    flush=True,
)
subprocess.run(
    [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/check_inspection.py")], check=True
)
summary = api("/api/dataset")
assert summary["samples"] >= 5, summary
rows = [json.loads(p.read_text()) for p in (ROOT / "data/dataset/samples").glob("*/metadata.json")]
current = [r for r in rows if r["scene_id"] == scene["id"]]
assert len(current) == 5 and len({r["condition"] for r in current}) == 5, current
assert all(
    r["split"] == "train"
    and r["label_origin"] == "synthetic_scene_manifest"
    and not r["training_ready"]
    for r in current
)
eda = api("/api/dataset/analyze", {})
assert not eda["leakage_errors"], eda["leakage_errors"]
proof = {"passed": True, "operation": operation, "scene": scene, "samples": current, "eda": eda}
(ROOT / "docs/verification/dataset-pilot.json").write_text(
    json.dumps(proof, ensure_ascii=False, indent=2) + "\n"
)
print("PASS:", summary, flush=True)
