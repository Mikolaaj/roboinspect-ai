"""FastAPI routes shared by buttons and the future validated LLM planner."""

import json
import secrets
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from .chat import ChatRequest, ChatService
from .contracts import (
    ACTIVE,
    ConflictError,
    GoalRequest,
    MappingAction,
    MappingOperation,
    MappingRequest,
    MissionEvent,
    MissionPlan,
    MissionRecord,
    RuntimeUpdate,
    Sector,
    WarehouseAction,
)
from .inspection import InspectionService, inspection_plan, list_reports
from .mapping import project_zones
from .missions import MissionService
from .observation import observation_zones
from .operations import request_operation, request_warehouse
from .rag import documents
from .routes import hangar_layout
from .speech import AUDIO_TYPES, SpeechError, SpeechService, Transcript

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "operator/web"
CAMERAS = {"fpv", "follow", "overhead"}


def create_app(
    service: MissionService,
    operator=None,
    port=8765,
    shutdown: Callable | None = None,
    chat=None,
    speech=None,
):
    if operator is not None:
        service.inspector = InspectionService(service.store)
    chat = chat or ChatService(service)
    speech = speech or SpeechService()
    layout = json.loads((ROOT / "config/hangar.json").read_text())
    zones = layout["inspection_zones"]
    observation = observation_zones(layout)

    @asynccontextmanager
    async def lifespan(_):
        service.start_worker()
        chat.start()
        try:
            yield
        finally:
            stopping.set()
            chat.close()
            service.close()
            if shutdown:
                shutdown()
            service.store.close()

    app = FastAPI(title="RoboInspect AI — Missions", version="0.2.0", lifespan=lifespan)
    stopping = threading.Event()

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        if request.method == "POST":
            host = request.headers.get("host", "")
            if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                return JSONResponse({"error": "Host not allowed"}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != f"http://{host}":
                return JSONResponse({"error": "Origin not allowed"}, status_code=403)
            is_audio = request.url.path == "/api/speech/transcribe"
            content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
            if (is_audio and content_type not in AUDIO_TYPES) or (
                not is_audio and content_type != "application/json"
            ):
                return JSONResponse({"error": "Nieobsługiwany typ danych"}, status_code=415)
            try:
                limit = speech.config["max_bytes"] if is_audio else 16384
                if int(request.headers.get("content-length", "0")) > limit:
                    return JSONResponse({"error": "Żądanie jest za duże"}, status_code=413)
            except ValueError:
                return JSONResponse({"error": "Invalid content length"}, status_code=400)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(ConflictError)
    async def conflict(_, exc):
        return JSONResponse({"error": str(exc)}, status_code=409)

    @app.exception_handler(HTTPException)
    async def http_error(_, exc):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        details = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(
            {"error": "Nieprawidłowe polecenie", "detail": details},
            status_code=400 if request.url.path == "/api/goal" else 422,
        )

    @app.get("/api/speech/runtime")
    def speech_runtime():
        return speech.runtime()

    @app.post("/api/speech/transcribe", response_model=Transcript)
    async def transcribe_audio(request: Request):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > speech.config["max_bytes"]:
                raise HTTPException(413, "Nagranie jest za duże")
        try:
            return await run_in_threadpool(speech.transcribe, bytes(data))
        except SpeechError as exc:
            raise HTTPException(exc.code, str(exc)) from exc

    @app.get("/api/chat/runtime")
    def chat_runtime():
        import httpx

        try:
            with httpx.Client(timeout=1, trust_env=False) as client:
                tags = client.get("http://127.0.0.1:11435/api/tags")
                tags.raise_for_status()
                available = any(m["name"] == chat.planner.model for m in tags.json()["models"])
                loaded = client.get("http://127.0.0.1:11435/api/ps")
                loaded.raise_for_status()
                model = next(
                    (m for m in loaded.json()["models"] if m["name"] == chat.planner.model), None
                )
            return {
                "available": available,
                "model": chat.planner.model,
                "loaded": model is not None,
                "gpu_memory_bytes": model.get("size_vram", 0) if model else None,
            }
        except (httpx.HTTPError, ValueError, KeyError):
            return {
                "available": False,
                "model": chat.planner.model,
                "loaded": False,
                "message": "Uruchom kokpit; przygotowanie: bash scripts/setup_bielik.sh",
            }

    @app.get("/api/chat")
    def chat_history(
        before: int | None = Query(default=None, ge=1),
        limit: int = Query(default=100, ge=1, le=200),
        include_archived: bool = False,
    ):
        return chat.history(before, limit, include_archived)

    @app.get("/api/chat/control")
    def chat_control():
        return {"control_epoch": chat.control_epoch()}

    @app.post("/api/chat/{turn_id}/cancel")
    def stop_answer(turn_id: UUID, body: MappingRequest):
        record = chat.cancel_answer(str(turn_id))
        if record is None:
            raise HTTPException(404, "Wiadomość nie istnieje")
        return record

    @app.post("/api/chat/session")
    def open_chat_panel(
        body: MappingRequest, idempotency_key: str = Header(min_length=1, max_length=128)
    ):
        return chat.open_panel(idempotency_key)

    @app.post("/api/chat/new")
    def new_chat(body: MappingRequest, idempotency_key: str = Header(min_length=1, max_length=128)):
        return chat.new_conversation(idempotency_key)

    @app.post("/api/chat", status_code=202)
    def chat_message(
        body: ChatRequest,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=128),
    ):
        record, created = chat.submit(body.text, idempotency_key, body.control_epoch)
        response.status_code = 202 if created else 200
        return record

    @app.get("/api/history")
    def activity_history(limit: int = Query(default=30, ge=1, le=100)):
        rows = [
            {
                "id": r.id,
                "kind": "mission",
                "name": r.name,
                "status": r.status,
                "created_at": r.created_at,
                "message": r.message,
                "details": [
                    f"{'Analiza ' if s.action == 'inspect' else ''}{s.target} ({s.status})"
                    for s in r.steps
                ],
            }
            for r in service.store.list(limit)
        ]
        rows += [
            {
                "id": r.id,
                "kind": "warehouse" if r.kind.value.startswith("warehouse_") else "mapping",
                "name": r.name,
                "status": r.status,
                "created_at": r.created_at,
                "message": r.message,
                "saved_map": r.saved_map,
                "details": [e.message for e in r.events],
                "events": r.events,
            }
            for r in service.store.operation_list(limit)
        ]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)[:limit]

    @app.post("/api/mapping/{action}", response_model=MappingOperation, status_code=202)
    def mapping_action(
        action: MappingAction,
        body: MappingRequest,
        response: Response,
        idempotency_key: str | None = Header(default=None, min_length=1, max_length=128),
    ):
        record, created = request_operation(service, action, idempotency_key)
        response.status_code = 202 if created else 200
        return record

    @app.post("/api/warehouse/{action}", response_model=MappingOperation, status_code=202)
    def warehouse_action(
        action: WarehouseAction,
        body: MappingRequest,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=128),
    ):
        record, created = request_warehouse(service, action, idempotency_key)
        response.status_code = 202 if created else 200
        return record

    @app.post("/api/internal/runtime", include_in_schema=False)
    def runtime_update(update: RuntimeUpdate, x_runtime_token: str | None = Header(default=None)):
        expected = getattr(operator, "runtime_token", "")
        if not expected or not secrets.compare_digest(x_runtime_token or "", expected):
            raise HTTPException(403, "Runtime token required")
        operator.set_runtime(update.mode, update.transitioning, update.map_file)
        if update.world_file is not None and update.warehouse is not None:
            operator.set_warehouse(update.world_file, update.warehouse.model_dump())
        return {"accepted": True}

    @app.get("/api/missions", response_model=list[MissionRecord])
    def list_missions(limit: int = Query(default=30, ge=1, le=100)):
        return service.store.list(limit)

    @app.post("/api/missions", response_model=MissionRecord, status_code=202)
    def new_mission(
        plan: MissionPlan,
        response: Response,
        idempotency_key: str | None = Header(default=None, min_length=1, max_length=128),
    ):
        record, created = service.create(plan, idempotency_key)
        response.status_code = 202 if created else 200
        return record

    @app.get("/api/missions/{mission_id}", response_model=MissionRecord)
    def get_mission(mission_id: UUID):
        record = service.store.get(str(mission_id))
        if record is None:
            raise HTTPException(404, "Misja nie istnieje")
        return record

    @app.get("/api/missions/{mission_id}/events", response_model=list[MissionEvent])
    def mission_events(mission_id: UUID):
        get_mission(mission_id)
        return service.store.history(str(mission_id))

    @app.post("/api/missions/{mission_id}/cancel", response_model=MissionRecord)
    def cancel_mission(mission_id: UUID):
        get_mission(mission_id)
        return service.cancel(str(mission_id))

    @app.post("/api/goal", status_code=202)
    def legacy_goal(
        command: GoalRequest,
        response: Response,
        idempotency_key: str | None = Header(default=None, min_length=1, max_length=128),
    ):
        plan = MissionPlan(name=f"Przejazd do {command.goal}", steps=[{"target": command.goal}])
        record, created = service.create(plan, idempotency_key)
        response.status_code = 202 if created else 200
        return {"accepted": True, "goal": command.goal, "mission_id": record.id}

    @app.post("/api/cancel")
    def cancel_active(response: Response):
        jobs = service.store.operation_busy()
        if jobs:
            if jobs[0].kind != MappingAction.START or len(jobs) > 1:
                raise ConflictError("Trwa operacja przełączenia lub zapisu mapy")
            service.store.cancel_operation(jobs[0].id)
            response.status_code = 202
            return {"accepted": True, "operation_id": jobs[0].id}
        record = service.cancel()
        response.status_code = 202 if record and record.status in ACTIVE else 200
        return {"accepted": True, "mission_id": record.id if record else None}

    @app.get("/api/status")
    def status():
        result = service.robot.snapshot()
        result["inspection_zones"] = (
            project_zones(result["map"], zones) if result.get("map") else []
        )
        result["observation_zones"] = (
            project_zones(result["map"], observation) if result.get("map") else []
        )
        result["runtime_ready"] = result["ready"]
        record = service.summary()
        result["mission"] = record.model_dump(mode="json") if record else None
        result["ready"] = result["ready"] and service.healthy
        if record:
            result["busy"] = record.status in ACTIVE
            result["message"] = record.message
            result["mission_id"] = record.id
            result["events"] = [
                {"time": e.time.astimezone().strftime("%H:%M:%S"), "message": e.message}
                for e in service.store.history(record.id)
            ]
            if record.status.value == "queued":
                result["state"] = "dispatching"
            elif record.status.value == "running":
                result["state"] = "navigating"
            else:
                result["state"] = record.status.value
            if record.current_step is not None:
                result["goal"] = record.steps[record.current_step].target
                if (
                    record.status.value == "running"
                    and record.steps[record.current_step].action == "inspect"
                ):
                    result["state"] = "inspecting"
            if record.status.value == "uncertain":
                result["ready"] = False
        jobs = service.store.operation_busy()
        recent = service.store.operation_list(1)
        operation = jobs[0] if jobs else (recent[0] if recent else None)
        result["operation"] = operation.model_dump(mode="json") if operation else None
        result["operation_busy"] = bool(jobs)
        if operation and (jobs or record is None or operation.created_at > record.created_at):
            result.update(message=operation.message, state=operation.status.value, goal=None)
            result["events"] = [
                {"time": e.time.astimezone().strftime("%H:%M:%S"), "message": e.message}
                for e in operation.events
            ]
        if jobs:
            result.update(ready=False, busy=True)
            if jobs[0].cancel_requested:
                result.update(state="canceling", message="Zatrzymywanie obchodu…")
        return result

    @app.post("/api/inspect/{sector}", response_model=MissionRecord, status_code=202)
    def inspect_sector(
        sector: str,
        body: MappingRequest,
        response: Response,
        idempotency_key: str = Header(min_length=1, max_length=128),
    ):
        record, created = service.create(inspection_plan(sector), idempotency_key)
        response.status_code = 202 if created else 200
        return record

    @app.get("/api/inspections")
    def inspections(limit: int = Query(default=30, ge=1, le=100)):
        return list_reports(service.store, limit)

    @app.get("/api/inspections/{report_id}/{name}")
    def inspection_image(report_id: UUID, name: str):
        if name not in ("raw.jpg", "annotated.jpg", "segmented.jpg", "masks.png", "masks.npz"):
            raise HTTPException(404, "Nieznany obraz")
        path = ROOT / "data/inspections" / str(report_id) / name
        if not path.is_file():
            raise HTTPException(404, "Brak obrazu")
        return FileResponse(
            path,
            media_type="image/png"
            if name.endswith(".png")
            else "application/octet-stream"
            if name.endswith(".npz")
            else "image/jpeg",
        )

    def vision_request(path):
        import os

        import httpx

        try:
            with httpx.Client(timeout=1.5, trust_env=False) as client:
                r = client.get(
                    os.environ.get("ROBOINSPECT_VISION_URL", "http://127.0.0.1:8766") + path,
                    headers={"X-Runtime-Token": getattr(operator, "runtime_token", "")},
                )
                r.raise_for_status()
                return r
        except httpx.HTTPError as exc:
            raise HTTPException(503, "Detektor nie jest jeszcze gotowy") from exc

    @app.get("/api/vision")
    def vision_status():
        return vision_request("/latest").json()

    @app.get("/api/vision/frame.jpg")
    def vision_frame():
        return Response(vision_request("/frame.jpg").content, media_type="image/jpeg")

    @app.get("/api/hangar")
    def hangar():
        return hangar_layout(
            service.scenario,
            getattr(operator, "world_file", None),
            getattr(operator, "warehouse", {}).get("layout_id", "standard"),
        )

    @app.get("/api/sectors", response_model=dict[str, Sector])
    def sectors():
        import json

        return json.loads((ROOT / "config/hangar.json").read_text())["sectors"]

    @app.get("/health")
    def health():
        return {"service": "roboinspect", "executor_healthy": service.healthy}

    @app.get("/api/map.png")
    def map_image():
        if operator is None:
            raise HTTPException(503, "Mapa nie jest jeszcze dostępna")
        with operator.lock:
            data = operator.map_png
        if data is None:
            raise HTTPException(503, "Oczekiwanie na mapę")
        return Response(data, media_type="image/png")

    @app.get("/api/frame/{name}.jpg")
    def frame(name: str):
        if operator is None or name not in CAMERAS:
            raise HTTPException(404, "Camera not found")
        with operator.lock:
            image = operator.frames.get(name)
        if image is None:
            raise HTTPException(503, "Oczekiwanie na obraz")
        return Response(image["jpeg"], media_type="image/jpeg")

    def frames(name):
        sequence = -1
        try:
            while not stopping.is_set():
                with operator.frames_changed:
                    operator.frames_changed.wait_for(
                        lambda: operator.frames.get(name, {}).get("sequence", -1) != sequence,
                        timeout=1,
                    )
                    image = operator.frames.get(name)
                    if image is None:
                        sequence = -1
                    data = None
                    if image and image["sequence"] != sequence:
                        data, sequence = image["jpeg"], image["sequence"]
                if data is None:
                    yield b""
                else:
                    yield (
                        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(data)).encode()
                        + b"\r\n\r\n"
                        + data
                        + b"\r\n"
                    )
        finally:
            pass

    def detected_frames():
        import os

        import httpx

        sequence = None
        with httpx.Client(timeout=2, trust_env=False) as client:
            while not stopping.is_set():
                try:
                    result = client.get(
                        os.environ.get("ROBOINSPECT_VISION_URL", "http://127.0.0.1:8766")
                        + "/frame.jpg",
                        headers={"X-Runtime-Token": getattr(operator, "runtime_token", "")},
                    )
                    result.raise_for_status()
                    current = result.headers.get("x-frame-sequence")
                    if current != sequence or current is None:
                        sequence = current
                        data = result.content
                        yield (
                            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                            + str(len(data)).encode()
                            + b"\r\n\r\n"
                            + data
                            + b"\r\n"
                        )
                except httpx.HTTPError:
                    pass
                stopping.wait(0.15)

    @app.get("/stream/{name}.mjpg")
    def stream(name: str):
        if operator is None or name not in CAMERAS:
            raise HTTPException(404, "Camera not found")
        return StreamingResponse(
            detected_frames() if name == "fpv" else frames(name),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.get("/guide", response_class=HTMLResponse, include_in_schema=False)
    def operator_guide():
        sections = "".join(
            f'<section id="{escape(c["id"])}"><h2>{escape(c["title"])}</h2>'
            f"<p>{escape(c['text'])}</p></section>"
            for c in documents()
        )
        return HTMLResponse(
            '<!doctype html><html lang="pl"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Instrukcja operatora RoboInspect</title><link rel="stylesheet" href="/style.css">'
            '<main class="operator-guide"><a href="/control">Panel sterowania</a>'
            "<h1>Instrukcja operatora</h1>" + sections + "</main></html>",
            headers={
                "Content-Security-Policy": "default-src 'none'; style-src 'self'; base-uri 'none'"
            },
        )

    files = {
        "/": ("index.html", "text/html"),
        "/control": ("control.html", "text/html"),
        "/app.js": ("app.js", "text/javascript"),
        "/activity.js": ("activity.js", "text/javascript"),
        "/voice.js": ("voice.js", "text/javascript"),
        "/route-map.js": ("route-map.js", "text/javascript"),
        "/vision.js": ("vision.js", "text/javascript"),
        "/style.css": ("style.css", "text/css"),
    }

    def static_endpoint(filename, mime):
        def endpoint():
            return FileResponse(WEB / filename, media_type=mime)

        return endpoint

    for route, (filename, mime) in files.items():
        app.add_api_route(
            route, static_endpoint(filename, mime), methods=["GET"], include_in_schema=False
        )
    return app
