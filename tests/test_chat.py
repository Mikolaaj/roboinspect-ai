import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from roboinspect.api import create_app
from roboinspect.chat import ChatService, ExperimentTracker, Interpretation
from roboinspect.contracts import ConflictError, MissionPlan


class Planner:
    model = "test-bielik"

    def __init__(self, action="navigate", targets=None):
        self.action, self.targets = action, targets if targets is not None else ["B", "BASE"]
        self.calls = 0

    def interpret(self, *args):
        self.calls += 1
        return Interpretation(action=self.action, targets=self.targets, message="Test"), {}


class Tracker:
    def log(self, *args):
        return "run-test"


def make(service, planner=None, tracker=None):
    return ChatService(service, planner or Planner(), tracker or Tracker())


def test_chat_deduplicates_and_dispatches_via_service(service):
    planner = Planner()
    chat = make(service, planner)
    record, created = chat.submit("Jedź do B i wróć", "request")
    assert created
    assert chat.submit(record["text"], "request")[0]["id"] == record["id"]
    with pytest.raises(ConflictError):
        chat.submit("Jedź do C", "request")
    with pytest.raises(ConflictError):
        chat.submit("Inna wiadomość", "other")
    chat.process(record)
    saved = chat.history()[0]
    assert saved["mission"]["steps"][0]["target"] == "B"
    assert saved["mission"]["steps"][1]["target"] == "BASE"
    assert saved["run_id"] == "run-test"
    assert planner.calls == 1
    assert not service.robot.calls  # Durable executor owns actual dispatch.
    service.tick()
    assert service.robot.calls == ["B"]


def test_invalid_target_and_schema_never_move(service):
    with pytest.raises(ValidationError):
        Interpretation(action="navigate", targets=["Z"], message="test")
    for action, targets in [("chat", ["A"]), ("navigate", [])]:
        with pytest.raises(ValidationError):
            Interpretation(action=action, targets=targets, message="test")

    class Broken(Planner):
        def interpret(self, *args):
            raise ValueError("invalid model output")

    chat = make(service, Broken())
    row, _ = chat.submit("Jedź do Z", "z")
    chat.process(row)
    assert chat.history()[0]["status"] == "error"
    assert service.store.active() is None


def test_mapping_and_busy_mission_block_chat_navigation(service):
    service.robot.state["ready"] = False
    chat = make(service)
    row, _ = chat.submit("Jedź do B", "b")
    chat.process(row)
    assert chat.history()[0]["status"] == "rejected"
    assert service.store.active() is None


def test_restart_does_not_replay_pending_turn(service):
    chat = make(service)
    chat.submit("Jedź do B", "b")
    restarted = make(service)
    restarted.start()
    restarted.close()
    assert restarted.history()[0]["status"] == "interrupted"
    assert service.store.active() is None
    assert not service.robot.calls


def test_tracking_failure_preserves_single_mission(service):
    class BrokenTracker:
        def log(self, *args):
            raise RuntimeError("disk")

    chat = make(service, tracker=BrokenTracker())
    row, _ = chat.submit("Jedź do B", "b")
    chat.process(row)
    assert chat.history()[0]["tracking_error"] == "RuntimeError"
    assert len(service.store.list()) == 1
    assert chat.submit("Jedź do B", "b")[1] is False


def test_chat_history_pagination_and_api(service):
    chat = make(service, Planner("chat", []))
    with TestClient(create_app(service, chat=chat), base_url="http://127.0.0.1:8765") as client:
        assert (
            client.post(
                "/api/chat", json={"text": " "}, headers={"Idempotency-Key": "a"}
            ).status_code
            == 422
        )
        assert client.post("/api/chat", json={"text": "Hej"}).status_code == 422
        assert (
            client.post(
                "/api/chat",
                json={"text": "Hej"},
                headers={"Idempotency-Key": "a", "Origin": "https://evil.test"},
            ).status_code
            == 403
        )
        first = client.post("/api/chat", json={"text": "Hej"}, headers={"Idempotency-Key": "a"})
        assert first.status_code == 202
        assert (
            client.post(
                "/api/chat", json={"text": "Hej"}, headers={"Idempotency-Key": "a"}
            ).status_code
            == 200
        )
        assert client.get("/api/chat").json()[0]["text"] == "Hej"
        assert client.get("/api/chat?before=1").json() == []


def test_cancel_does_not_cancel_newer_mission(service):
    class Slow(Planner):
        def interpret(self, *args):
            service.create(
                MissionPlan(steps=[{"target": "A"}]),
                "new",
            )
            return Interpretation(action="cancel", targets=[], message="test"), {}

    chat = make(service, Slow())
    row, _ = chat.submit("Anuluj", "cancel")
    chat.process(row)
    assert service.store.active().status == "queued"
    assert "Brak aktywnej" in chat.history()[0]["reply"]


def test_real_mlflow_local_tracking(tmp_path):
    tracker = ExperimentTracker(f"sqlite:///{tmp_path / 'tracking.db'}")
    record = {"id": "test", "text": "Cześć", "reply": "Cześć", "status": "answered"}
    run = tracker.log(
        record,
        Interpretation(action="chat", targets=[], message="Cześć"),
        {"latency_seconds": 0.1, "schema_valid": 1},
        "test-model",
    )
    from mlflow.tracking import MlflowClient

    saved = MlflowClient(tracking_uri=tracker.uri).get_run(run)
    assert saved.data.metrics["schema_valid"] == 1
    assert saved.data.params["model"] == "test-model"


def test_stop_during_inference_cannot_dispatch(service):
    class StopBeforeReturn(Planner):
        def interpret(self, *args):
            chat.stopping.set()
            return super().interpret(*args)

    chat = make(service, StopBeforeReturn())
    row, _ = chat.submit("Jedź do B", "stop")
    chat.process(row)
    assert not service.store.list()
    assert chat.history()[0]["status"] == "error"


def test_persisted_chat_exposes_actual_mission_result(service):
    chat = make(service)
    row, _ = chat.submit("Jedź do B i wróć", "test")
    chat.process(row)
    for _ in range(2):
        service.tick()
        service.robot.finish()
    service.tick()
    reopened = make(service)
    record = reopened.history()[0]
    assert record["text"] == "Jedź do B i wróć"
    assert record["mission"]["status"] == "succeeded"
    assert record["mission"]["message"] == "Wszystkie kroki misji wykonane"


def test_valid_json_with_invented_target_is_rejected():
    from roboinspect.chat import guard_targets

    guessed = Interpretation(action="navigate", targets=["P1"], message="Jadę")
    assert guard_targets("Jedź tam", guessed).action == "clarify"
    assert guard_targets("Jedź do sektora Z", guessed).targets == []
    assert guard_targets("Nie jedź do P1", guessed).action == "clarify"
    allowed = Interpretation(action="navigate", targets=["B", "BASE"], message="Plan")
    assert guard_targets("Jedź do B i wróć do bazy", allowed) == allowed
    partial = Interpretation(action="navigate", targets=["A"], message="Plan")
    assert guard_targets("Jedź do A oraz sektora Z", partial).action == "clarify"


def test_restart_links_committed_mission_without_dispatching_it_again(service):
    chat = make(service)
    row, _ = chat.submit("Jedź do A", "a")
    original, _ = service.create(MissionPlan(steps=[{"target": "A"}]), "chat:" + row["id"])
    restarted = make(service)
    restarted.start()
    restarted.close()
    saved = restarted.history()[0]
    assert saved["status"] == "interrupted"
    assert saved["mission_id"] == original.id
    assert len(service.store.list()) == 1
    assert not service.robot.calls


def test_cancellation_is_not_counted_as_new_mission_in_mlflow(service):
    class Capture(Tracker):
        def log(self, record, parsed, metrics, model):
            self.metrics = metrics
            return super().log(record, parsed, metrics, model)

    service.create(MissionPlan(steps=[{"target": "A"}]), "original")
    tracker = Capture()
    chat = make(service, Planner("cancel", []), tracker)
    row, _ = chat.submit("Anuluj", "cancel")
    chat.process(row)
    assert tracker.metrics["mission_accepted"] == 0
    assert len(service.store.list()) == 1


def test_old_conversation_is_not_reintroduced_as_command_context(service):
    class Inspect(Planner):
        def interpret(self, text, state):
            self.received = (text, state)
            return Interpretation(action="status", targets=[], message="Sprawdzam"), {}

    chat = make(service, Planner("chat", []))
    old, _ = chat.submit("Wcześniejsza rozmowa", "old")
    chat.process(old)
    planner = Inspect()
    chat.planner = planner
    current, _ = chat.submit("Gdzie jesteś?", "current")
    chat.process(current)
    assert planner.received[0] == "Gdzie jesteś?"
    assert set(planner.received[1]) == {"ready", "busy", "state", "map_position", "goal"}
    assert len(chat.history()) == 2
    assert service.store.active() is None


def test_new_conversation_archives_without_losing_history(service):
    chat = make(service, Planner("chat", []))
    row, _ = chat.submit("Stara rozmowa testowa", "old")
    chat.process(row)
    marker = chat.new_conversation("new-session")
    assert chat.history() == []
    assert chat.history(include_archived=True)[0]["text"] == "Stara rozmowa testowa"
    fresh, _ = chat.submit("Moje nowe pytanie", "fresh")
    chat.process(fresh)
    assert chat.new_conversation("new-session") == marker
    assert len(chat.history()) == 1
    reopened = make(service)
    assert reopened.history()[0]["text"] == "Moje nowe pytanie"
    assert len(reopened.history(include_archived=True)) == 2


def test_new_conversation_waits_for_pending_answer(service):
    chat = make(service)
    chat.submit("Jedź do A", "pending")
    with pytest.raises(ConflictError):
        chat.new_conversation("new")
    assert len(chat.history()) == 1


def test_instructional_question_cannot_trigger_navigation():
    from roboinspect.chat import guard_targets

    guess = Interpretation(action="navigate", targets=["B"], message="Jadę")
    assert guard_targets("Jak wysłać robota do sektora B?", guess).action == "clarify"
