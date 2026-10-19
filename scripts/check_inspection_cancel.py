#!/usr/bin/env python3
"""Cancel an actual inspection during its dwell using the same STOP as chat."""

import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
base = "http://127.0.0.1:8765"


def api(path, data=None):
    req = Request(
        base + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "Idempotency-Key": str(uuid4())},
    )
    with urlopen(req, timeout=5) as r:
        return json.load(r)


mission = api("/api/inspect/C", {})
deadline = time.monotonic() + 400
while time.monotonic() < deadline:
    m = api("/api/missions/" + mission["id"])
    i = m["current_step"]
    if (
        i is not None
        and m["steps"][i]["action"] == "inspect"
        and m["steps"][i]["status"] == "running"
    ):
        break
    if m["status"] not in ["queued", "running"]:
        raise RuntimeError(m)
    time.sleep(0.08)
else:
    raise RuntimeError("No inspection step")
epoch = api("/api/chat/control")["control_epoch"]
stop = api("/api/chat", {"text": "STOP", "control_epoch": epoch})
deadline = time.monotonic() + 15
while time.monotonic() < deadline:
    m = api("/api/missions/" + mission["id"])
    if m["status"] == "canceled":
        break
    time.sleep(0.1)
assert m["status"] == "canceled", m
time.sleep(3)
rows = [r for r in api("/api/inspections?limit=100") if r["mission_id"] == m["id"]]
assert not rows, rows
s = api("/api/status")
assert (
    not s["busy"] and abs(s["velocity"]["linear"]) < 0.02 and abs(s["velocity"]["angular"]) < 0.02
)
report = {
    "passed": True,
    "mission_id": m["id"],
    "status": m["status"],
    "reports_after_late_result_wait": len(rows),
    "remaining_steps": [step["status"] for step in m["steps"]],
    "stop_reply": stop["reply"],
}
(ROOT / "artifacts/inspection-check/cancel.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
)
print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
