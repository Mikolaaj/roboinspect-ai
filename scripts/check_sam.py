#!/usr/bin/env python3
"""Real inspection on a running simulator, with local Bielik loaded and GPU measurements."""

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--sector", default="C", choices=["A", "B", "C"])
args = parser.parse_args()
base = "http://127.0.0.1:8765"


def api(path, data=None):
    req = Request(
        base + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "Idempotency-Key": str(uuid4())},
    )
    with urlopen(req, timeout=10) as response:
        return json.load(response)


def gpu():
    out = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=memory.used,memory.total,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
    used, total, util = map(float, out.splitlines()[0].split(","))
    return dict(used_mib=used, total_mib=total, utilization_percent=util)


deadline = time.monotonic() + 90
while True:
    try:
        if api("/api/status")["ready"] and api("/api/vision").get("ready"):
            break
    except URLError:
        pass
    if time.monotonic() > deadline:
        raise RuntimeError("Startup timeout")
    time.sleep(1)
# Ask a harmless explanation so local Bielik is actually loaded during inspection.
chat = api("/api/chat", {"text": "Jak działa inspekcja zdjęć?"})
deadline = time.monotonic() + 100
while time.monotonic() < deadline:
    rows = api("/api/chat")
    current = next(r for r in rows if r["id"] == chat["id"])
    if current["status"] != "pending":
        break
    time.sleep(0.3)
assert current["status"] == "answered", current
# Keep Bielik resident throughout navigation, instead of the default two minutes.
request = Request(
    "http://127.0.0.1:11435/api/generate",
    data=json.dumps(
        {"model": "roboinspect-bielik:q4_k_m", "prompt": "", "stream": False, "keep_alive": "15m"}
    ).encode(),
    headers={"Content-Type": "application/json"},
)
with urlopen(request, timeout=90) as response:
    json.load(response)
with urlopen("http://127.0.0.1:11435/api/ps", timeout=5) as response:
    loaded = json.load(response)
assert any(
    model["name"] == "roboinspect-bielik:q4_k_m" and model.get("size_vram", 0) > 0
    for model in loaded["models"]
), loaded
baseline = gpu()
mission = api("/api/inspect/" + args.sector, {})
samples = []
deadline = time.monotonic() + 700
last = None
while time.monotonic() < deadline:
    m = api("/api/missions/" + mission["id"])
    samples.append(gpu())
    if m["message"] != last:
        print(m["message"], flush=True)
        last = m["message"]
    if m["status"] not in ("queued", "running", "canceling", "uncertain"):
        break
    time.sleep(0.5)
assert m["status"] == "succeeded", m
rows = [r for r in api("/api/inspections?limit=100") if r["mission_id"] == mission["id"]]
for row in rows:
    seg = row["segmentation"]
    assert seg["status"] in ("complete", "no_detections"), seg
    assert len(seg["masks"]) == row["total"]
    for field in ("image_url", "mask_url", "data_url"):
        if row["total"]:
            with urlopen(base + seg[field]) as response:
                assert len(response.read()) > 0
with urlopen("http://127.0.0.1:11435/api/ps", timeout=5) as response:
    loaded_after = json.load(response)
assert any(
    model["name"] == "roboinspect-bielik:q4_k_m" and model.get("size_vram", 0) > 0
    for model in loaded_after["models"]
), loaded_after
proof = {
    "llm_loaded_after_inspection": loaded_after,
    "passed": True,
    "sector": args.sector,
    "mission": m,
    "reports": rows,
    "gpu_baseline": baseline,
    "gpu_peak_sampled_mib": max(s["used_mib"] for s in samples),
    "gpu_samples": samples,
    "llm_loaded_before_inspection": loaded,
}
(ROOT / f"docs/verification/sam-inspection-{args.sector.lower()}.json").write_text(
    json.dumps(proof, ensure_ascii=False, indent=2) + "\n"
)
print("PASS", [(r["panel"], r["total"], r["segmentation"]["seconds"]) for r in rows], flush=True)
