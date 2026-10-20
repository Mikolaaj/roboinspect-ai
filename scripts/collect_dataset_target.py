#!/usr/bin/env python3
"""Collect actual Gazebo robot-camera frames at staged poses to exact split/class quotas."""

import argparse
import fcntl
import hashlib
import json
import math
import os
import random
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import rclpy
from cockpit import stop as stop_process
from PIL import Image
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image as RosImage

from roboinspect.banner_conditions import MODES
from roboinspect.banners import decorate
from roboinspect.dataset import analyze, collect_observation, samples, summary

ROOT = Path(__file__).resolve().parents[1]


class Camera(Node):
    def __init__(self):
        super().__init__("dataset_staged_camera")
        self.latest = None
        self.sequence = 0
        self.lock = threading.Lock()
        self.create_subscription(
            RosImage, "/roboinspect/camera/image", self.receive, qos_profile_sensor_data
        )

    def receive(self, message):
        with self.lock:
            self.sequence += 1
            self.latest = (message, self.sequence, time.monotonic())

    def frame(self, since, before, timeout=45):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                item = self.latest
            if (
                item
                and item[1] >= before + 4
                and item[2] > since + 0.8
                and time.monotonic() - item[2] < 2
            ):
                message, seq, _ = item
                if message.encoding != "rgb8":
                    raise RuntimeError("Unexpected camera encoding: " + message.encoding)
                picture = Image.frombytes(
                    "RGB",
                    (message.width, message.height),
                    bytes(message.data),
                    "raw",
                    "RGB",
                    message.step,
                )
                return picture, seq, message.header.stamp.sec + message.header.stamp.nanosec / 1e9
            time.sleep(0.1)
        raise TimeoutError("No fresh robot-camera frame")


def targets(total):
    if total % 25:
        raise ValueError("Total must be divisible by 25 for 60/20/20 and five balanced classes")
    return {"train": total * 3 // 5, "validation": total // 5, "test": total // 5}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--total", type=int, default=200)
    args = parser.parse_args()
    quotas = targets(args.total)
    batch_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "artifacts/dataset-target" / batch_id
    out.mkdir(parents=True)
    lockfile = (ROOT / "artifacts/dataset-target.lock").open("w")
    fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # Never run staged robot poses alongside the interactive cockpit or another collector.
    cockpit_lock = (ROOT / "artifacts/cockpit.lock").open("a")
    fcntl.flock(cockpit_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    before = summary(ROOT)
    if before["samples"] > args.total:
        raise RuntimeError("Dataset already exceeds requested target; no deletion performed")
    goals = json.loads((ROOT / "config/navigation-goals.json").read_text())["poses"]
    random_seed = int(hashlib.sha256(batch_id.encode()).hexdigest()[:16], 16)
    rng = random.Random(random_seed)
    os.environ["ROS_DOMAIN_ID"] = "126"
    rclpy.init()
    camera = Camera()

    def spin_camera():
        try:
            rclpy.spin(camera)
        except ExternalShutdownException:
            pass

    thread = threading.Thread(target=spin_camera, daemon=True)
    thread.start()
    process = None
    made = []
    error = None

    def log(kind, **values):
        row = {"at": datetime.now(UTC).isoformat(), "kind": kind, **values}
        with (out / "events.jsonl").open("a") as file:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps(row, ensure_ascii=False), flush=True)

    log("start", before=before, targets=quotas, random_seed=random_seed)
    try:
        for split, quota in quotas.items():
            failures = 0
            while True:
                rows = samples(ROOT)
                counts = {
                    mode: sum(r["split"] == split and r["condition"] == mode for r in rows)
                    for mode in MODES
                }
                remaining = {mode: quota // 5 - counts[mode] for mode in MODES}
                if any(n < 0 for n in remaining.values()):
                    raise RuntimeError("Existing class exceeds target quota")
                if not any(remaining.values()):
                    break
                seed = rng.randrange(1, 2**31)
                profile = {"mode": "mixed", "split": split, "collect": True, "seed": seed}
                world, _ = decorate(
                    ROOT / "simulation/worlds/hangar_normal_robot.sdf", seed, ROOT, profile=profile
                )
                scene = json.loads(world.with_suffix(".json").read_text())
                chosen = [p for p, v in scene["panels"].items() if remaining[v["condition"]] > 0]
                tree = ET.parse(world)
                robot = tree.getroot().find("world/model[@name='roboinspect']")
                if robot is None:
                    raise RuntimeError("Robot missing from world")
                # Isolated acquisition fixture: fixed chassis avoids wheel drift after pose changes.
                static = robot.find("static")
                if static is None:
                    static = ET.SubElement(robot, "static")
                static.text = "true"
                x, y, yaw = goals[chosen[0]]
                robot.find("pose").text = f"{x} {y} 0 0 0 {yaw}"
                staged = out / f"{scene['id']}.sdf"
                tree.write(staged, encoding="utf-8", xml_declaration=True)
                env = os.environ.copy()
                env["GZ_PARTITION"] = "dataset_" + batch_id + "_" + str(seed)
                logfile = (out / (scene["id"] + ".log")).open("w")
                process = subprocess.Popen(
                    [
                        "bash",
                        str(ROOT / "scripts/run_robot.sh"),
                        "headless:=true",
                        f"world:={staged}",
                    ],
                    env=env,
                    stdout=logfile,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                try:
                    started = time.monotonic()
                    camera.frame(started, camera.sequence, timeout=65)
                    for panel in chosen:
                        if len(samples(ROOT)) >= args.total:
                            break
                        mode = scene["panels"][panel]["condition"]
                        x, y, yaw = goals[panel]
                        x += rng.uniform(-0.22, 0.22)
                        y += rng.uniform(-0.18, 0.12)
                        yaw += rng.uniform(-0.065, 0.065)
                        request = f'name: "roboinspect" position {{x: {x} y: {y} z: 0}} orientation {{z: {math.sin(yaw / 2)} w: {math.cos(yaw / 2)}}}'
                        result = subprocess.run(
                            [
                                "gz",
                                "service",
                                "-s",
                                "/world/roboinspect_hangar/set_pose",
                                "--reqtype",
                                "gz.msgs.Pose",
                                "--reptype",
                                "gz.msgs.Boolean",
                                "--timeout",
                                "5000",
                                "--req",
                                request,
                            ],
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=8,
                        )
                        if result.returncode or "data: true" not in result.stdout:
                            raise RuntimeError(
                                "Pose change failed: " + result.stdout + result.stderr
                            )
                        pic, seq, stamp = camera.frame(time.monotonic(), camera.sequence)
                        identity = str(uuid4())
                        folder = ROOT / "data/inspections" / identity
                        folder.mkdir(parents=True)
                        pic.save(folder / "raw.jpg", quality=95)
                        report = {
                            "id": identity,
                            "created_at": datetime.now(UTC).isoformat(),
                            "mission_id": None,
                            "panel": panel,
                            "sector": {"P1": "A", "P2": "A", "P3": "B", "P4": "B", "P5": "C"}[
                                panel
                            ],
                            "camera_sequence": seq,
                            "camera_stamp_s": stamp,
                            "position": {"x": x, "y": y},
                            "heading": yaw,
                            "warehouse": {"layout_id": "standard", "mode": "standard"},
                            "collection_mode": "staged_static_robot_camera",
                            "acquisition_batch": batch_id,
                            "pose_source": "gazebo_set_pose_static_fixture",
                            "sim_robot_pose": {"x": x, "y": y, "z": 0, "yaw": yaw},
                            "renderer": "Gazebo robot RGB camera; fixed chassis, varied poses",
                        }
                        record = collect_observation(report, scene, ROOT)
                        digest = record["frame_sha256"]
                        invalid = record["review_status"] == "needs_retake"
                        duplicate = sum(r["frame_sha256"] == digest for r in samples(ROOT)) > 1
                        if invalid or duplicate:
                            quarantine = out / "quarantine"
                            quarantine.mkdir(exist_ok=True)
                            (ROOT / "data/dataset/samples" / identity).rename(quarantine / identity)
                            raise RuntimeError(
                                "Invalid crop or duplicate; evidence moved to session quarantine"
                            )
                        made.append(identity)
                        log(
                            "sample",
                            id=identity,
                            split=split,
                            condition=mode,
                            panel=panel,
                            total=len(samples(ROOT)),
                            camera_sequence=seq,
                            scene=scene["id"],
                        )
                    failures = 0
                except Exception as exc:
                    failures += 1
                    log("scene_error", message=str(exc), attempt=failures)
                    if failures >= 3:
                        raise
                finally:
                    stop_process(process)
                    process = None
                    logfile.close()
        final = summary(ROOT)
        assert final["samples"] == args.total and final["splits"] == quotas, final
        eda = analyze(ROOT)
        if eda["leakage_errors"] or eda["duplicates"]:
            raise RuntimeError("EDA found leakage or duplicates")
        proof = {
            "passed": True,
            "batch_id": batch_id,
            "before": before,
            "after": final,
            "targets": quotas,
            "new_ids": made,
            "eda": eda,
            "collection_mode": "staged_static_robot_camera",
            "note": "Real Gazebo camera pixels, fixed chassis at varied known poses. Not Nav2 mission executions or YOLO predictions.",
        }
        (ROOT / "docs/verification/dataset-200.json").write_text(
            json.dumps(proof, ensure_ascii=False, indent=2) + "\n"
        )
        log("complete", summary=final, run_id=eda.get("run_id"))
    except BaseException as exc:
        error = str(exc)
        log("stopped", error=error, summary=summary(ROOT))
        raise
    finally:
        if process is not None:
            stop_process(process)
        rclpy.try_shutdown()
        thread.join(timeout=3)
        camera.destroy_node()
        (out / "session.json").write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "before": before,
                    "after": summary(ROOT),
                    "new_ids": made,
                    "error": error,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
