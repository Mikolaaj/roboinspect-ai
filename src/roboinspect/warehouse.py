"""Reproducible warehouse layouts with verified access to every inspection goal."""

import copy
import json
import math
import random
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path
from uuid import uuid4

import numpy as np
import yaml
from PIL import Image

from .routes import ROOT, collision_boxes

MOVABLE = {
    "workbench_A": "A",
    "crate_3": "A",
    "column_0": "A",
    "crate_0": "B",
    "crate_1": "B",
    "rack_C": "C",
    "crate_2": "C",
    "column_1": "C",
}
DEFAULT = {"mode": "standard", "layout_id": "standard", "seed": None, "movable_count": 8}


def read_selection(root=ROOT):
    file = root / "data/warehouse/current.json"
    if not file.exists():
        return None
    result = json.loads(file.read_text())
    for name in ["world", "map"]:
        path = Path(result[name]).resolve()
        if (
            not path.is_relative_to((root / "data/warehouse/versions").resolve())
            or not path.is_file()
        ):
            raise RuntimeError("Brak zapisanej wersji magazynu. Przywróć pliki data/warehouse.")
    return result


def view(selection):
    return {key: selection[key] for key in DEFAULT} if selection else dict(DEFAULT)


def bounds(model):
    world = ET.Element("world")
    world.append(copy.deepcopy(model))
    boxes = collision_boxes(world)
    return [
        min(b[0] for b in boxes),
        max(b[1] for b in boxes),
        min(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]


def intersects(a, b, margin=0):
    return not (
        a[1] + margin <= b[0]
        or b[1] + margin <= a[0]
        or a[3] + margin <= b[2]
        or b[3] + margin <= a[2]
    )


def placements(world, seed, layout):
    rng = random.Random(seed)
    poses = {}
    occupied = []
    models = {m.get("name"): m for m in world.findall("model")}
    # Largest pieces first. Keep a 2.2 m wide longitudinal passage per sector.
    names = sorted(
        MOVABLE,
        key=lambda n: (
            (bounds(models[n])[1] - bounds(models[n])[0])
            * (bounds(models[n])[3] - bounds(models[n])[2])
        ),
        reverse=True,
    )
    for name in names:
        sector = MOVABLE[name]
        cfg = layout["sectors"][sector]
        x1, x2, _, _ = cfg["bounds"]
        gx = layout["inspection_zones"][sector]["pose"][0]
        b = bounds(models[name])
        width, depth = b[1] - b[0], b[3] - b[2]
        for _ in range(500):
            turn = rng.choice([False, True])
            w, h = (depth, width) if turn else (width, depth)
            left, right = rng.choice([(x1 + 0.5, gx - 1.1), (gx + 1.1, x2 - 0.5)])
            if right - left < w + 0.1 or h > 4.9:
                continue
            x = rng.uniform(left + w / 2, right - w / 2)
            y = rng.uniform(-1.5 + h / 2, 3.5 - h / 2)
            box = [x - w / 2, x + w / 2, y - h / 2, y + h / 2]
            if any(intersects(box, other, 0.28) for other in occupied):
                continue
            occupied.append(box)
            poses[name] = {"center": [x, y], "quarter_turn": turn}
            break
        else:
            raise ValueError("Nie znaleziono miejsca dla wyposażenia")
    return poses


def transform_model(model, pose):
    b = bounds(model)
    cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
    x, y = pose["center"]
    turn = pose["quarter_turn"]
    for link in model.findall("link"):
        for node in list(link.findall("visual")) + list(link.findall("collision")):
            p = node.find("pose")
            values = list(map(float, p.text.split()))
            dx, dy = values[0] - cx, values[1] - cy
            values[:2] = [x - dy, y + dx] if turn else [x + dx, y + dy]
            p.text = " ".join(map(str, values))
            if turn:
                size = node.find("geometry/box/size")
                sx, sy, sz = size.text.split()
                size.text = f"{sy} {sx} {sz}"


def apply_layout(tree, mode, poses):
    world = tree.getroot().find("world")
    for model in list(world.findall("model")):
        name = model.get("name")
        if name not in MOVABLE:
            continue
        if mode == "clear":
            world.remove(model)
        elif mode == "random":
            transform_model(model, poses[name])


def raster_map(world, resolution=0.05):
    xmin, ymin = -16, -12
    width, height = 640, 480
    pixels = np.full((height, width), 254, dtype=np.uint8)
    inflated = np.zeros((height, width), dtype=np.uint8)
    boxes = collision_boxes(world) + [
        (-16, -15, -12, 12),
        (15, 16, -12, 12),
        (-16, 16, -12, -11),
        (-16, 16, 11, 12),
    ]
    for target, margin, value in [(pixels, 0, 0), (inflated, 0.45, 1)]:
        for x1, x2, y1, y2 in boxes:
            c1 = max(0, math.floor((x1 - margin - xmin) / resolution))
            c2 = min(width, math.floor((x2 + margin - xmin) / resolution) + 1)
            r1 = max(0, math.floor((y1 - margin - ymin) / resolution))
            r2 = min(height, math.floor((y2 + margin - ymin) / resolution) + 1)
            target[r1:r2, c1:c2] = value
    return pixels, inflated


def validate_access(world, goals):
    pixels, blocked = raster_map(world)

    def cell(p):
        return int((p[1] + 12) / 0.05), int((p[0] + 16) / 0.05)

    r, c = cell(goals["BASE"])
    if blocked[r, c]:
        raise ValueError("Baza jest zablokowana")
    seen = np.zeros_like(blocked)
    seen[r, c] = 1
    queue = deque([(r, c)])
    while queue:
        r, c = queue.popleft()
        for nr, nc in [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]:
            if 0 <= nr < 480 and 0 <= nc < 640 and not blocked[nr, nc] and not seen[nr, nc]:
                seen[nr, nc] = 1
                queue.append((nr, nc))
    for name, point in goals.items():
        r, c = cell(point)
        if not (0 <= r < 480 and 0 <= c < 640 and seen[r, c]):
            raise ValueError(f"Brak dostępu do {name}")
    return pixels


def prepare_layout(mode, seed=None, root=ROOT):
    if mode not in {"standard", "clear", "random"}:
        raise ValueError("Nieznane ustawienie magazynu")
    if mode == "random" and seed is None:
        raise ValueError("Losowanie wymaga zapisanego ziarna")
    layout = json.loads((root / "config/hangar.json").read_text())
    goals = json.loads((root / "config/navigation-goals.json").read_text())["poses"]
    empty = ET.parse(root / "simulation/worlds/hangar_normal.sdf")
    poses = {}
    if mode == "random":
        for attempt in range(40):
            try:
                poses = placements(empty.getroot().find("world"), seed + attempt, layout)
                break
            except ValueError:
                if attempt == 39:
                    raise
    robot = ET.parse(root / "simulation/worlds/hangar_normal_robot.sdf")
    apply_layout(empty, mode, poses)
    apply_layout(robot, mode, poses)
    pixels = validate_access(empty.getroot().find("world"), goals)
    identity = f"{mode}-{uuid4().hex[:12]}"
    destination = root / "data/warehouse/versions" / identity
    destination.mkdir(parents=True)
    for tree, name in [(empty, "hangar.sdf"), (robot, "hangar_robot.sdf")]:
        ET.indent(tree, space="  ")
        tree.write(destination / name, encoding="utf-8", xml_declaration=True)
    Image.fromarray(np.flipud(pixels)).save(destination / "hangar.pgm")
    (destination / "hangar.yaml").write_text(
        yaml.safe_dump(
            {
                "image": "hangar.pgm",
                "mode": "trinary",
                "resolution": 0.05,
                "origin": [-16.0, -12.0, 0.0],
                "negate": 0,
                "occupied_thresh": 0.65,
                "free_thresh": 0.196,
            },
            sort_keys=False,
        )
    )
    result = {
        "mode": mode,
        "layout_id": identity,
        "seed": seed if mode == "random" else None,
        "movable_count": 0 if mode == "clear" else len(MOVABLE),
        "world": str(destination / "hangar_robot.sdf"),
        "map": str(destination / "hangar.yaml"),
        "placements": poses,
        "validated_goals": list(goals),
    }
    (destination / "layout.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    return result


def persist_selection(selection, root=ROOT):
    path = root / "data/warehouse/current.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(selection, ensure_ascii=False) + "\n")
    temporary.replace(path)
