import pytest
from fastapi.testclient import TestClient

from roboinspect.api import create_app
from roboinspect.contracts import ConflictError, MappingAction, MissionPlan, MissionStatus
from roboinspect.operations import request_operation
from roboinspect.store import MissionStore


def enable(service):
    service.robot.state.update(
        mapping_controls=True, scenario="normal", mode="navigation", mapping_ready=False
    )


def test_mapping_and_mission_share_exclusive_robot(service):
    enable(service)
    operation, _ = request_operation(service, MappingAction.START, "start")
    with pytest.raises(ConflictError):
        service.create(MissionPlan(steps=[{"target": "A"}]), None)
    service.store.update_operation(operation.id, status=MissionStatus.SUCCEEDED, message="done")
    service.create(MissionPlan(steps=[{"target": "A"}]), None)
    with pytest.raises(ConflictError):
        request_operation(service, MappingAction.START, "another")


def test_duplicate_and_preemption_are_durable(service):
    enable(service)
    original, created = request_operation(service, MappingAction.START, "same")
    assert created
    assert request_operation(service, MappingAction.START, "same")[0].id == original.id
    assert len(service.store.operation_list()) == 1
    with pytest.raises(ConflictError):
        request_operation(service, MappingAction.RESET, "same")
    control, _ = request_operation(service, MappingAction.FINISH, "finish")
    assert service.store.operation(original.id).cancel_requested
    with pytest.raises(ConflictError):
        request_operation(service, MappingAction.RESET, "reset")
    # Progress updates cannot overwrite a concurrent cancellation request.
    service.store.update_operation(original.id, message="punkt 1")
    assert service.store.operation(original.id).cancel_requested
    reopened = MissionStore(str(service.store.engine.url))
    try:
        assert reopened.operation(control.id).kind == MappingAction.FINISH
        assert reopened.operation(original.id).events[-1].message == "punkt 1"
        reopened.interrupt_operations()
        assert all(r.status == MissionStatus.INTERRUPTED for r in reopened.operation_list())
    finally:
        reopened.close()


def test_save_requires_active_mapping_mode(service):
    enable(service)
    with pytest.raises(ConflictError):
        request_operation(service, MappingAction.SAVE, None)
    service.robot.state.update(mode="mapping", mapping_ready=True, ready=False)
    assert request_operation(service, MappingAction.SAVE, "save")[1]


def test_mapping_api_history_idempotency_and_internal_auth(service):
    enable(service)
    with TestClient(create_app(service), base_url="http://127.0.0.1:8765") as client:
        first = client.post("/api/mapping/start", json={}, headers={"Idempotency-Key": "one"})
        assert first.status_code == 202
        duplicate = client.post("/api/mapping/start", json={}, headers={"Idempotency-Key": "one"})
        assert duplicate.status_code == 200
        assert first.json()["id"] == duplicate.json()["id"]
        assert client.post("/api/goal", json={"goal": "A"}).status_code == 409
        assert client.get("/api/history").json()[0]["kind"] == "mapping"
        assert client.get("/api/status").json()["operation_busy"]
        assert (
            client.post(
                "/api/internal/runtime", json={"mode": "mapping", "transitioning": True}
            ).status_code
            == 403
        )
        assert client.post("/api/mapping/wrong", json={}).status_code == 422
        assert client.post("/api/mapping/reset", json={"arbitrary": True}).status_code == 422


def test_runner_failure_is_recorded_and_releases_robot(service, tmp_path):
    import threading
    from types import SimpleNamespace

    from roboinspect.mapping_runner import MappingRunner

    enable(service)
    record, _ = request_operation(service, MappingAction.START, "runner")

    def fail_switch(*args):
        raise RuntimeError("SLAM startup failed")

    manager = SimpleNamespace(
        root=tmp_path, log_dir=tmp_path, shutdown=threading.Event(), switch=fail_switch
    )
    runner = MappingRunner(manager, service.store)
    runner.tick()
    result = service.store.operation(record.id)
    assert result.status == MissionStatus.FAILED
    assert result.events[-1].message == "SLAM startup failed"
    assert not service.store.operation_busy()
    service.create(MissionPlan(steps=[{"target": "A"}]), None)


def test_runner_stops_survey_before_queued_reset(service, tmp_path):
    from types import SimpleNamespace

    from roboinspect.mapping_runner import MappingRunner

    enable(service)
    record, _ = request_operation(service, MappingAction.START, "survey")
    request_operation(service, MappingAction.RESET, "reset")
    stopped = []
    manager = SimpleNamespace(stop=lambda p: stopped.append(p))
    runner = MappingRunner(manager, service.store)
    runner.current = record
    runner.process = SimpleNamespace(poll=lambda: None)
    runner.log_path = tmp_path / "survey.log"
    runner.log_path.write_text("")
    runner.tick()
    assert len(stopped) == 1
    assert service.store.operation(record.id).status == MissionStatus.CANCELED
    remaining = service.store.operation_busy()
    assert len(remaining) == 1 and remaining[0].kind == MappingAction.RESET


def test_cancel_during_mode_transition_does_not_start_robot(service, tmp_path):
    import threading
    from types import SimpleNamespace

    from roboinspect.mapping_runner import MappingRunner

    enable(service)
    record, _ = request_operation(service, MappingAction.START, "early-cancel")
    manager = SimpleNamespace(
        root=tmp_path,
        log_dir=tmp_path,
        shutdown=threading.Event(),
        switch=lambda *_: service.store.cancel_operation(record.id),
    )
    runner = MappingRunner(manager, service.store)
    runner.tick()
    assert service.store.operation(record.id).status == MissionStatus.CANCELED
    assert runner.process is None
