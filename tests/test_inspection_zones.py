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


def test_green_observation_pads_match_navigation_goals_and_have_no_collisions():
    from roboinspect.observation import observation_zones

    layout = json.loads((ROOT / "config/hangar.json").read_text())
    goals = json.loads((ROOT / "config/navigation-goals.json").read_text())["poses"]
    for path in (ROOT / "simulation/worlds").glob("hangar_*.sdf"):
        world = ET.parse(path).getroot().find("world")
        pads = [
            m for m in world.findall("model") if m.get("name", "").startswith("observation_pad_")
        ]
        assert len(pads) == 5
        for pad in pads:
            name = pad.get("name").removeprefix("observation_pad_")
            pose = list(map(float, pad.findtext("pose").split()))
            assert pose[:2] == goals[name][:2]
            assert not pad.findall(".//collision")
            px, py, _ = layout["inspection_points"][name]["panel_xyz"]
            assert px == pose[0] and py > pose[1]
    assert set(observation_zones(layout)) == {"P1", "P2", "P3", "P4", "P5"}
