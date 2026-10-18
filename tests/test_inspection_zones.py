import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from roboinspect.mapping import project_zones

ROOT = Path(__file__).resolve().parents[1]


def test_one_painted_zone_per_sector_and_no_collision():
    layout = json.loads((ROOT / "config/hangar.json").read_text())
    goals = json.loads((ROOT / "config/navigation-goals.json").read_text())["poses"]
    for file in (ROOT / "simulation/worlds").glob("hangar_*.sdf"):
        world = ET.parse(file).getroot().find("world")
        zones = [
            m for m in world.findall("model") if m.get("name", "").startswith("inspection_zone_")
        ]
        assert len(zones) == 3, file.name
        assert not world.findall("model[@name='inspection_marker_P1']")
        assert all(not zone.findall(".//collision") for zone in zones)
    fov = float(
        ET.parse(ROOT / "simulation/models/roboinspect/model.sdf").findtext(".//horizontal_fov")
    )
    for name, zone in layout["inspection_zones"].items():
        assert goals[name] == zone["pose"]
        x, y, yaw = zone["pose"]
        assert yaw == pytest.approx(math.pi / 2)
        # The camera sits 0.29 m ahead of base_link. Both panel edges must fit.
        for point in zone["panels"]:
            px, py, _ = layout["inspection_points"][point]["panel_xyz"]
            assert py > y
            for edge in [-0.65, 0.65]:
                assert abs(math.atan2(px + edge - x, py - 0.145 - y - 0.29)) < fov / 2
        assert min(zone["size"]) > 1.0


def test_zone_overlay_native_and_navigation_frames_agree():
    zone = {"A": {"pose": [-9, 5, math.pi / 2], "size": [2, 1.4]}}
    nav = {"frame": "map", "origin": [-16, -12, 0], "resolution": 0.05, "width": 640, "height": 480}
    native = {**nav, "frame": "map_slam", "origin": [-5, -5, 0]}
    assert project_zones(nav, zone) == project_zones(native, zone)
    marker = project_zones(nav, zone)[0]
    assert marker["name"] == "A"
    assert marker["width"] == pytest.approx(6.25)
