import math
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from roboinspect.api import create_app
from roboinspect.routes import (
    ROOT,
    SEGMENTS,
    RouteState,
    clean_path,
    costmap_obstacles,
    hangar_layout,
    sample_segments,
    visual_message,
)


def test_route_is_real_fresh_and_clears_after_cancellation():
    route = RouteState()
    assert not route.update([[0, 0], [3, 4]], "map", 20, now=1)
    route.begin([3, 4, 0], 20)
    assert not route.update([[0, 0], [3, 4]], "odom", 21, now=1)
    assert not route.update([[0, 0], [3, 4]], "map", 19, now=1)
    assert route.update([[0, 0], [3, 4]], "map", 21, now=1)
    assert route.snapshot(True, now=2)["status"] == "live"
    assert route.snapshot(True, now=5)["points"] == []
    assert route.snapshot(False, now=2)["goal"] is None
    route.clear()
    assert route.snapshot(True, now=2)["status"] == "idle"


def test_previous_goal_or_out_of_order_plan_cannot_replace_current():
    route = RouteState()
    route.begin([3, 4, 0], 20)
    assert route.update([[0, 0], [3, 4]], "map", 23, now=1)
    assert not route.update([[0, 0], [3, 4]], "map", 22, now=2)
    route.begin([8, 8, 0], 24)
    assert not route.update([[0, 0], [3, 4]], "map", 25, now=2)
    assert route.snapshot(True, now=3)["status"] == "waiting"
    assert route.snapshot(True, now=3)["goal"] == [8, 8]


@pytest.mark.parametrize(
    "points",
    [[[0, 0], [math.nan, 1]], [[0, 0], [99, 0]], [[0, 0]], [[0, 0], [0, 0]], [[0, 0], [1, 1]]],
)
def test_bad_or_unrelated_paths_are_not_drawn(points):
    assert clean_path(points, [3, 4]) == []


def test_sampling_keeps_corners_and_cost_bounded():
    samples = sample_segments([[0, 0], [10, 0], [10, 10]])
    assert len(samples) <= SEGMENTS
    assert all(0 <= x <= 10 and 0 <= y <= 10 for x, y, _ in samples)
    assert samples[0][2] == pytest.approx(0)
    assert samples[-1][2] == pytest.approx(math.pi / 2)
    assert len(sample_segments([[0, 0], [30, 0], [30, 20], [-30, 20]])) == SEGMENTS


def test_visual_messages_hide_every_unused_element_and_final_goal():
    hidden = visual_message({"points": [], "goal": None})
    assert hidden.count("pose {") == SEGMENTS + 1
    assert hidden.count("z:-2") == SEGMENTS + 1
    active = visual_message({"points": [[0, 0], [2, 0]], "goal": [2, 0]})
    assert 'route_goal" position { x:2.0000 y:0.0000 z:0.045' in active
    assert "nan" not in active


def test_costmap_uses_lethal_cells_only_and_ros_coordinates():
    boxes = costmap_obstacles([0, 99, 100, 100, 0, 100], 3, 2, 0.5, (-1, -2, 0))
    assert boxes == [[0, 0.5, -2, -1.5], [-1, -0.5, -1.5, -1], [0, 0.5, -1.5, -1]]
    assert costmap_obstacles([100], 2, 2, 0.1, (0, 0, 0)) == []
    assert costmap_obstacles([100], 1, 1, 0.1, (0, 0, 1)) == []


def test_visuals_never_have_collision_or_appear_in_hangar_obstacles():
    for scenario in ["normal", "blocked", "unreachable"]:
        data = hangar_layout(scenario)
        world = (
            ET.parse(ROOT / f"simulation/worlds/hangar_{scenario}_robot.sdf")
            .getroot()
            .find("world")
        )
        visuals = [m for m in world.findall("model") if m.get("name", "").startswith("route_")]
        assert len(visuals) == SEGMENTS + 1
        assert all(not v.findall(".//collision") for v in visuals)
        assert all(float(v.findtext("pose").split()[2]) < 0 for v in visuals)
        assert data["obstacles"]
        assert len(data["zones"]) == 3


def test_overview_api_is_scenario_specific_and_read_only(service):
    with TestClient(create_app(service), base_url="http://127.0.0.1:8765") as client:
        result = client.get("/api/hangar")
        assert result.status_code == 200
        assert result.json()["scenario"] == "normal"
        assert result.json()["bounds"] == [-15, 15, -11, 11]
        assert client.get("/route-map.js").status_code == 200
        assert not service.robot.calls


def test_old_world_clock_and_delayed_plan_cannot_look_fresh():
    route = RouteState()
    route.begin([3, 4, 0], 2)
    assert not route.update([[0, 0], [3, 4]], "map", 500, now=1, simulation_time=3)
    assert not route.update([[0, 0], [3, 4]], "map", 3, now=1, simulation_time=10)
    assert route.update([[0, 0], [3, 4]], "map", 10, now=1, simulation_time=10)
