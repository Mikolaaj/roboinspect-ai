#!/usr/bin/env python3
"""Prepare attributed COCO examples and self-contained textured planes."""

import hashlib
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
base = ROOT / "data/vision"
archive = base / "coco128.zip"
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
if digest != "61e5e3028863d8ffc3b81d6a514603954889f0edd5e4b44c4ce60b2da99aeb8e":
    raise RuntimeError("Niezgodna suma archiwum COCO128")
print("COCO128 SHA256:", digest)
with zipfile.ZipFile(archive) as z:
    names = z.namelist()
    labels = [n for n in names if "/labels/train2017/" in n and n.endswith(".txt")]
    wanted = [0, 15, 16, 17, 18, 19, 20, 21, 22, 23, 2, 5, 39, 56, 58]
    chosen = []
    for cls in wanted:
        candidates = []
        for label in labels:
            boxes = [
                list(map(float, line.split()))
                for line in z.read(label).decode().splitlines()
                if line.strip()
            ]
            area = max([b[3] * b[4] for b in boxes if int(b[0]) == cls] or [0])
            if area > 0.07 and label not in chosen:
                candidates.append((area, label))
        if candidates:
            chosen.append(max(candidates)[1])
    for label in sorted(labels):
        if len(chosen) >= 24:
            break
        if label not in chosen:
            chosen.append(label)
    (base / "photos").mkdir(parents=True, exist_ok=True)
    (base / "meshes").mkdir(exist_ok=True)
    manifest = []
    for label in chosen:
        name = Path(label).stem
        image_name = label.replace("/labels/", "/images/").replace(".txt", ".jpg")
        data = z.read(image_name)
        raw = base / "photos" / f"{name}.jpg"
        raw.write_bytes(data)
        # Letterbox preserves the photo geometry and object proportions on a square board.
        photo = Image.open(raw).convert("RGB")
        ImageOps.pad(photo, (1024, 1024), color=(235, 235, 235)).save(
            base / "meshes" / f"{name}.jpg", quality=95
        )
        (base / "meshes" / f"{name}.mtl").write_text(
            f"newmtl photo\nKa 1 1 1\nKd 1 1 1\nKs 0 0 0\nillum 1\nmap_Kd {name}.jpg\n"
        )
        (base / "meshes" / f"{name}.obj").write_text(
            f"mtllib {name}.mtl\no photo\nv -0.56 0 -0.55\nv 0.56 0 -0.55\nv 0.56 0 0.55\nv -0.56 0 0.55\nvt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nvn 0 -1 0\nusemtl photo\nf 1/1/1 2/2/1 3/3/1\nf 1/1/1 3/3/1 4/4/1\n"
        )
        manifest.append(
            {
                "id": name,
                "source": f"https://cocodataset.org/#explore?id={int(name)}",
                "file": str(raw.relative_to(ROOT)),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    (base / "photos.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(
    "Prepared",
    len(manifest),
    "photos. Source: COCO train2017 through official Ultralytics COCO128 sample.",
)
