import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from roboinspect.api import create_app
from roboinspect.banner_conditions import MODES, build_scene, render_condition, source_splits
from roboinspect.banners import assignments
from roboinspect.contracts import BannerConditionRequest, ConflictError, WarehouseAction
from roboinspect.dataset import analyze, collect_observation, roi_for_panel, samples
from roboinspect.operations import request_warehouse

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scene(tmp_path):
    meshes = tmp_path / "data/vision/meshes"
    meshes.mkdir(parents=True)
    photos = []
    for i in range(24):
        image = Image.fromarray(np.tile(np.arange(128, dtype=np.uint8), (128, 1))).convert("RGB")
        image.putpixel((0, 0), (i, 0, 0))
        image.save(meshes / f"{i}.jpg")
        (meshes / f"{i}.obj").write_text(f"mtllib {i}.mtl\n")
        photos.append(
            {
                "id": str(i),
                "sha256": hashlib.sha256(f"source-{i}".encode()).hexdigest(),
                "source": "https://example.com/photo/" + str(i),
            }
        )
    (tmp_path / "data/vision/photos.json").write_text(json.dumps(photos))
    (tmp_path / "config").mkdir()
    (tmp_path / "config/hangar.json").write_bytes((ROOT / "config/hangar.json").read_bytes())
    profile = {"mode": "mixed", "split": "train", "collect": True, "seed": 42}
    selected = assignments(7, tmp_path, split="train")
    built = build_scene(selected, photos, profile, tmp_path)
    return tmp_path, photos, built


def test_source_groups_do_not_cross_splits_even_with_duplicate_source_ids(scene):
    root, photos, _ = scene
    plan = source_splits(photos + [dict(photos[0], id="copy")])
    assert len(plan) == 24
    assert {v: list(plan.values()).count(v) for v in set(plan.values())} == {
        "train": 14,
        "validation": 5,
        "test": 5,
    }
    for split in ["train", "validation", "test"]:
        selected = assignments(42, root, split=split)
        assert all(
            plan[next(p["sha256"] for p in photos if p["id"] == i)] == split
            for i in selected.values()
        )


@pytest.mark.parametrize("condition", MODES)
def test_transform_is_reproducible_and_has_no_text_label(condition):
    source = Image.fromarray(np.tile(np.arange(256, dtype=np.uint8), (256, 1))).convert("RGB")
    a = render_condition(source, condition, 42)
    b = render_condition(source, condition, 42)
    assert a.tobytes() == b.tobytes() and a.size == source.size
    if condition == "clean":
        assert a.tobytes() == source.tobytes()
    elif condition == "missing":
        assert np.asarray(a).std() < 3
    else:
        assert np.mean(np.asarray(a) != np.asarray(source)) > 0.01


def test_mixed_scene_has_every_class_once_and_replays_assets(scene):
    root, photos, built = scene
    assert {p["condition"] for p in built["panels"].values()} == set(MODES)
    repeated = build_scene(assignments(7, root, split="train"), photos, built["profile"], root)
    assert repeated == built
    assert all(
        (root / "data/vision/meshes" / p["mesh"]).is_file() for p in built["panels"].values()
    )
    assert all(p["mesh"].startswith("variant_") for p in built["panels"].values())


def observation(root, scene, panel="P1"):
    identity = str(uuid4())
    directory = root / "data/inspections" / identity
    directory.mkdir(parents=True)
    image = Image.fromarray(
        np.tile(np.arange(1280, dtype=np.uint16).astype(np.uint8), (720, 1))
    ).convert("RGB")
    image.save(directory / "raw.jpg")
    return dict(
        id=identity,
        mission_id=str(uuid4()),
        created_at="2026-10-19T12:00:00+00:00",
        panel=panel,
        sector="A",
        camera_sequence=1,
        camera_stamp_s=5.0,
        position={"x": -11.0, "y": 6.6},
        heading=math.pi / 2,
    )


def test_camera_sample_keeps_provenance_and_requires_review(scene):
    root, photos, built = scene
    report = observation(root, built)
    row = collect_observation(report, built, root)
    assert (
        row["status"] == "collected"
        and row["review_status"] == "pending_review"
        and not row["training_ready"]
    )
    assert row["condition"] == built["panels"]["P1"]["condition"]
    assert row["source_group"] == built["panels"]["P1"]["source_sha256"]
    assert row["label_origin"] == "synthetic_scene_manifest"
    assert (root / "data/dataset/samples" / row["id"] / "frame.jpg").read_bytes() == (
        root / "data/inspections" / report["id"] / "raw.jpg"
    ).read_bytes()
    assert samples(root)[0]["roi_xyxy"] == roi_for_panel(
        "P1", report["position"], report["heading"], 1280, 720, root
    )
    with pytest.raises(ValueError):
        roi_for_panel("P1", report["position"], -math.pi / 2, 1280, 720, root)


def test_collection_rejects_scene_with_sources_from_a_different_split(scene):
    root, photos, built = scene
    report = observation(root, built)
    built["profile"]["split"] = "test"
    with pytest.raises(ValueError, match="grupy"):
        collect_observation(report, built, root)
    assert not samples(root)


def test_eda_exposes_leakage_instead_of_declaring_training_ready(scene):
    root, _, built = scene
    a = collect_observation(observation(root, built), built, root)
    b = dict(a, id=str(uuid4()), split="test")
    folder = root / "data/dataset/samples" / b["id"]
    folder.mkdir()
    import shutil

    for file in ["frame.jpg", "crop.jpg"]:
        shutil.copyfile(root / "data/dataset/samples" / a["id"] / file, folder / file)
    (folder / "metadata.json").write_text(json.dumps(b))
    result = analyze(root)
    assert result["leakage_errors"] and result["duplicates"] and not result["training_allowed"]
    assert result["training_ready"] == 0 and result["samples"] == 2
    assert (root / "data/dataset/reports/report.html").is_file()


def test_conditions_are_durable_idempotent_and_blocked_during_motion(service):
    service.robot.state.update(mapping_controls=True, scenario="normal", mode="navigation")
    profile = BannerConditionRequest(mode="mixed", split="train")
    job, _ = request_warehouse(service, WarehouseAction.CONDITIONS, "conditions", profile)
    assert job.banner_profile == profile and job.layout_seed is not None
    assert (
        request_warehouse(service, WarehouseAction.CONDITIONS, "conditions", profile)[0].id
        == job.id
    )
    with pytest.raises(ConflictError):
        request_warehouse(
            service, WarehouseAction.CONDITIONS, "conditions", BannerConditionRequest(mode="dirty")
        )
    with pytest.raises(ConflictError):
        request_warehouse(service, WarehouseAction.CONDITIONS, "other", profile)


def test_condition_api_rejects_unknown_modes_and_external_origin(service):
    service.robot.state.update(mapping_controls=True, scenario="normal", mode="navigation")
    with TestClient(create_app(service), base_url="http://127.0.0.1:8765") as client:
        headers = {"Idempotency-Key": "profile"}
        assert (
            client.post(
                "/api/banners/condition", json={"mode": "arbitrary"}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/banners/condition",
                json={"mode": "mixed"},
                headers={**headers, "Origin": "https://external.test"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/banners/condition", json={"mode": "mixed"}, headers=headers
            ).status_code
            == 202
        )
        assert (
            client.post(
                "/api/banners/condition", json={"mode": "mixed"}, headers=headers
            ).status_code
            == 200
        )


def test_canceled_inspection_never_appends_dataset_sample(service, monkeypatch):
    from concurrent.futures import Future

    from roboinspect.inspection import InspectionService

    inspector = InspectionService(service.store)
    inspector.future = Future()
    inspector.future.set_result({"collection_scene": {"profile": {"collect": True}}})
    inspector.cancel.set()
    monkeypatch.setattr(
        "roboinspect.dataset.collect_observation",
        lambda *a: pytest.fail("Canceled observation must not enter the dataset"),
    )
    with pytest.raises(RuntimeError, match="anulowana"):
        inspector.poll()
    inspector.close()


def test_empty_eda_is_explicitly_not_ready_for_training(tmp_path):
    result = analyze(tmp_path)
    assert result["samples"] == 0 and result["training_allowed"] is False
    assert set(result["missing_conditions"]) == set(MODES)
    assert set(result["missing_splits"]) == {"train", "validation", "test"}
    assert (tmp_path / "data/dataset/reports/samples.csv").read_text().startswith("id,condition")


def test_review_preserves_provenance_supports_undo_and_detects_conflicts(scene):
    from roboinspect.contracts import DatasetReviewRequest
    from roboinspect.dataset import list_samples, review_sample, revision, summary

    root, _, built = scene
    row = collect_observation(observation(root, built), built, root)
    request = DatasetReviewRequest(
        decision="approved",
        condition="dirty",
        expected_revision=revision(row),
        note="Sprawdzony wycinek",
    )
    reviewed = review_sample(row["id"], request, root)
    assert reviewed["training_ready"] and reviewed["condition"] == "dirty"
    assert reviewed["original_condition"] == row["condition"]
    assert reviewed["original_label_origin"] == "synthetic_scene_manifest"
    assert reviewed["label_origin"] == "human_review" and len(reviewed["review_history"]) == 1
    assert summary(root)["training_ready"] == 1 and summary(root)["pending_review"] == 0
    assert list_samples(root, status="pending")["total"] == 0
    with pytest.raises(ConflictError):
        review_sample(row["id"], request, root)
    request = DatasetReviewRequest(
        decision="rejected", condition="dirty", expected_revision=reviewed["revision"]
    )
    rejected = review_sample(row["id"], request, root)
    assert not rejected["training_ready"] and summary(root)["rejected"] == 1
    assert list_samples(root, status="rejected", split="train", condition="dirty")["total"] == 1
    restored = review_sample(
        row["id"],
        DatasetReviewRequest(
            decision="pending_review", condition="clean", expected_revision=rejected["revision"]
        ),
        root,
    )
    assert not restored["training_ready"] and len(restored["review_history"]) == 3
    assert list_samples(root, status="pending")["total"] == 1
    assert restored["source_group"] == row["source_group"] and restored["split"] == row["split"]


@pytest.mark.parametrize("damage", ["crop", "hash", "split"])
def test_review_cannot_approve_invalid_artifacts(scene, damage):
    from roboinspect.contracts import DatasetReviewRequest
    from roboinspect.dataset import review_sample, revision

    root, _, built = scene
    row = collect_observation(observation(root, built), built, root)
    folder = root / "data/dataset/samples" / row["id"]
    if damage == "crop":
        row["crop_sha256"] = None
    elif damage == "hash":
        (folder / "crop.jpg").write_bytes(b"changed")
    else:
        row["split"] = "test"
    (folder / "metadata.json").write_text(json.dumps(row))
    with pytest.raises(ValueError):
        review_sample(
            row["id"],
            DatasetReviewRequest(
                decision="approved", condition="clean", expected_revision=revision(row)
            ),
            root,
        )
    assert samples(root)[0]["review_status"] == "pending_review"


def test_review_api_validation_filtering_and_external_origin(scene, service, monkeypatch):
    from roboinspect.dataset import revision

    root, _, built = scene
    row = collect_observation(observation(root, built), built, root)
    monkeypatch.setattr("roboinspect.api.ROOT", root)
    with TestClient(create_app(service), base_url="http://127.0.0.1:8765") as client:
        url = f"/api/dataset/samples/{row['id']}/review"
        payload = dict(decision="approved", condition="clean", expected_revision=revision(row))
        assert client.get("/api/dataset/samples?status=pending").json()["total"] == 1
        assert client.get("/api/dataset/samples?status=invalid").status_code == 422
        assert client.post(url, json={**payload, "condition": "arbitrary"}).status_code == 422
        assert (
            client.post(url, json=payload, headers={"Origin": "https://external.test"}).status_code
            == 403
        )
        assert client.post(url, json=payload).status_code == 200
        assert client.post(url, json=payload).status_code == 409
        assert client.get("/api/dataset/samples?status=approved").json()["total"] == 1
        assert client.get("/api/dataset/samples?status=pending").json()["total"] == 0


def test_eda_exports_review_decisions_and_excludes_rejected_from_class_coverage(scene):
    from roboinspect.contracts import DatasetReviewRequest
    from roboinspect.dataset import review_sample, revision

    root, _, built = scene
    row = collect_observation(observation(root, built), built, root)
    review_sample(
        row["id"],
        DatasetReviewRequest(
            decision="rejected", condition="dirty", expected_revision=revision(row)
        ),
        root,
    )
    result = analyze(root)
    assert result["rejected"] == 1 and result["pending_review"] == 0
    assert result["conditions_by_split"]["train"] == {}
    assert set(result["approved_missing_by_split"]["train"]) == set(MODES)
    assert (
        "training_ready" in (root / "data/dataset/reports/samples.csv").read_text().splitlines()[0]
    )
    assert result["training_allowed"] is False


def test_explicit_capture_profile_does_not_change_interactive_profile(scene):
    import xml.etree.ElementTree as ET

    from roboinspect.banners import decorate

    root, _, _ = scene
    saved = root / "data/vision/conditions.json"
    original = {"mode": "clean", "split": "train", "collect": False, "seed": 123}
    saved.write_text(json.dumps(original))
    source = root / "world.sdf"
    source.write_text(
        '<sdf version="1.9"><world name="test">'
        + "".join(f'<model name="panel_P{i}"><link name="body"/></model>' for i in range(1, 6))
        + "</world></sdf>"
    )
    profile = {"mode": "mixed", "split": "validation", "collect": True, "seed": 42}
    world, _ = decorate(source, 42, root, profile=profile)
    scene_record = json.loads(world.with_suffix(".json").read_text())
    assert scene_record["profile"] == profile
    assert json.loads(saved.read_text()) == original
    assert len(ET.parse(world).getroot().findall('.//visual[@name="banner_photo"]')) == 5


def test_staged_capture_keeps_acquisition_provenance(scene):
    root, _, built = scene
    report = observation(root, built)
    report.update(
        collection_mode="staged_static_robot_camera",
        acquisition_batch="test-batch",
        pose_source="gazebo_set_pose_static_fixture",
        sim_robot_pose={"x": -11, "y": 6.6, "z": 0, "yaw": math.pi / 2},
    )
    row = collect_observation(report, built, root)
    assert row["collection_mode"] == "staged_static_robot_camera"
    assert row["acquisition_batch"] == "test-batch"
    assert row["pose_source"] == "gazebo_set_pose_static_fixture"
    assert row["sim_robot_pose"] == report["sim_robot_pose"]
    assert row["training_ready"] is False
