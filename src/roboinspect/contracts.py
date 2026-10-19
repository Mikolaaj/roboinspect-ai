"""Validated commands and durable mission records. No arbitrary robot coordinates."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def now() -> datetime:
    return datetime.now(UTC)


class GoalName(StrEnum):
    BASE = "BASE"
    A = "A"
    B = "B"
    C = "C"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class NavigationStep(StrictModel):
    action: Literal["navigate", "inspect"] = "navigate"
    target: GoalName
    timeout_seconds: int = Field(default=300, ge=10, le=900, strict=True)


class MissionPlan(StrictModel):
    name: str = Field(default="Przejazd robota", min_length=1, max_length=120)
    steps: list[NavigationStep] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def inspection_follows_navigation(self):
        for i, step in enumerate(self.steps):
            if step.action == "inspect" and (
                not str(step.target).startswith("P")
                or i == 0
                or self.steps[i - 1].action != "navigate"
                or self.steps[i - 1].target != step.target
            ):
                raise ValueError("Inspekcja wymaga wcześniejszego przejazdu do tej samej tablicy P")
        return self


class MissionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELING = "canceling"
    UNCERTAIN = "uncertain"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    INTERRUPTED = "interrupted"


ACTIVE = frozenset(
    {MissionStatus.QUEUED, MissionStatus.RUNNING, MissionStatus.CANCELING, MissionStatus.UNCERTAIN}
)


class StepRecord(NavigationStep):
    status: Literal["pending", "running", "succeeded", "failed", "canceled", "skipped"] = "pending"
    execution_id: str | None = None


class MissionRecord(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    scenario: str
    status: MissionStatus = MissionStatus.QUEUED
    steps: list[StepRecord]
    current_step: int | None = None
    message: str = "Misja przyjęta"
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class MissionEvent(StrictModel):
    id: int
    mission_id: str
    time: datetime
    message: str
    status: MissionStatus


class GoalRequest(StrictModel):
    goal: GoalName


class RobotState(BaseModel):
    """Typed navigation fields, with additional sensor telemetry preserved."""

    model_config = ConfigDict(extra="allow")
    ready: bool
    busy: bool
    state: str
    execution_id: str | None = None
    goal: GoalName | None = None


class ConflictError(Exception):
    pass


class Sector(StrictModel):
    label: str
    bounds: tuple[float, float, float, float]
    color: tuple[float, float, float, float]


class MappingAction(StrEnum):
    START = "start"
    SAVE = "save"
    RESET = "reset"
    FINISH = "finish"
    WAREHOUSE_STANDARD = "warehouse_standard"
    WAREHOUSE_CLEAR = "warehouse_clear"
    WAREHOUSE_RANDOM = "warehouse_random"
    WAREHOUSE_PICTURES = "warehouse_pictures"


class OperationLog(StrictModel):
    time: datetime = Field(default_factory=now)
    message: str


class MappingOperation(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: MappingAction
    name: str
    status: MissionStatus = MissionStatus.QUEUED
    message: str = "Operacja przyjęta"
    cancel_requested: bool = False
    saved_map: str | None = None
    layout_seed: int | None = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    events: list[OperationLog] = Field(default_factory=list)


class MappingRequest(StrictModel):
    pass


class WarehouseAction(StrEnum):
    STANDARD = "standard"
    CLEAR = "clear"
    RANDOM = "random"
    PICTURES = "pictures"


class WarehouseView(StrictModel):
    mode: Literal["standard", "clear", "random"] = "standard"
    layout_id: str = "standard"
    seed: int | None = None
    movable_count: int = 8


class RuntimeUpdate(StrictModel):
    mode: Literal["navigation", "mapping"]
    transitioning: bool
    map_file: str | None = None
    world_file: str | None = None
    warehouse: WarehouseView | None = None
