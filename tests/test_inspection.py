import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from roboinspect.api import create_app
from roboinspect.contracts import MissionPlan, MissionStatus
from roboinspect.inspection import evidence_answer, inspection_plan, inspection_question, reports


class Inspector:
    def __init__(self):
        self.calls = []
        self.aborted = False
        self.result = None

    def available(self):
        return True

    def start(self, step, mission):
        self.calls.append(step.target.value)
        self.aborted = False

    def poll(self):
        return self.result

    def abort(self):
        self.aborted = True

    def close(self):
        self.abort()


@pytest.mark.parametrize("sector,points", [("A", ["P1", "P2"]), ("B", ["P3", "P4"]), ("C", ["P5"])])
def test_inspection_plan_visits_each_board_and_returns_to_sector(sector, points):
    plan = inspection_plan(sector)
    assert plan.steps[0].target == sector and plan.steps[-1].target == sector
    assert [s.target for s in plan.steps if s.action == "inspect"] == points
    for i, s in enumerate(plan.steps):
        if s.action == "inspect":
            assert plan.steps[i - 1].action == "navigate" and plan.steps[i - 1].target == s.target


@pytest.mark.parametrize(
    "steps",
    [
        [{"action": "inspect", "target": "P1"}],
        [{"target": "A"}, {"action": "inspect", "target": "P1"}],
        [{"target": "A"}, {"action": "inspect", "target": "A"}],
    ],
)
def test_arbitrary_capture_without_board_approach_is_rejected(steps):
    with pytest.raises(ValidationError):
        MissionPlan(steps=steps)


def test_inspection_waits_for_navigation_then_analysis_and_cancel_skips_rest(service):
    detector = Inspector()
    service.inspector = detector
    record, _ = service.create(inspection_plan("A"), "inspect")
    service.tick()
    assert service.robot.calls == ["A"] and not detector.calls
    service.robot.finish()
    service.tick()
    assert service.robot.calls == ["A", "P1"]
    service.tick()
    assert not detector.calls
    service.robot.finish()
    service.tick()
    assert detector.calls == ["P1"]
    service.tick()
    assert service.store.get(record.id).current_step == 2
    service.cancel()
    assert detector.aborted
    detector.result = {"total": 2}
    service.tick()
    assert service.store.get(record.id).status == MissionStatus.CANCELED
    assert service.robot.calls == ["A", "P1"]


def test_completed_capture_advances_to_next_board_once(service):
    detector = Inspector()
    service.inspector = detector
    record, _ = service.create(inspection_plan("A"), "inspect")
    service.tick()
    service.robot.finish()
    service.tick()
    service.robot.finish()
    service.tick()
    detector.result = {"total": 2}
    service.tick()
    assert service.robot.calls == ["A", "P1", "P2"]
    assert service.store.get(record.id).steps[2].status == "succeeded"


def test_detector_failure_does_not_complete_or_dispatch_rest(service):
    detector = Inspector()
    service.inspector = detector
    service.create(inspection_plan("A"), "inspect")
    service.tick()
    service.robot.finish()
    service.tick()
    service.robot.finish()
    service.tick()
    detector.poll = lambda: (_ for _ in ()).throw(RuntimeError("camera unavailable"))
    service.tick()
    assert service.summary().status == MissionStatus.FAILED
    assert service.robot.calls == ["A", "P1"]


def test_inspection_requires_ready_detector_and_api_is_guarded(service):
    app = create_app(service)
    client = TestClient(app, base_url="http://127.0.0.1:8765")
    headers = {"Idempotency-Key": "capture"}
    assert client.post("/api/inspect/A", json={}, headers=headers).status_code == 409
    service.inspector = Inspector()
    assert (
        client.post(
            "/api/inspect/A", json={}, headers={**headers, "Origin": "http://evil.test"}
        ).status_code
        == 403
    )
    first = client.post("/api/inspect/A", json={}, headers=headers)
    second = client.post("/api/inspect/A", json={}, headers=headers)
    assert first.status_code == 202 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert (
        client.post("/api/inspect/Z", json={}, headers={"Idempotency-Key": "z"}).status_code == 409
    )


def test_evidence_reports_latest_mission_not_sum_of_repeated_visits(service):
    with service.store.engine.begin() as c:
        for i, mission in enumerate(["old", "new", "new"]):
            row = {
                "id": str(i),
                "execution_id": str(i),
                "created_at": f"2026-10-19T12:00:0{i}+00:00",
                "mission_id": mission,
                "sector": "A",
                "panel": "P1" if i < 2 else "P2",
                "detections": [{"label": "person", "instance": 1, "confidence": 0.91}],
                "total": 1,
            }
            c.execute(
                reports.insert().values(
                    id=str(i), execution_id=str(i), created_at=row["created_at"], record=row
                )
            )
    answer = evidence_answer(service.store, "Co robot widział w sektorze A?")
    assert answer.count("person 1") == 2
    assert "P1" in answer and "P2" in answer and "91%" in answer
    assert "Nie mam" in evidence_answer(service.store, "Co widział w sektorze B?")
    assert inspection_question("Ile detekcji było w sektorze A?")
    assert not inspection_question("Jedź do A")


def test_photo_selection_and_texture_do_not_change_collisions(tmp_path):
    import json
    import shutil
    import xml.etree.ElementTree as ET

    from roboinspect.banners import assignments, decorate
    from roboinspect.routes import ROOT, collision_boxes

    (tmp_path / "data/vision").mkdir(parents=True)
    (tmp_path / "config").mkdir()
    shutil.copy(ROOT / "config/hangar.json", tmp_path / "config/hangar.json")
    (tmp_path / "data/vision/photos.json").write_text(
        json.dumps([{"id": str(i)} for i in range(24)])
    )
    selected = assignments(3, tmp_path)
    assert len(set(selected.values())) == 5
    assert selected == assignments(3, tmp_path) and selected != assignments(4, tmp_path)
    source = ROOT / "simulation/worlds/hangar_normal_robot.sdf"
    target, _ = decorate(source, 3, tmp_path)
    original = ET.parse(source).getroot().find("world")
    decorated = ET.parse(target).getroot().find("world")
    assert collision_boxes(original) == collision_boxes(decorated)
    for panel in selected:
        assert (
            decorated.find(
                f"model[@name='panel_{panel}']/link/visual[@name='banner_photo']/geometry/mesh/uri"
            )
            is not None
        )
    assert decorated.find(".//sensor[@name='front_camera']/camera/image/width").text == "1280"


def test_capture_validation_rejects_inconsistent_counts_and_outside_boxes():
    from roboinspect.inspection import CaptureResult

    data = dict(
        detections=[dict(label="person", instance=1, confidence=0.8, xyxy=[1, 2, 30, 40])],
        counts={"person": 1},
        total=1,
        width=1280,
        height=720,
        inference_seconds=0.1,
        model="YOLO11s",
        device="cuda:0",
        raw_jpeg="",
        annotated_jpeg="",
        camera_stamp_s=3,
        camera_sequence=1,
        warehouse=None,
        position={"x": 1, "y": 2},
    )
    assert CaptureResult.model_validate(data).total == 1
    with pytest.raises(ValidationError):
        CaptureResult.model_validate({**data, "counts": {"person": 2}})
    data["detections"][0]["xyxy"] = [0, 0, 1500, 40]
    with pytest.raises(ValidationError):
        CaptureResult.model_validate(data)
