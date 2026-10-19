"""Camera inspection plans, durable evidence and grounded operator answers."""

import base64
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import Field, model_validator
from sqlalchemy import JSON, Column, String, Table, select

from .banners import PANELS
from .contracts import ConflictError, MissionPlan, StrictModel, now
from .operator_policy import normalized
from .store import metadata

ROOT = Path(__file__).resolve().parents[2]
reports = Table(
    "inspection_reports",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("execution_id", String(36), unique=True, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("record", JSON, nullable=False),
)


def inspection_plan(sector):
    if sector not in PANELS:
        raise ConflictError("Wybierz sektor A, B lub C")
    steps = [{"target": sector}]
    for panel in PANELS[sector]:
        steps += [{"target": panel}, {"action": "inspect", "target": panel}]
    steps += [{"target": sector}]
    return MissionPlan(name=f"Inspekcja obrazów sektora {sector}", steps=steps)


def list_reports(store, limit=50):
    with store.engine.connect() as connection:
        return list(
            connection.execute(
                select(reports.c.record).order_by(reports.c.created_at.desc()).limit(limit)
            ).scalars()
        )


class Detection(StrictModel):
    label: str = Field(pattern=r"^[a-z ]{1,40}$")
    instance: int = Field(ge=1, le=50)
    confidence: float = Field(ge=0, le=1)
    xyxy: tuple[float, float, float, float]


class CaptureResult(StrictModel):
    detections: list[Detection] = Field(max_length=50)
    counts: dict[str, int]
    total: int = Field(ge=0, le=50)
    width: int = Field(ge=1, le=4096)
    height: int = Field(ge=1, le=4096)
    inference_seconds: float = Field(ge=0, le=40)
    model: str
    device: str
    raw_jpeg: str = Field(max_length=6000000)
    annotated_jpeg: str = Field(max_length=6000000)
    camera_stamp_s: float
    camera_sequence: int = Field(ge=1)
    warehouse: dict | None
    position: dict

    @model_validator(mode="after")
    def consistent_counts(self):
        observed = {}
        for d in self.detections:
            observed[d.label] = observed.get(d.label, 0) + 1
            if d.instance != observed[d.label]:
                raise ValueError("Niezgodne numery wykryć")
            x1, y1, x2, y2 = d.xyxy
            if not (0 <= x1 < x2 <= self.width and 0 <= y1 < y2 <= self.height):
                raise ValueError("Ramka poza obrazem")
        if self.total != len(self.detections) or self.counts != observed:
            raise ValueError("Niezgodna liczba wykryć")
        return self


class InspectionService:
    def __init__(self, store):
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="camera-inspection")
        self.cancel = threading.Event()
        self.future = None
        self.execution_id = None
        self.url = os.environ.get("ROBOINSPECT_VISION_URL", "http://127.0.0.1:8766")
        self.headers = {"X-Runtime-Token": os.environ.get("ROBOINSPECT_RUNTIME_TOKEN", "")}
        reports.create(store.engine, checkfirst=True)

    def available(self):
        try:
            with httpx.Client(timeout=1, trust_env=False) as client:
                r = client.get(self.url + "/latest", headers=self.headers)
                return r.status_code == 200 and r.json().get("ready", False)
        except (httpx.HTTPError, ValueError):
            return False

    def start(self, step, mission):
        if self.future and not self.future.done():
            raise RuntimeError("Poprzednia analiza jeszcze się kończy")
        self.cancel = threading.Event()
        self.execution_id = step.execution_id
        self.future = self.pool.submit(
            self.capture, step.target.value, mission.id, step.execution_id, self.cancel
        )

    def capture(self, panel, mission_id, execution_id, cancel):
        # Deliberate dwell, independent from the navigation server's settling time.
        if cancel.wait(2):
            raise RuntimeError("Inspekcja anulowana")
        with httpx.Client(timeout=35, trust_env=False) as client:
            response = client.post(
                self.url + "/capture", json={"panel": panel}, headers=self.headers
            )
            response.raise_for_status()
            result = CaptureResult.model_validate(response.json()).model_dump()
        if cancel.is_set():
            raise RuntimeError("Inspekcja anulowana")
        result.update(
            id=str(uuid4()),
            mission_id=mission_id,
            execution_id=execution_id,
            panel=panel,
            sector=next(s for s, ps in PANELS.items() if panel in ps),
            created_at=now().isoformat(),
        )
        directory = ROOT / "data/inspections" / result["id"]
        directory.mkdir(parents=True)
        for field, name in [("raw_jpeg", "raw.jpg"), ("annotated_jpeg", "annotated.jpg")]:
            (directory / name).write_bytes(base64.b64decode(result.pop(field), validate=True))
        result["image_url"] = f"/api/inspections/{result['id']}/annotated.jpg"
        result["raw_url"] = f"/api/inspections/{result['id']}/raw.jpg"
        return result

    def poll(self):
        if self.future is None or not self.future.done():
            return None
        result = self.future.result()
        if self.cancel.is_set():
            raise RuntimeError("Inspekcja anulowana")
        with self.store.engine.begin() as connection:
            connection.execute(
                reports.insert().values(
                    id=result["id"],
                    execution_id=result["execution_id"],
                    created_at=result["created_at"],
                    record=result,
                )
            )
        self.future = None
        threading.Thread(target=self.log_metrics, args=(result,), daemon=True).start()
        return result

    def log_metrics(self, result):
        try:
            from mlflow import MlflowClient

            client = MlflowClient(tracking_uri=f"sqlite:///{ROOT / 'data/mlflow.db'}")
            experiment = client.get_experiment_by_name("roboinspect-yolo")
            eid = (
                experiment.experiment_id
                if experiment
                else client.create_experiment(
                    "roboinspect-yolo", artifact_location=str(ROOT / "data/mlflow-artifacts/vision")
                )
            )
            run = client.create_run(
                eid,
                tags={
                    "panel": result["panel"],
                    "sector": result["sector"],
                    "mission_id": result["mission_id"],
                    "report_id": result["id"],
                },
            )
            client.log_param(run.info.run_id, "model", result["model"])
            client.log_param(run.info.run_id, "device", result["device"])
            client.log_param(run.info.run_id, "confidence_threshold", 0.30)
            client.log_metric(run.info.run_id, "detections", result["total"])
            client.log_metric(run.info.run_id, "inference_seconds", result["inference_seconds"])
            client.log_artifact(
                run.info.run_id, str(ROOT / "data/inspections" / result["id"] / "annotated.jpg")
            )
            client.set_terminated(run.info.run_id)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Nie zapisano pomiaru YOLO w MLflow; raport kamery jest zachowany"
            )

    def abort(self):
        self.cancel.set()

    def close(self):
        self.abort()
        self.pool.shutdown(wait=False, cancel_futures=True)


def inspection_question(text):
    value = normalized(text)
    return bool(
        re.search(
            r"widzial|wykryl|wykryto|rozpoznal|ile.*(?:osob|ludzi|zwierz)|wynik.*inspek|jakie.*zdjec|co.*(?:zdjec|baner|tablic)",
            value,
        )
        or ("detekcj" in value and re.search(r"sektor|stref|ile|ostatni", value))
    )


def evidence_answer(store, text):
    value = normalized(text)
    sector = re.search(r"\b(?:sektor\w*|stref\w*)\s+([a-z0-9]+)\b", value)
    if sector and sector[1].upper() not in PANELS:
        return "Nie znam takiego sektora. Wybierz A, B lub C. Nie wysłano polecenia ruchu."
    panel = re.search(r"\b(p[0-9]+)\b", value)
    if panel and panel[1].upper() not in [p for ps in PANELS.values() for p in ps]:
        return "Nie znam tej tablicy. Dostępne są P1 do P5."
    rows = list_reports(store, 100)
    if panel:
        rows = [r for r in rows if r["panel"] == panel[1].upper()]
    if sector:
        rows = [r for r in rows if r["sector"] == sector[1].upper()]
    if not rows:
        return (
            "Nie mam zapisanej inspekcji"
            + (f" sektora {sector[1].upper()}" if sector else "")
            + ". Wybierz Inspekcja sektora A, B lub C. Sam przejazd nie tworzy raportu."
        )
    # Latest mission only: do not add counts of the same object across repeat visits.
    mission = rows[0]["mission_id"]
    rows = [r for r in rows if r["mission_id"] == mission]
    latest_by_panel = {}
    for row in rows:
        latest_by_panel.setdefault(row["panel"], row)
    rows = list(latest_by_panel.values())
    per_panel = max(1, 12 // len(rows))
    lines = [
        "Ostatnia zapisana inspekcja: " + rows[0]["created_at"][:19].replace("T", " ") + " UTC."
    ]
    for row in reversed(rows):
        objects = (
            ", ".join(
                f"{d['label']} {d['instance']} ({100 * d['confidence']:.0f}%)"
                for d in row["detections"][:per_panel]
            )
            or "brak wykryć powyżej progu 30%"
        )
        if len(row["detections"]) > per_panel:
            objects += f", pozostałe {len(row['detections']) - per_panel} wykryć w kokpicie"
        lines.append(
            f"Sektor {row['sector']}, {row['panel']}: {objects}. Liczba wykryć w tej klatce: {row['total']}."
        )
    lines.append(
        f"Liczba detekcji w zapisanych obserwacjach tej misji: {sum(r['total'] for r in rows)}. Nie oznacza to liczby unikalnych osób między zdjęciami."
    )
    if re.search(r"osob|ludz|czlowiek", value):
        people = sum(r["counts"].get("person", 0) for r in rows)
        lines.append(f"Liczba wykryć klasy person (człowiek): {people}.")
    record = store.get(mission)
    if record and record.status.value != "succeeded":
        lines.append(
            "Misja nie ma statusu zakończonej: pokazuję tylko dotychczas zapisane tablice."
        )
    lines.append(
        "To wynik YOLO z zapisanej kamery, nie pewny opis wszystkich obiektów. Procent oznacza pewność detektora. Aktualne zdjęcia mogły się od tego czasu zmienić; raporty znajdziesz w kokpicie."
    )
    return "\n".join(lines)
