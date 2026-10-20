#!/usr/bin/env python3
"""Bounded real-camera collection session with a wall-clock cutoff and audit log."""

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--until", required=True, help="ISO timestamp including UTC offset")
    args = parser.parse_args()
    cutoff = datetime.fromisoformat(args.until).timestamp()
    out = ROOT / "artifacts/dataset-session" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    events = []

    def log(kind, **values):
        entry = {"time": datetime.now().astimezone().isoformat(), "kind": kind, **values}
        events.append(entry)
        with (out / "events.jsonl").open("a") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(json.dumps(entry, ensure_ascii=False), flush=True)

    def api(path, data=None):
        request = Request(
            "http://127.0.0.1:8765" + path,
            data=None if data is None else json.dumps(data).encode(),
            headers={"Content-Type": "application/json", "Idempotency-Key": str(uuid4())},
        )
        with urlopen(request, timeout=12) as response:
            return json.load(response)

    def wait_ready():
        limit = min(cutoff, time.time() + 160)
        while time.time() < limit:
            try:
                state = api("/api/status")
                if (
                    state.get("ready")
                    and not state.get("busy")
                    and not state.get("operation_busy")
                    and api("/api/vision").get("ready")
                ):
                    return state
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError("Readiness timeout or session cutoff")

    initial = None
    try:
        wait_ready()
        initial = api("/api/dataset")
        log("start", cutoff=args.until, initial=initial)
        cycle = 0
        while time.time() < cutoff - 120:
            split = ["train", "validation", "train", "test"][cycle % 4]
            wait_ready()
            operation = api(
                "/api/banners/condition", {"mode": "mixed", "split": split, "collect": True}
            )
            log("scene_requested", cycle=cycle, split=split, operation_id=operation["id"])
            limit = min(cutoff, time.time() + 160)
            while time.time() < limit:
                state = api("/api/status")
                if not state.get("operation_busy"):
                    if state.get("operation", {}).get("status") != "succeeded":
                        raise RuntimeError(str(state.get("operation")))
                    break
                time.sleep(2)
            else:
                raise TimeoutError("Scene update timeout")
            log("scene_ready", scene_id=state.get("banner_scene", {}).get("id"), split=split)
            for sector in ["A", "B", "C"]:
                if time.time() >= cutoff - 90:
                    break
                wait_ready()
                mission = api("/api/inspect/" + sector, {})
                log("mission_started", sector=sector, mission_id=mission["id"])
                limit = min(cutoff, time.time() + 420)
                while time.time() < limit:
                    mission = api("/api/missions/" + mission["id"])
                    if mission["status"] not in ["queued", "running", "canceling", "uncertain"]:
                        break
                    time.sleep(2)
                else:
                    api("/api/cancel", {})
                    log("mission_timeout", mission_id=mission["id"])
                    if time.time() >= cutoff - 90:
                        break
                    raise TimeoutError("Mission stalled")
                log(
                    "mission_finished",
                    sector=sector,
                    status=mission["status"],
                    message=mission.get("message"),
                    dataset=api("/api/dataset"),
                )
                if mission["status"] != "succeeded":
                    break
            cycle += 1
    except Exception as error:
        log("error", message=str(error))
    finally:
        try:
            api("/api/cancel", {})
            log("collection_stopped", summary=api("/api/dataset"))
            eda = api("/api/dataset/analyze", {})
            (out / "eda.json").write_text(json.dumps(eda, ensure_ascii=False, indent=2))
            log("eda", report=eda)
        except Exception as error:
            log("finalization_error", message=str(error))
        subprocess.run(
            ["bash", str(ROOT / "scripts/stop_cockpit.sh")], cwd=ROOT, timeout=90, check=False
        )
        log("shutdown")
        (out / "summary.json").write_text(
            json.dumps({"initial": initial, "events": events}, ensure_ascii=False, indent=2)
        )


if __name__ == "__main__":
    main()
