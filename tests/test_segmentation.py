import base64
import io
from concurrent.futures import Future
from copy import deepcopy
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from roboinspect.api import create_app
from roboinspect.inspection import (
    CaptureResult,
    InspectionService,
    evidence_answer,
    inspection_question,
    list_reports,
)
from roboinspect.segmentation import validate_artifacts


def sample():
    width, height = 32, 24
    masks = np.zeros((2, height, width), dtype=np.uint8)
    masks[0, 2:12, 3:14] = 1
    masks[1, 5:18, 9:24] = 1
    labels = np.zeros((height, width), dtype=np.uint8)
    labels[masks[1].astype(bool)] = 2
    labels[masks[0].astype(bool)] = 1

    def image(data, fmt):
        stream = io.BytesIO()
        Image.fromarray(data).save(stream, format=fmt)
        return base64.b64encode(stream.getvalue()).decode()

    buffer = io.BytesIO()
    np.savez_compressed(buffer, packed=np.packbits(masks, axis=2))
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    return dict(
        detections=[
            dict(label="person", instance=i + 1, confidence=0.9, xyxy=[1, 1, 30, 23])
            for i in range(2)
        ],
        counts={"person": 2},
        total=2,
        width=width,
        height=height,
        inference_seconds=0.03,
        model="YOLO11s",
        device="cuda:0",
        raw_jpeg=image(rgb, "JPEG"),
        annotated_jpeg=image(rgb, "JPEG"),
        camera_stamp_s=10.0,
        camera_sequence=5,
        warehouse=None,
        position={"x": 0, "y": 0},
        segmentation=dict(
            model="SAM 2.1 Tiny",
            weights_sha256="a" * 64,
            device="cuda:0",
            status="complete",
            masks=[
                dict(
                    detection_index=i + 1,
                    pixels=int(mask.sum()),
                    image_fraction=float(mask.mean()),
                    predicted_iou=0.92,
                    color=[66, 211, 146],
                )
                for i, mask in enumerate(masks)
            ],
            seconds=0.3,
            message="Maski",
            gpu_allocated_mib=500.0,
            gpu_peak_allocated_mib=650.0,
        ),
        segmented_jpeg=image(rgb, "JPEG"),
        mask_png=image(labels, "PNG"),
        masks_npz=base64.b64encode(buffer.getvalue()).decode(),
    )


def test_overlapping_masks_remain_separate_and_match_detection_order():
    payload = sample()
    result = CaptureResult.model_validate(payload).model_dump()
    validate_artifacts(
        *[base64.b64decode(result[k]) for k in ["segmented_jpeg", "mask_png", "masks_npz"]],
        result["width"],
        result["height"],
        result["total"],
        result["segmentation"]["masks"],
    )
    packed = np.load(io.BytesIO(base64.b64decode(result["masks_npz"])), allow_pickle=False)[
        "packed"
    ]
    masks = np.unpackbits(packed, axis=2, count=result["width"])
    assert (masks[0] & masks[1]).sum() > 0
    assert int(masks[0].sum()) == 110 and int(masks[1].sum()) == 195


@pytest.mark.parametrize("mutation", ["duplicate", "index", "pixels", "missing", "bad_status"])
def test_malformed_segmentation_is_rejected(mutation):
    data = sample()
    if mutation == "duplicate":
        data["segmentation"]["masks"][1]["detection_index"] = 1
    if mutation == "index":
        data["segmentation"]["masks"][1]["detection_index"] = 3
    if mutation == "pixels":
        data["segmentation"]["masks"][0]["pixels"] = 100000
    if mutation == "missing":
        data["mask_png"] = None
    if mutation == "bad_status":
        data["segmentation"]["status"] = "error"
    with pytest.raises(ValidationError):
        CaptureResult.model_validate(data)


def test_masks_pixels_and_archive_are_validated_not_just_metadata():
    data = sample()
    blobs = [base64.b64decode(data[k]) for k in ["segmented_jpeg", "mask_png", "masks_npz"]]
    changed = deepcopy(data["segmentation"]["masks"])
    changed[0]["pixels"] = 9
    with pytest.raises(ValueError, match="powierzchni"):
        validate_artifacts(*blobs, 32, 24, 2, changed)
    archive = io.BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as z:
        z.writestr("packed.npy", b"0" * 100000)
    with pytest.raises(ValueError, match="duże"):
        validate_artifacts(
            blobs[0], blobs[1], archive.getvalue(), 32, 24, 2, data["segmentation"]["masks"]
        )


def test_sam_error_preserves_yolo_and_legacy_captures():
    data = sample()
    data["segmentation"].update(status="error", masks=[])
    for key in ["segmented_jpeg", "mask_png", "masks_npz"]:
        data[key] = None
    assert CaptureResult.model_validate(data).total == 2
    data.pop("segmentation")
    assert CaptureResult.model_validate(data).segmentation is None


def test_segmentation_artifacts_survive_report_and_api_restart(service, tmp_path, monkeypatch):
    import roboinspect.inspection as module

    (tmp_path / "config").mkdir()
    (tmp_path / "config/hangar.json").write_text((module.ROOT / "config/hangar.json").read_text())
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr("roboinspect.api.ROOT", tmp_path)
    payload = sample()
    real = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    monkeypatch.setattr(module.httpx, "Client", lambda **kwargs: real(transport=transport))

    class Cancel:
        def wait(self, timeout):
            return False

        def is_set(self):
            return False

    inspector = InspectionService(service.store)
    monkeypatch.setattr(inspector, "log_metrics", lambda result: None)
    try:
        result = inspector.capture("P1", "mission", "execution", Cancel())
        assert "masks_npz" not in result and result["segmentation"]["data_url"].endswith(
            "masks.npz"
        )
        inspector.future = Future()
        inspector.future.set_result(result)
        inspector.poll()
        stored = list_reports(service.store)[0]
        assert stored["segmentation"]["masks"][1]["pixels"] == 195
        monkeypatch.setattr(module.httpx, "Client", real)
        with TestClient(create_app(service), base_url="http://127.0.0.1:8765") as client:
            assert (
                client.get(stored["segmentation"]["image_url"]).headers["content-type"]
                == "image/jpeg"
            )
            assert (
                client.get(stored["segmentation"]["mask_url"]).headers["content-type"]
                == "image/png"
            )
            assert client.get(stored["segmentation"]["data_url"]).status_code == 200
            assert (
                client.get(
                    stored["segmentation"]["data_url"].replace("masks.npz", "unknown.npz")
                ).status_code
                == 404
            )
        assert inspection_question("Ile masek zapisano w sektorze A?")
        answer = evidence_answer(service.store, "Ile masek zapisano w sektorze A?")
        assert "zapisane maski: 2" in answer and "SAM 2.1 Tiny" in answer
    finally:
        inspector.close()


def test_no_detection_does_not_require_masks():
    data = sample()
    data.update(
        detections=[], counts={}, total=0, segmented_jpeg=None, mask_png=None, masks_npz=None
    )
    data["segmentation"].update(status="no_detections", masks=[])
    assert CaptureResult.model_validate(data).segmentation.status == "no_detections"
