#!/usr/bin/env python3
"""Exercise real camera inspection end to end, including all boards and sector return."""

import argparse
import json
import math
import time
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

parser = argparse.ArgumentParser()
parser.add_argument("--sectors", nargs="+", default=["A", "B", "C"])
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "artifacts/inspection-check"
out.mkdir(parents=True, exist_ok=True)
base = "http://127.0.0.1:8765"


def api(path, data=None, key=None):
    r = Request(
        base + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "Idempotency-Key": key or str(uuid4())},
    )
    with urlopen(r, timeout=8) as response:
        return json.load(response)


goals = json.loads((ROOT / "config/navigation-goals.json").read_text())["poses"]
results = []
for sector in args.sectors:
    deadline = time.monotonic() + 90
    while not api("/api/status")["ready"] or not api("/api/vision").get("ready"):
        if time.monotonic() > deadline:
            raise RuntimeError("Startup timeout")
        time.sleep(1)
    key = str(uuid4())
    mission = api("/api/inspect/" + sector, {}, key)
    duplicate = api("/api/inspect/" + sector, {}, key)
    assert duplicate["id"] == mission["id"]
    print("RUN:", sector, mission["id"], flush=True)
    deadline = time.monotonic() + 850
    message = None
    while time.monotonic() < deadline:
        mission = api("/api/missions/" + mission["id"])
        if mission["message"] != message:
            message = mission["message"]
            print(message, flush=True)
        if mission["status"] not in ["queued", "running", "canceling", "uncertain"]:
            break
        time.sleep(1)
    assert mission["status"] == "succeeded", mission
    reports = [r for r in api("/api/inspections?limit=100") if r["mission_id"] == mission["id"]]
    expected = {"A": ["P1", "P2"], "B": ["P3", "P4"], "C": ["P5"]}[sector]
    assert sorted(r["panel"] for r in reports) == expected
    for r in reports:
        assert r["width"] == 1280 and r["height"] == 720 and r["device"] == "cuda:0"
        assert r["total"] == len(r["detections"]) == sum(r["counts"].values())
        with urlopen(base + r["image_url"]) as response:
            (out / (r["panel"] + ".jpg")).write_bytes(response.read())
    s = api("/api/status")
    p = s["map_position"]
    assert math.hypot(p["x"] - goals[sector][0], p["y"] - goals[sector][1]) < 0.5
    results.append({"sector": sector, "mission": mission, "reports": reports, "return_position": p})
    (out / "result.json").write_text(
        json.dumps({"passed": True, "results": results}, ensure_ascii=False, indent=2) + "\n"
    )
    print("PASS:", sector, [(r["panel"], r["counts"]) for r in reports], flush=True)
