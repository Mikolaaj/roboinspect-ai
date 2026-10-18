"""One durable mission owner; never replay an ambiguous movement after restart."""

import fcntl
import logging
import threading
import time
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .contracts import ACTIVE, ConflictError, MissionPlan, MissionRecord, MissionStatus
from .store import MissionStore

logger = logging.getLogger(__name__)


class Robot(Protocol):
    def snapshot(self) -> dict: ...
    def start(self, target: str, execution_id: str) -> None: ...
    def cancel(self) -> None: ...
    def recover(self) -> None: ...


def stationary(state: dict) -> bool:
    velocity = state.get("velocity", {})
    return abs(velocity.get("linear", 1)) < 0.02 and abs(velocity.get("angular", 1)) < 0.02


class MissionService:
    def __init__(
        self,
        store: MissionStore,
        robot: Robot,
        scenario: str,
        owner_file: Path,
        clock=time.monotonic,
    ):
        owner_file.parent.mkdir(parents=True, exist_ok=True)
        self.owner = owner_file.open("a")
        try:
            fcntl.flock(self.owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.owner.close()
            raise RuntimeError("Inny wykonawca jest już właścicielem robota") from exc
        self.store, self.robot, self.scenario = store, robot, scenario
        self.clock = clock
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.step_started = None
        self.recovery_sent = None
        self.failure_after_cancel = False
        self.healthy = True
        previous = store.active()
        if previous:
            self._uncertain(previous, "Restart wykonawcy: trwa sprawdzanie zatrzymania robota")

    def start_worker(self):
        self.thread = threading.Thread(target=self._loop, name="mission-executor", daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.stop_event.wait(0.15):
            try:
                self.tick()
                self.healthy = True
            except Exception:
                self.healthy = False
                logger.exception("Mission executor tick failed")
                self.stop_event.wait(1)

    def create(self, plan: MissionPlan, key: str | None) -> tuple[MissionRecord, bool]:
        with self.lock:
            if key and self.store.by_key(key):
                return self.store.create(plan, self.scenario, key)
            state = self.robot.snapshot()
            if (
                not self.healthy
                or not state.get("ready")
                or state.get("busy")
                or state.get("remote_active")
                or self.store.active()
            ):
                raise ConflictError("Robot nie jest gotowy lub ma aktywną misję")
            return self.store.create(plan, self.scenario, key)

    def cancel(self, mission_id: str | None = None) -> MissionRecord | None:
        with self.lock:
            record = self.store.get(mission_id) if mission_id else self.store.active()
            if record is None or record.status not in ACTIVE:
                return record
            if record.status == MissionStatus.UNCERTAIN:
                return record
            if record.status != MissionStatus.CANCELING:
                record.status = MissionStatus.CANCELING
                record.message = "Anulowanie misji; pozostałe kroki nie zostaną wykonane"
                self.store.save(record)
            try:
                self.robot.cancel()
            except Exception:
                self._uncertain(
                    record, "Utrata kontaktu podczas anulowania; sprawdzanie zatrzymania"
                )
            return record

    def _finish(self, record, status, message):
        record.status, record.message = status, message
        for step in record.steps:
            if step.status == "pending":
                step.status = "skipped"
            elif step.status == "running":
                step.status = "canceled" if status == MissionStatus.CANCELED else "failed"
        self.store.save(record)
        self.step_started = None
        self.failure_after_cancel = False

    def _uncertain(self, record, message):
        record.status, record.message = MissionStatus.UNCERTAIN, message
        self.store.save(record)
        self.recovery_sent = None

    def _recover(self, record, state):
        if (
            self.recovery_sent is None
            or self.clock() - self.recovery_sent > 3
            and state.get("recovery_state") != "pending"
        ):
            try:
                self.robot.recover()
                self.recovery_sent = self.clock()
                return
            except Exception:
                return
        if (
            state.get("recovery_state") == "succeeded"
            and state.get("ready")
            and not state.get("busy")
            and not state.get("remote_active")
            and stationary(state)
        ):
            self._finish(
                record,
                MissionStatus.INTERRUPTED,
                "Misja przerwana; zatrzymanie potwierdzone, kroki nie zostały ponowione",
            )

    def tick(self):
        with self.lock:
            record = self.store.active()
            if record is None:
                return
            try:
                state = self.robot.snapshot()
            except Exception:
                if record.status != MissionStatus.UNCERTAIN:
                    self._uncertain(record, "Brak stanu robota; wynik ruchu jest niepewny")
                return
            if record.status == MissionStatus.UNCERTAIN:
                self._recover(record, state)
                return
            if not state.get("ready"):
                self._uncertain(record, "Utrata gotowości robota; misja nie jest uznana za udaną")
                return
            if record.status == MissionStatus.CANCELING:
                if not state.get("busy") and not state.get("remote_active") and stationary(state):
                    self._finish(
                        record,
                        MissionStatus.FAILED
                        if self.failure_after_cancel
                        else MissionStatus.CANCELED,
                        "Przekroczono limit czasu kroku"
                        if self.failure_after_cancel
                        else "Misja anulowana; robot zatrzymany",
                    )
                return
            if record.current_step is not None:
                step = record.steps[record.current_step]
                if step.status == "running":
                    if state.get("execution_id") != step.execution_id:
                        self._uncertain(
                            record, "Niezgodny identyfikator wykonania; sprawdzanie zatrzymania"
                        )
                        return
                    if (
                        self.step_started is not None
                        and self.clock() - self.step_started > step.timeout_seconds
                    ):
                        self.failure_after_cancel = True
                        self.cancel(record.id)
                        return
                    if state.get("state") in ["failed", "canceled"]:
                        step.status = state["state"]
                        self._finish(
                            record,
                            MissionStatus.FAILED,
                            "Krok nie został wykonany; pozostałe kroki pominięto",
                        )
                        return
                    if (
                        state.get("state") != "succeeded"
                        or state.get("busy")
                        or not stationary(state)
                    ):
                        return
                    step.status = "succeeded"
                    record.message = f"Zakończono krok {record.current_step + 1}: {step.target}"
                    self.store.save(record)
            pending = next(
                (i for i, step in enumerate(record.steps) if step.status == "pending"), None
            )
            if pending is None:
                self._finish(record, MissionStatus.SUCCEEDED, "Wszystkie kroki misji wykonane")
                return
            if state.get("busy") or state.get("remote_active"):
                self._uncertain(record, "Robot wykonuje nieoczekiwane zadanie")
                return
            step = record.steps[pending]
            step.execution_id, step.status = str(uuid4()), "running"
            record.current_step, record.status = pending, MissionStatus.RUNNING
            record.message = f"Krok {pending + 1}/{len(record.steps)}: jazda do {step.target}"
            self.store.save(record)  # Commit intent before any physical side effect.
            self.step_started = self.clock()
            try:
                self.robot.start(step.target.value, step.execution_id)
            except Exception:
                self._uncertain(record, "Niepotwierdzone wysłanie celu; ruch nie będzie ponawiany")

    def summary(self):
        with self.lock:
            records = self.store.list(limit=1)
            active = self.store.active()
            return active or (records[0] if records else None)

    def close(self):
        if self.owner.closed:
            return
        try:
            self.cancel()
            deadline = time.monotonic() + 4
            while self.store.active() and time.monotonic() < deadline:
                self.tick()
                time.sleep(0.1)
            with self.lock:
                record = self.store.active()
                if record and record.status != MissionStatus.UNCERTAIN:
                    self._uncertain(
                        record, "Zamknięcie przed potwierdzeniem wyniku; weryfikacja po restarcie"
                    )
        finally:
            self.stop_event.set()
            if self.thread:
                self.thread.join(timeout=3)
            fcntl.flock(self.owner, fcntl.LOCK_UN)
            self.owner.close()
