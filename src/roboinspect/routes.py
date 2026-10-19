"""Read-only navigation telemetry and bounded, collision-free route geometry."""

import hashlib
import json
import math
import time
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEGMENTS = 160


def clean_path(points, goal):
    if not 2 <= len(points) <= 3000:
        return []
    result = []
    for x, y in points:
        if not (math.isfinite(x) and math.isfinite(y) and abs(x) <= 32 and abs(y) <= 24):
            return []
        if not result or math.dist((x, y), result[-1]) > 0.01:
            result.append([float(x), float(y)])
    if len(result) < 2 or math.dist(result[-1], goal[:2]) > 0.6:
        return []
    return result


class RouteState:
    def __init__(self):
        self.clear()
        self.revision = 0

    def clear(self):
        self.points = []
        self.received = 0
        self.stamp = 0
        self.started = float("inf")
        self.target = None

    def begin(self, target, simulation_time):
        self.clear()
        self.target = list(target)
        self.started = simulation_time

    def update(self, points, frame, stamp, now=None, simulation_time=None):
        if self.target is None or frame != "map" or stamp < self.started or stamp < self.stamp:
            return False
        if simulation_time is not None and abs(stamp - simulation_time) > 2:
            return False
        cleaned = clean_path(points, self.target)
        if not cleaned:
            return False
        self.points, self.stamp = cleaned, stamp
        self.received = time.monotonic() if now is None else now
        self.revision += 1
        return True

    def snapshot(self, active, now=None):
        if not active or self.target is None:
            return {"points": [], "goal": None, "revision": self.revision, "status": "idle"}
        age = (time.monotonic() if now is None else now) - self.received
        fresh = bool(self.points) and age < 3
        return {
            "points": self.points if fresh else [],
            "goal": self.target[:2],
            "revision": self.revision,
            "status": "live" if fresh else "waiting",
            "age_s": round(age, 2) if self.received else None,
            "source": "/plan",
        }


def sample_segments(points):
    """Arc-length sampling keeps the number of moving Gazebo models bounded."""
    if len(points) < 2:
        return []
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    total = sum(lengths)
    if total < 0.01:
        return []
    count = min(SEGMENTS, max(1, math.ceil(total / 0.45)))
    spacing = total / count
    result = []
    index, passed = 0, 0.0
    for i in range(count):
        distance = (i + 0.5) * spacing
        while index < len(lengths) - 1 and passed + lengths[index] < distance:
            passed += lengths[index]
            index += 1
        a, b = points[index], points[index + 1]
        ratio = (distance - passed) / max(lengths[index], 1e-9)
        result.append(
            (
                a[0] + (b[0] - a[0]) * ratio,
                a[1] + (b[1] - a[1]) * ratio,
                math.atan2(b[1] - a[1], b[0] - a[0]),
            )
        )
    return result


def visual_message(route):
    segments = sample_segments(route.get("points", []))
    poses = []
    for i in range(SEGMENTS):
        x, y, yaw = segments[i] if i < len(segments) else (0, 0, 0)
        z = 0.045 if i < len(segments) else -2
        poses.append(
            f'pose {{ name: "route_segment_{i}" position {{ x:{x:.4f} y:{y:.4f} z:{z} }} '
            f"orientation {{ z:{math.sin(yaw / 2):.6f} w:{math.cos(yaw / 2):.6f} }} }}"
        )
    goal = route.get("goal")
    x, y, z = (*goal, 0.045) if goal else (0, 0, -2)
    poses.append(
        f'pose {{ name:"route_goal" position {{ x:{x:.4f} y:{y:.4f} z:{z} }} orientation {{ w:1 }} }}'
    )
    return " ".join(poses)


def collision_boxes(world):
    boxes = []
    for model in world.findall("model"):
        if model.findtext("static") != "true":
            continue
        mp = [float(v) for v in model.findtext("pose", "0 0 0 0 0 0").split()]
        for link in model.findall("link"):
            lp = [float(v) for v in link.findtext("pose", "0 0 0 0 0 0").split()]
            for collision in link.findall("collision"):
                size = collision.findtext("geometry/box/size")
                if not size:
                    continue
                sx, sy, sz = map(float, size.split())
                cp = [float(v) for v in collision.findtext("pose", "0 0 0 0 0 0").split()]
                x, y, z = (mp[i] + lp[i] + cp[i] for i in range(3))
                if z + sz / 2 > 0.05:
                    boxes.append([x - sx / 2, x + sx / 2, y - sy / 2, y + sy / 2])
    return boxes


@lru_cache(maxsize=16)
def hangar_layout(scenario, world_file=None, layout_id="standard"):
    if scenario not in {"normal", "blocked", "unreachable"}:
        raise ValueError("Unknown scenario")
    layout = json.loads((ROOT / "config/hangar.json").read_text())
    path = Path(world_file) if world_file else ROOT / f"simulation/worlds/hangar_{scenario}.sdf"
    world = ET.parse(path).getroot().find("world")
    boxes = collision_boxes(world)
    return {
        "bounds": layout["floor_bounds"],
        "sectors": layout["sectors"],
        "zones": layout["inspection_zones"],
        "observation_zones": {
            name: {"pose": point["observation_pose"], "size": [1, 1]}
            for name, point in layout["inspection_points"].items()
        },
        "base": layout["base_pose"][:2],
        "obstacles": boxes,
        "scenario": scenario,
        "layout_id": layout_id,
    }


def costmap_obstacles(data, width, height, resolution, origin):
    """Run-length encode lethal observed cells, not inflated planning costs."""
    if width * height != len(data) or width * height > 1_000_000 or resolution <= 0:
        return []
    if abs(origin[2]) > 1e-6:
        return []
    rectangles = []
    for row in range(height):
        start = None
        for column in range(width + 1):
            occupied = column < width and data[row * width + column] >= 100
            if occupied and start is None:
                start = column
            elif not occupied and start is not None:
                rectangles.append(
                    [
                        origin[0] + start * resolution,
                        origin[0] + column * resolution,
                        origin[1] + row * resolution,
                        origin[1] + (row + 1) * resolution,
                    ]
                )
                start = None
                if len(rectangles) >= 3500:
                    return rectangles
    return rectangles


def route_fingerprint(route):
    return hashlib.sha256(json.dumps([route.get("points"), route.get("goal")]).encode()).hexdigest()
