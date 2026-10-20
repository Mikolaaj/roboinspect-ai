#!/usr/bin/env python3
"""Generate reproducible texture variants. These are assets, not camera training samples."""

import json
from pathlib import Path

from roboinspect.banner_conditions import MODES, VERSION, make_asset, source_splits
from roboinspect.banners import catalog

ROOT = Path(__file__).resolve().parents[1]
photos = catalog(ROOT)
partitions = source_splits(photos)
rows = []
for photo in photos:
    for condition in MODES:
        for seed in [1, 2]:
            asset = make_asset(photo, condition, seed, ROOT)
            rows.append({**asset, "split": partitions[photo["sha256"]]})
path = ROOT / "data/dataset/assets.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(
    json.dumps(
        {
            "kind": "texture-assets-not-camera-training-data",
            "generator": VERSION,
            "variants": rows,
            "source_splits": partitions,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n"
)
print("Warianty tekstur:", len(rows), "grupy źródłowe:", len(partitions))
