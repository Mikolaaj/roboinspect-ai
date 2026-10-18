"""Transactional durable history; SQLite locally, PostgreSQL through DATABASE_URL."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import RLock

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    select,
)
from sqlalchemy.exc import IntegrityError

from .contracts import (
    ACTIVE,
    ConflictError,
    MappingOperation,
    MissionEvent,
    MissionPlan,
    MissionRecord,
    MissionStatus,
    OperationLog,
    now,
)

metadata = MetaData()
missions = Table(
    "missions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("request_key", String(128), unique=True),
    Column("digest", String(64), nullable=False),
    Column("active_slot", Integer, unique=True),
    Column("created_at", String(40), nullable=False),
    Column("record", JSON, nullable=False),
)
events = Table(
    "mission_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("mission_id", String(36), nullable=False, index=True),
    Column("time", String(40), nullable=False),
    Column("message", String(1000), nullable=False),
    Column("status", String(20), nullable=False),
)

operations = Table(
    "mapping_operations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("request_key", String(128), unique=True),
    Column("kind", String(20), nullable=False),
    Column("status", String(20), nullable=False),
    Column("cancel_requested", Boolean, nullable=False, default=False),
    Column("created_at", String(40), nullable=False),
    Column("record", JSON, nullable=False),
)


class MissionStore:
    def __init__(self, url: str):
        if url.startswith("sqlite:///") and ":memory:" not in url:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        options = {"check_same_thread": False, "timeout": 10} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=options)
        if url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def sqlite_settings(connection, _):
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA busy_timeout=10000")

        metadata.create_all(self.engine)
        self.lock = RLock()

    def get(self, mission_id: str) -> MissionRecord | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(missions.c.record).where(missions.c.id == mission_id)
            ).first()
            return MissionRecord.model_validate(row[0]) if row else None

    def list(self, limit: int = 50) -> list[MissionRecord]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(missions.c.record)
                .order_by(missions.c.created_at.desc(), missions.c.id.desc())
                .limit(limit)
            )
            return [MissionRecord.model_validate(row[0]) for row in rows]

    def active(self) -> MissionRecord | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(missions.c.record).where(missions.c.active_slot == 1)
            ).first()
            return MissionRecord.model_validate(row[0]) if row else None

    def create(
        self, plan: MissionPlan, scenario: str, key: str | None
    ) -> tuple[MissionRecord, bool]:
        digest = hashlib.sha256(
            json.dumps(
                {"scenario": scenario, "plan": plan.model_dump(mode="json")}, sort_keys=True
            ).encode()
        ).hexdigest()
        with self.lock, self.engine.begin() as connection:
            if key is not None:
                row = (
                    connection.execute(select(missions).where(missions.c.request_key == key))
                    .mappings()
                    .first()
                )
                if row:
                    if row["digest"] != digest:
                        raise ConflictError("Ten klucz był już użyty do innego polecenia")
                    return MissionRecord.model_validate(row["record"]), False
            record = MissionRecord(
                name=plan.name, scenario=scenario, steps=[step.model_dump() for step in plan.steps]
            )
            try:
                connection.execute(
                    missions.insert().values(
                        id=record.id,
                        request_key=key,
                        digest=digest,
                        active_slot=1,
                        created_at=record.created_at.isoformat(),
                        record=record.model_dump(mode="json"),
                    )
                )
            except IntegrityError as exc:
                raise ConflictError("Robot ma już aktywną misję") from exc
            self._event(connection, record)
            return record, True

    def save(self, record: MissionRecord) -> None:
        record.updated_at = now()
        with self.lock, self.engine.begin() as connection:
            connection.execute(
                missions.update()
                .where(missions.c.id == record.id)
                .values(
                    active_slot=1 if record.status in ACTIVE else None,
                    record=record.model_dump(mode="json"),
                )
            )
            self._event(connection, record)

    @staticmethod
    def _event(connection, record):
        connection.execute(
            events.insert().values(
                mission_id=record.id,
                time=record.updated_at.isoformat(),
                message=record.message,
                status=record.status.value,
            )
        )

    def history(self, mission_id: str) -> list[MissionEvent]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(events).where(events.c.mission_id == mission_id).order_by(events.c.id)
            ).mappings()
            return [MissionEvent.model_validate(dict(row)) for row in rows]

    def close(self):
        self.engine.dispose()

    def by_key(self, key: str) -> MissionRecord | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(missions.c.record).where(missions.c.request_key == key)
            ).first()
            return MissionRecord.model_validate(row[0]) if row else None

    def operation(self, operation_id):
        with self.engine.connect() as connection:
            row = (
                connection.execute(select(operations).where(operations.c.id == operation_id))
                .mappings()
                .first()
            )
            return self._operation_row(row) if row else None

    @staticmethod
    def _operation_row(row):
        record = MappingOperation.model_validate(row["record"])
        record.cancel_requested = row["cancel_requested"]
        return record

    def operation_list(self, limit=50):
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(operations).order_by(operations.c.created_at.desc()).limit(limit)
            ).mappings()
            return [self._operation_row(row) for row in rows]

    def operation_busy(self):
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(operations)
                .where(operations.c.status.in_([s.value for s in ACTIVE]))
                .order_by(operations.c.created_at)
            ).mappings()
            return [self._operation_row(row) for row in rows]

    def operation_key(self, key):
        with self.engine.connect() as connection:
            row = (
                connection.execute(select(operations).where(operations.c.request_key == key))
                .mappings()
                .first()
            )
            return self._operation_row(row) if row else None

    def create_operation(self, record, key, cancel_id=None):
        record.events.append(OperationLog(message=record.message))
        with self.engine.begin() as connection:
            connection.execute(
                operations.insert().values(
                    id=record.id,
                    kind=record.kind.value,
                    request_key=key,
                    status=record.status.value,
                    cancel_requested=False,
                    created_at=record.created_at.isoformat(),
                    record=record.model_dump(mode="json"),
                )
            )
            if cancel_id is not None:
                connection.execute(
                    operations.update()
                    .where(operations.c.id == cancel_id)
                    .values(cancel_requested=True)
                )
        return record

    def update_operation(self, operation_id, *, status=None, message=None, saved_map=None):
        # Only the single cockpit supervisor writes execution progress.
        record = self.operation(operation_id)
        if status is not None:
            record.status = status
        if message is not None:
            record.message = message
            record.events.append(OperationLog(message=message))
        if saved_map is not None:
            record.saved_map = saved_map
        record.updated_at = now()
        with self.engine.begin() as connection:
            connection.execute(
                operations.update()
                .where(operations.c.id == operation_id)
                .values(status=record.status.value, record=record.model_dump(mode="json"))
            )
        return record

    def cancel_operation(self, operation_id):
        with self.engine.begin() as connection:
            connection.execute(
                operations.update()
                .where(operations.c.id == operation_id)
                .values(cancel_requested=True)
            )

    def interrupt_operations(self):
        for record in self.operation_busy():
            self.update_operation(
                record.id,
                status=MissionStatus.INTERRUPTED,
                message="Restart lub zamknięcie kokpitu; operacja nie będzie ponawiana",
            )
