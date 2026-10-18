import pytest
from pydantic import ValidationError

from roboinspect.contracts import ConflictError, MissionPlan, MissionStatus
from roboinspect.missions import MissionService
from roboinspect.store import MissionStore


def plan(*targets):
    return MissionPlan(steps=[{"target": t} for t in targets])


@pytest.mark.parametrize(
    "data",
    [
        {"steps": []},
        {"steps": [{"target": "D"}]},
        {"steps": [{"target": "A", "x": 2}]},
        {"steps": [{"target": "A", "action": "shell"}]},
        {"steps": [{"target": "A", "timeout_seconds": "20"}]},
        {"steps": [{"target": "A"}] * 21},
    ],
)
def test_reject_invalid_plan(data):
    with pytest.raises(ValidationError):
        MissionPlan.model_validate(data)


def test_sequence_waits_for_stopped_result(service):
    record, _ = service.create(plan("A", "BASE"), "sequence")
    service.tick()
    assert service.robot.calls == ["A"]
    service.robot.state["state"] = "succeeded"
    service.tick()
    assert service.robot.calls == ["A"]
    service.robot.finish()
    service.tick()
    assert service.robot.calls == ["A", "BASE"]
    service.robot.finish()
    service.tick()
    assert service.store.get(record.id).status == MissionStatus.SUCCEEDED
    assert all(s.status == "succeeded" for s in service.store.get(record.id).steps)


def test_idempotency_and_active_conflict(service):
    record, created = service.create(plan("A"), "same")
    assert created
    assert service.create(plan("A"), "same") == (record, False)
    with pytest.raises(ConflictError):
        service.create(plan("B"), "same")
    with pytest.raises(ConflictError):
        service.create(plan("B"), None)


@pytest.mark.parametrize("started", [False, True])
def test_cancel_skips_remaining_steps(service, started):
    record, _ = service.create(plan("A", "B", "BASE"), None)
    if started:
        service.tick()
    service.cancel()
    service.tick()
    result = service.store.get(record.id)
    assert result.status == MissionStatus.CANCELED
    assert service.robot.calls == (["A"] if started else [])
    assert result.steps[-1].status == "skipped"


def test_failed_step_does_not_dispatch_next(service):
    record, _ = service.create(plan("A", "B"), None)
    service.tick()
    service.robot.finish("failed")
    service.tick()
    assert service.store.get(record.id).status == MissionStatus.FAILED
    assert service.robot.calls == ["A"]


def test_stale_execution_result_is_not_success(service):
    record, _ = service.create(plan("A", "B"), None)
    service.tick()
    service.robot.finish()
    service.robot.state["execution_id"] = "another-goal"
    service.tick()
    assert service.store.get(record.id).status == MissionStatus.UNCERTAIN
    assert service.robot.calls == ["A"]


def test_timeout_cancels_and_fails(service):
    record, _ = service.create(plan("A", "B"), None)
    service.tick()
    service.step_started -= 301
    service.tick()
    service.tick()
    assert service.store.get(record.id).status == MissionStatus.FAILED
    assert service.robot.calls == ["A"]


def test_offline_never_reports_success(service):
    record, _ = service.create(plan("A"), None)
    service.tick()
    service.robot.state["ready"] = False
    service.tick()
    assert service.store.get(record.id).status == MissionStatus.UNCERTAIN
    service.robot.state["ready"] = True


def test_restart_recovers_without_replay(tmp_path):
    from conftest import FakeRobot

    url = f"sqlite:///{tmp_path / 'history.db'}"
    store = MissionStore(url)
    record, _ = store.create(plan("A", "BASE"), "normal", "restart")
    store.close()
    store = MissionStore(url)
    robot = FakeRobot()
    service = MissionService(store, robot, "normal", tmp_path / "owner")
    try:
        service.tick()
        assert store.get(record.id).status == MissionStatus.UNCERTAIN
        service.tick()
        assert store.get(record.id).status == MissionStatus.INTERRUPTED
        assert robot.calls == []
        assert robot.recoveries == 1
        assert len(store.history(record.id)) >= 3
    finally:
        service.close()
        store.close()


def test_second_owner_rejected(service, tmp_path):
    with pytest.raises(RuntimeError, match="właścicielem"):
        MissionService(service.store, service.robot, "normal", tmp_path / "owner.lock")


def test_database_rejects_second_active_owner(service):
    service.create(plan("A"), None)
    another = MissionStore(str(service.store.engine.url))
    try:
        with pytest.raises(ConflictError):
            another.create(plan("B"), "normal", None)
    finally:
        another.close()


def test_unconfirmed_send_is_never_retried(service):
    record, _ = service.create(plan("A", "B"), None)
    original = service.robot.start

    def sent_but_reply_lost(target, execution_id):
        original(target, execution_id)
        raise TimeoutError("response lost after sending")

    service.robot.start = sent_but_reply_lost
    service.tick()
    assert service.store.get(record.id).status == MissionStatus.UNCERTAIN
    service.tick()
    service.tick()
    assert service.store.get(record.id).status == MissionStatus.INTERRUPTED
    assert service.robot.calls == ["A"]


def test_finished_history_survives_database_reopen(service):
    record, _ = service.create(plan("A"), "persisted")
    service.tick()
    service.robot.finish()
    service.tick()
    reopened = MissionStore(str(service.store.engine.url))
    try:
        assert reopened.get(record.id).status == MissionStatus.SUCCEEDED
        assert reopened.by_key("persisted").id == record.id
        assert reopened.history(record.id)[-1].status == MissionStatus.SUCCEEDED
    finally:
        reopened.close()
