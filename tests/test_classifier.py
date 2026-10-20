import hashlib
import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from PIL import Image

from roboinspect.banner_conditions import MODES, source_splits
from roboinspect.classifier import (
    classification_metrics,
    fit_ridge,
    freeze_dataset,
    image_features,
    preprocess_image,
    ridge_scores,
    verify_snapshot,
)


@pytest.fixture
def reviewed_data(tmp_path):
    photos = [{"sha256": hashlib.sha256(str(i).encode()).hexdigest()} for i in range(20)]
    (tmp_path / "data/vision").mkdir(parents=True)
    (tmp_path / "data/vision/photos.json").write_text(json.dumps(photos))
    partition = source_splits(photos)
    for split in ("train", "validation", "test"):
        group = next(g for g, p in partition.items() if p == split)
        for i, condition in enumerate(MODES):
            identity = str(uuid4())
            folder = tmp_path / "data/dataset/samples" / identity
            folder.mkdir(parents=True)
            Image.new("RGB", (80, 80), (i * 30, len(split) * 20, 30)).save(folder / "crop.jpg")
            Image.new("RGB", (90, 90), (i * 30, len(split) * 20, 30)).save(folder / "frame.jpg")
            row = {
                "id": identity,
                "created_at": "2026-10-19T00:00:00Z",
                "split": split,
                "condition": condition,
                "review_status": "approved",
                "training_ready": True,
                "roi_xyxy": [0, 0, 80, 80],
                "source_group": group,
                "scene_source_groups": [group],
                "crop_sha256": hashlib.sha256((folder / "crop.jpg").read_bytes()).hexdigest(),
                "frame_sha256": hashlib.sha256((folder / "frame.jpg").read_bytes()).hexdigest(),
            }
            (folder / "metadata.json").write_text(json.dumps(row))
    return tmp_path


def test_freeze_is_repeatable_and_independent_of_later_live_edits(reviewed_data):
    root = reviewed_data
    path = freeze_dataset(root)
    manifest = verify_snapshot(path)
    assert path == freeze_dataset(root)
    assert len(manifest["records"]) == 15
    live = next((root / "data/dataset/samples").glob("*/metadata.json"))
    row = json.loads(live.read_text())
    row["review_status"] = "rejected"
    row["training_ready"] = False
    live.write_text(json.dumps(row))
    assert len(verify_snapshot(path)["records"]) == 15
    with pytest.raises(ValueError, match="wszystkie klasy"):
        freeze_dataset(root)


def test_unreviewed_data_are_never_silently_used(reviewed_data):
    live = next((reviewed_data / "data/dataset/samples").glob("*/metadata.json"))
    row = json.loads(live.read_text())
    row["review_status"] = "pending_review"
    row["training_ready"] = False
    live.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="wszystkie klasy"):
        freeze_dataset(reviewed_data)


def test_freeze_refuses_changed_pixels(reviewed_data):
    image = next((reviewed_data / "data/dataset/samples").glob("*/crop.jpg"))
    image.write_bytes(b"changed")
    with pytest.raises(ValueError, match="obraz"):
        freeze_dataset(reviewed_data)


def test_snapshot_refuses_manifest_tampering(reviewed_data):
    path = freeze_dataset(reviewed_data)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["records"][0]["condition"] = "dirty"
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest"):
        verify_snapshot(path)


def test_snapshot_refuses_frozen_pixel_tampering(reviewed_data):
    path = freeze_dataset(reviewed_data)
    next((path / "images").glob("*.jpg")).write_bytes(b"changed")
    with pytest.raises(ValueError, match="obraz"):
        verify_snapshot(path)


def test_snapshot_does_not_allow_source_group_leakage(reviewed_data):
    for file in (reviewed_data / "data/dataset/samples").glob("*/metadata.json"):
        row = json.loads(file.read_text())
        if row["split"] == "test":
            row["scene_source_groups"].append(
                next(
                    g
                    for g, p in source_splits(
                        json.loads((reviewed_data / "data/vision/photos.json").read_text())
                    ).items()
                    if p == "train"
                )
            )
            file.write_text(json.dumps(row))
            break
    with pytest.raises(ValueError, match="podział"):
        freeze_dataset(reviewed_data)


def test_metrics_have_expected_matrix_and_macro_f1():
    result = classification_metrics([0, 0, 1, 1, 2, 3, 4], [0, 1, 1, 1, 2, 3, 4])
    assert result["accuracy"] == pytest.approx(6 / 7)
    assert result["confusion_matrix"][0][1] == 1
    assert result["per_class"]["clean"]["recall"] == 0.5
    assert result["per_class"]["cracked"]["precision"] == pytest.approx(2 / 3)
    assert result["macro_f1"] == pytest.approx((2 / 3 + 0.8 + 1 + 1 + 1) / 5)
    with pytest.raises(ValueError):
        classification_metrics([], [])
    with pytest.raises(ValueError):
        classification_metrics([5], [0])


def test_preprocessing_retains_board_edges_and_feature_shape():
    image = Image.new("RGB", (400, 200), "white")
    image.putpixel((0, 0), (255, 0, 0))
    ready = preprocess_image(image)
    assert ready.size == (224, 224) and ready.getpixel((100, 0)) == (128, 128, 128)
    feature = image_features(image)
    assert feature.shape == (106,) and np.isfinite(feature).all()


def test_ridge_fits_only_supplied_training_samples():
    x = np.repeat(np.eye(5), 4, axis=0)
    labels = np.repeat(np.arange(5), 4)
    model = fit_ridge(x, labels, 1.0)
    assert ridge_scores(model, np.eye(5)).argmax(1).tolist() == list(range(5))
    before = model["mean"].copy()
    ridge_scores(model, np.ones((1, 5)) * 1000)
    assert np.array_equal(before, model["mean"])


def test_training_report_routes_before_any_training(service, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from roboinspect.api import create_app

    (tmp_path / "config").mkdir()
    (tmp_path / "config/hangar.json").write_bytes(
        (Path(__file__).resolve().parents[1] / "config/hangar.json").read_bytes()
    )
    monkeypatch.setattr("roboinspect.api.ROOT", tmp_path)
    with TestClient(create_app(service), base_url="http://127.0.0.1:8765") as client:
        assert client.get("/api/classifier/training").json() == {"trained": False}
        assert client.get("/classifier").status_code == 200
        assert "Nie wykonano" in client.get("/classifier").text
        assert client.get("/api/classifier/artifacts/arbitrary.svg").status_code == 404


def test_result_reader_refuses_paths_outside_run_storage(tmp_path):
    from roboinspect.classifier_results import latest_result

    path = tmp_path / "data/classifier"
    path.mkdir(parents=True)
    (path / "latest.json").write_text(
        json.dumps({"results": str(tmp_path / "outside/results.json"), "snapshot_id": "x"})
    )
    with pytest.raises(ValueError, match="wynik"):
        latest_result(tmp_path)
