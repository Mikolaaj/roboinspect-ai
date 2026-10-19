"""Visible observation pads share the exact navigation goals; never add collisions."""

import xml.etree.ElementTree as ET


def observation_zones(layout):
    return {
        name: {"pose": point["observation_pose"], "size": [1.0, 1.0]}
        for name, point in layout["inspection_points"].items()
    }


def paint_observation_pads(world, layout):
    for old in list(world.findall("model")):
        if old.get("name", "").startswith("observation_pad_"):
            world.remove(old)
    for name, zone in observation_zones(layout).items():
        x, y, yaw = zone["pose"]
        model = ET.SubElement(world, "model", name="observation_pad_" + name)
        ET.SubElement(model, "static").text = "true"
        # Pads are aligned with the hall; arrow marks the +Y-facing observation heading.
        ET.SubElement(model, "pose").text = f"{x} {y} 0.038 0 0 0"
        link = ET.SubElement(model, "link", name="pad")
        parts = [
            ("fill", 0, 0, 1, 1, (0.04, 0.32, 0.20, 1)),
            ("north", 0, 0.48, 1, 0.04, (0.25, 0.95, 0.62, 1)),
            ("south", 0, -0.48, 1, 0.04, (0.25, 0.95, 0.62, 1)),
            ("west", -0.48, 0, 0.04, 1, (0.25, 0.95, 0.62, 1)),
            ("east", 0.48, 0, 0.04, 1, (0.25, 0.95, 0.62, 1)),
            ("center_x", 0, 0, 0.22, 0.035, (0.82, 1, 0.9, 1)),
            ("center_y", 0, 0, 0.035, 0.22, (0.82, 1, 0.9, 1)),
            ("heading", 0, 0.30, 0.06, 0.16, (0.82, 1, 0.9, 1)),
        ]
        for part, px, py, w, h, color in parts:
            visual = ET.SubElement(link, "visual", name=part)
            ET.SubElement(visual, "pose").text = f"{px} {py} {0 if part == 'fill' else 0.008} 0 0 0"
            ET.SubElement(
                ET.SubElement(ET.SubElement(visual, "geometry"), "box"), "size"
            ).text = f"{w} {h} .006"
            material = ET.SubElement(visual, "material")
            for key in ["ambient", "diffuse"]:
                ET.SubElement(material, key).text = " ".join(map(str, color))
            ET.SubElement(visual, "cast_shadows").text = "false"
