"""Occupancy-grid rendering and explicit alignment of SLAM's native coordinates."""

import math
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

BASE_OFFSET = (-11.0, -7.0)


def grid_image(data, width: int, height: int) -> Image.Image:
    if width <= 0 or height <= 0 or width * height > 4_000_000:
        raise ValueError("Invalid map dimensions")
    grid = np.asarray(data, dtype=np.int16).reshape(height, width)
    if np.any((grid < -1) | (grid > 100)):
        raise ValueError("Invalid occupancy values")
    pixels = np.full(grid.shape, 205, dtype=np.uint8)
    pixels[(grid >= 0) & (grid <= 19)] = 254
    pixels[grid >= 65] = 0
    return Image.fromarray(np.flipud(pixels))


def write_aligned_map(prefix: Path, data, width, height, resolution, origin):
    """Translate origin only; never fill unknown cells with synthetic geometry."""
    if not math.isfinite(resolution) or resolution <= 0:
        raise ValueError("Invalid map resolution")
    if len(origin) != 3 or not all(math.isfinite(v) for v in origin):
        raise ValueError("Invalid origin")
    if abs(origin[2]) > 1e-6:
        raise ValueError("This BASE alignment requires zero native-map origin yaw")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    image = grid_image(data, width, height)
    image.save(prefix.with_suffix(".pgm"))
    image.save(prefix.with_suffix(".png"))
    info = {
        "image": prefix.with_suffix(".pgm").name,
        "mode": "trinary",
        "resolution": resolution,
        "origin": [origin[0] + BASE_OFFSET[0], origin[1] + BASE_OFFSET[1], origin[2]],
        "negate": 0,
        "occupied_thresh": 0.65,
        # Gray 205 encodes p=0.196078: it must remain above the free threshold.
        "free_thresh": 0.196,
    }
    prefix.with_suffix(".yaml").write_text(yaml.safe_dump(info, sort_keys=False))
    return info


def project_robot(x, y, yaw, origin, resolution, width, height):
    """Map coordinates -> image pixels; inverse map-origin rotation + ROS row flip."""
    dx, dy = x - origin[0], y - origin[1]
    c, s = math.cos(origin[2]), math.sin(origin[2])
    column = (c * dx + s * dy) / resolution
    row = height - 1 - (-s * dx + c * dy) / resolution
    if not (0 <= column < width and 0 <= row < height):
        return None
    return {"x": column, "y": row, "heading": yaw - origin[2]}
