"""Reproducible synthetic board conditions and source-group splits. Not model predictions."""

import hashlib
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
VERSION = "board-conditions-v1"
MODES = ("clean", "cracked", "dirty", "occluded", "missing")
TITLES = {
    "clean": "Poprawny obraz",
    "cracked": "Pęknięcia",
    "dirty": "Zabrudzenie",
    "occluded": "Zasłonięcie",
    "missing": "Brak obrazu",
    "mixed": "Mieszane stany",
}


def source_splits(photos):
    groups = sorted(
        {p["sha256"] for p in photos},
        key=lambda value: hashlib.sha256(("2026:" + value).encode()).hexdigest(),
    )
    if len(groups) < 15:
        raise ValueError("Zbiór wymaga co najmniej 15 różnych zdjęć źródłowych")
    n = max(5, round(len(groups) * 0.2))
    return {
        group: ("test" if i < n else "validation" if i < 2 * n else "train")
        for i, group in enumerate(groups)
    }


def read_profile(root=ROOT):
    path = root / "data/vision/conditions.json"
    return (
        json.loads(path.read_text())
        if path.exists()
        else {"mode": "clean", "split": None, "collect": False, "seed": 0}
    )


def render_condition(image, condition, seed):
    if condition not in MODES:
        raise ValueError("Nieznany stan tablicy")
    image = image.convert("RGB").copy()
    rng = random.Random(seed)
    width, height = image.size
    layer = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(layer)
    if condition == "missing":
        return Image.new("RGB", image.size, (230, 230, 226))
    if condition == "cracked":
        for _ in range(3):
            x = rng.randint(width // 5, 4 * width // 5)
            points = [(x, 0)]
            for y in range(0, height + 1, max(1, height // 8)):
                x = max(0, min(width - 1, x + rng.randint(-width // 8, width // 8)))
                points.append((x, y))
            draw.line(points, fill=(25, 28, 30, 240), width=max(2, width // 180))
            draw.line(
                [(a + 3, b) for a, b in points],
                fill=(245, 245, 245, 200),
                width=max(1, width // 320),
            )
    elif condition == "dirty":
        for _ in range(16):
            x, y = rng.randrange(width), rng.randrange(height)
            r = rng.randint(width // 25, width // 8)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(85, 63, 27, rng.randint(110, 210)))
    elif condition == "occluded":
        w, h = int(width * rng.uniform(0.40, 0.6)), int(height * rng.uniform(0.55, 0.75))
        x, y = rng.randint(0, width - w), rng.randint(0, height - h)
        draw.rectangle((x, y, x + w, y + h), fill=(60, 65, 69, 255))
    return Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")


def make_asset(photo, condition, seed, root=ROOT):
    fingerprint = hashlib.sha256(
        f"{VERSION}:{photo['sha256']}:{condition}:{seed}".encode()
    ).hexdigest()
    stem = "variant_" + fingerprint[:24]
    directory = root / "data/vision/meshes"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{stem}.jpg"
    if not target.exists():
        original = Image.open(directory / f"{photo['id']}.jpg").convert("RGB")
        render_condition(original, condition, seed).save(target, quality=95)
        (directory / f"{stem}.mtl").write_text(
            f"newmtl photo\nKa 1 1 1\nKd 1 1 1\nKs 0 0 0\nillum 1\nmap_Kd {stem}.jpg\n"
        )
        original_mesh = (directory / f"{photo['id']}.obj").read_text()
        (directory / f"{stem}.obj").write_text(
            original_mesh.replace(f"{photo['id']}.mtl", f"{stem}.mtl")
        )
    return {
        "mesh": stem + ".obj",
        "texture_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "source_id": photo["id"],
        "source_sha256": photo["sha256"],
        "source_url": photo["source"],
        "condition": condition,
        "transform_seed": seed,
        "generator": VERSION,
    }


def build_scene(selected, photos, profile, root=ROOT):
    by_id = {p["id"]: p for p in photos}
    if profile["mode"] not in (*MODES, "mixed"):
        raise ValueError("Nieznany stan tablic")
    conditions = list(MODES)
    random.Random(profile["seed"]).shuffle(conditions)
    panels = {}
    for i, (panel, source_id) in enumerate(sorted(selected.items())):
        condition = conditions[i] if profile["mode"] == "mixed" else profile["mode"]
        seed = int(
            hashlib.sha256(f"{profile['seed']}:{panel}:{source_id}".encode()).hexdigest()[:8], 16
        )
        panels[panel] = make_asset(by_id[source_id], condition, seed, root)
    content = {"profile": profile, "panels": panels, "generator": VERSION}
    content["id"] = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    return content
