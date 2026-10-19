"""Photo assignments and actual textured Gazebo surfaces. Labels never feed detection."""

import hashlib
import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path

from .observation import paint_observation_pads

ROOT = Path(__file__).resolve().parents[2]

PANELS = {"A": ["P1", "P2"], "B": ["P3", "P4"], "C": ["P5"]}


def catalog(root=ROOT):
    path = root / "data/vision/photos.json"
    return json.loads(path.read_text()) if path.exists() else []


def assignments(seed=0, root=ROOT):
    photos = catalog(root)
    if len(photos) < 5:
        raise RuntimeError("Najpierw przygotuj zdjęcia: bash scripts/setup_vision.sh")
    chosen = random.Random(seed).sample(photos, 5)
    return {f"P{i}": row["id"] for i, row in enumerate(chosen, 1)}


def decorate(source, seed=0, root=ROOT):
    """Build a portable runtime copy, including existing persisted warehouse worlds."""
    tree = ET.parse(source)
    world = tree.getroot().find("world")
    paint_observation_pads(world, json.loads((root / "config/hangar.json").read_text()))
    photos = {row["id"]: row for row in catalog(root)}
    selected = assignments(seed, root) if photos else {}
    for panel, image_id in selected.items():
        link = world.find(f"model[@name='panel_{panel}']/link")
        if link is None:
            continue
        for old in list(link.findall("visual")):
            if old.get("name") == "banner_photo":
                link.remove(old)
        # OBJ lies in XZ with normal -Y, looking towards the robot approach.
        visual = ET.SubElement(link, "visual", name="banner_photo")
        center = json.loads((root / "config/hangar.json").read_text())["inspection_points"][panel][
            "panel_xyz"
        ]
        ET.SubElement(visual, "pose").text = f"{center[0]} {center[1] - 0.151} {center[2]} 0 0 0"
        mesh = ET.SubElement(ET.SubElement(visual, "geometry"), "mesh")
        ET.SubElement(mesh, "uri").text = (root / "data/vision/meshes" / f"{image_id}.obj").as_uri()
        ET.SubElement(visual, "cast_shadows").text = "false"
    for camera in world.findall(".//sensor[@name='front_camera']"):
        camera.find("camera/image/width").text = "1280"
        camera.find("camera/image/height").text = "720"
        camera.find("pose").text = "0.29 0 0.65 0 -0.14 0"
        camera.find("update_rate").text = "8"
    digest = hashlib.sha256(Path(source).read_bytes() + str(seed).encode()).hexdigest()[:16]
    target = root / "data/vision/worlds" / f"{digest}.sdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(target, encoding="utf-8", xml_declaration=True)
    return target, selected
