import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from roboinspect.api import create_app
from roboinspect.contracts import (
    ConflictError,
    MappingAction,
    MissionPlan,
    MissionStatus,
    WarehouseAction,
)
from roboinspect.mapping_runner import MappingRunner
from roboinspect.operations import request_operation, request_warehouse
from roboinspect.routes import ROOT, collision_boxes, hangar_layout
from roboinspect.warehouse import (
    MOVABLE,
    persist_selection,
    prepare_layout,
    read_selection,
    validate_access,
)


@pytest.fixture
def scene_root(tmp_path):
    for directory in ["config", "simulation/worlds"]:
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    for name in ["hangar.json", "navigation-goals.json"]:
        shutil.copy(ROOT / "config" / name, tmp_path / "config" / name)
    for name in ["hangar_normal.sdf", "hangar_normal_robot.sdf"]:
        shutil.copy(ROOT / "simulation/worlds" / name, tmp_path / "simulation/worlds" / name)
    return tmp_path


@pytest.mark.parametrize("mode,count", [("standard", 8), ("clear", 0), ("random", 8)])
def test_layout_world_map_and_persistence_are_consistent(scene_root, mode, count):
    result = prepare_layout(mode, 12, scene_root)
    assert result["movable_count"] == count
    robot = ET.parse(result["world"]).getroot().find("world")
    empty = ET.parse(Path(result["world"]).with_name("hangar.sdf")).getroot().find("world")
    assert len(set(MOVABLE) & {m.get("name") for m in robot.findall("model")}) == count
    assert collision_boxes(empty) == collision_boxes(robot)
    assert robot.find("model[@name='roboinspect']") is not None
    assert len([m for m in robot.findall("model") if m.get("name", "").startswith("panel_P")]) == 5
    goals = json.loads((scene_root / "config/navigation-goals.json").read_text())["poses"]
    validate_access(empty, goals)
    persist_selection(result, scene_root)
    assert read_selection(scene_root) == result
    # Source scenes are not overwritten by a UI operation.
    assert (scene_root / "simulation/worlds/hangar_normal.sdf").read_bytes() == (
        ROOT / "simulation/worlds/hangar_normal.sdf"
    ).read_bytes()


@pytest.mark.parametrize("seed", [0, 1, 7, 19, 123, 2026, 65535, 4294967295])
def test_random_layouts_keep_every_goal_and_reserved_corridor_accessible(scene_root, seed):
    result = prepare_layout("random", seed, scene_root)
    world = ET.parse(result["world"]).getroot().find("world")
    config = json.loads((scene_root / "config/hangar.json").read_text())
    for model in world.findall("model"):
        if model.get("name") not in MOVABLE:
            continue
        sector = MOVABLE[model.get("name")]
        center = config["inspection_zones"][sector]["pose"][0]
        copy = ET.Element("world")
        copy.append(model)
        for x1, x2, y1, y2 in collision_boxes(copy):
            assert x2 <= center - 1.09 or x1 >= center + 1.09
            assert y2 <= 3.51
    assert set(result["validated_goals"]) == {"BASE", "A", "B", "C", "P1", "P2", "P3", "P4", "P5"}


def test_seed_replays_the_same_positions_but_new_seeds_change_them(scene_root):
    a = prepare_layout("random", 42, scene_root)
    b = prepare_layout("random", 42, scene_root)
    c = prepare_layout("random", 43, scene_root)
    assert a["placements"] == b["placements"]
    assert a["placements"] != c["placements"]


def enable(service):
    service.robot.state.update(mapping_controls=True, scenario="normal", mode="navigation")


def test_layout_job_is_durable_idempotent_and_excludes_missions(service):
    enable(service)
    record, created = request_warehouse(service, WarehouseAction.RANDOM, "one")
    assert created and record.layout_seed is not None
    repeated, _ = request_warehouse(service, WarehouseAction.RANDOM, "one")
    assert repeated.id == record.id and repeated.layout_seed == record.layout_seed
    with pytest.raises(ConflictError):
        request_warehouse(service, WarehouseAction.CLEAR, "one")
    with pytest.raises(ConflictError):
        service.create(MissionPlan(steps=[{"target": "A"}]), "drive")
    with pytest.raises(ConflictError):
        request_operation(service, MappingAction.WAREHOUSE_CLEAR, "bad-api")


@pytest.mark.parametrize(
    "change",
    [
        {"busy": True},
        {"remote_active": True},
        {"mode": "mapping"},
        {"ready": False},
        {"velocity": {"linear": 0.1, "angular": 0}},
    ],
)
def test_cannot_change_world_during_motion_or_mapping(service, change):
    enable(service)
    service.robot.state.update(change)
    with pytest.raises(ConflictError):
        request_warehouse(service, WarehouseAction.CLEAR, "one")


def test_warehouse_api_rejects_extra_fields_and_records_history(service):
    enable(service)
    with TestClient(create_app(service), base_url="http://127.0.0.1:8765") as client:
        headers = {"Idempotency-Key": "layout"}
        assert (
            client.post(
                "/api/warehouse/random", json={"world": "/etc/passwd"}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/warehouse/random",
                json={},
                headers={**headers, "Origin": "https://other.test"},
            ).status_code
            == 403
        )
        first = client.post("/api/warehouse/random", json={}, headers=headers)
        assert first.status_code == 202
        assert client.post("/api/warehouse/random", json={}, headers=headers).status_code == 200
        assert client.get("/api/history").json()[0]["kind"] == "warehouse"
        assert client.post("/api/mapping/warehouse_random", json={}).status_code == 409
        assert client.get("/activity.js").status_code == 200


def test_runner_applies_layout_and_logs_result(service, tmp_path):
    enable(service)
    record, _ = request_warehouse(service, WarehouseAction.CLEAR, "clear")
    calls = []
    manager = SimpleNamespace(
        change_warehouse=lambda *args: calls.append(args) or {"movable_count": 0}
    )
    runner = MappingRunner(manager, service.store)
    runner.tick()
    result = service.store.operation(record.id)
    assert calls[0][0] == "clear" and result.status == MissionStatus.SUCCEEDED
    assert "BASE" in result.message
    assert not service.store.operation_busy()


def test_canceled_warehouse_job_never_applies_layout(service):
    enable(service)
    record, _ = request_warehouse(service, WarehouseAction.CLEAR, "clear")
    service.store.cancel_operation(record.id)
    runner = MappingRunner(SimpleNamespace(), service.store)
    runner.tick()
    assert service.store.operation(record.id).status == MissionStatus.CANCELED


def test_scene_specific_overview_does_not_reuse_standard_cache(scene_root):
    result = prepare_layout("clear", root=scene_root)
    custom = hangar_layout("normal", result["world"], result["layout_id"])
    assert len(custom["obstacles"]) < len(hangar_layout("normal")["obstacles"])
    assert custom["layout_id"] == result["layout_id"]
