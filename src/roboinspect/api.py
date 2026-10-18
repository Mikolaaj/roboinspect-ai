"""FastAPI routes shared by buttons and the future validated LLM planner."""

import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .contracts import (
    ACTIVE,
    ConflictError,
    GoalRequest,
    MissionEvent,
    MissionPlan,
    MissionRecord,
    Sector,
)
from .missions import MissionService

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "operator/web"
CAMERAS = {"fpv", "follow", "overhead"}


def create_app(service: MissionService, operator=None, port=8765, shutdown: Callable | None = None):
    @asynccontextmanager
    async def lifespan(_):
        service.start_worker()
        try:
            yield
        finally:
            stopping.set()
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
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"error": "Use application/json"}, status_code=415)
            try:
                if int(request.headers.get("content-length", "0")) > 16384:
                    return JSONResponse({"error": "Request too large"}, status_code=413)
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
        record = service.cancel()
        response.status_code = 202 if record and record.status in ACTIVE else 200
        return {"accepted": True, "mission_id": record.id if record else None}

    @app.get("/api/status")
    def status():
        result = service.robot.snapshot()
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
            if record.status.value == "uncertain":
                result["ready"] = False
        return result

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

    @app.get("/stream/{name}.mjpg")
    def stream(name: str):
        if operator is None or name not in CAMERAS:
            raise HTTPException(404, "Camera not found")
        return StreamingResponse(
            frames(name), media_type="multipart/x-mixed-replace; boundary=frame"
        )

    files = {
        "/": ("index.html", "text/html"),
        "/control": ("control.html", "text/html"),
        "/app.js": ("app.js", "text/javascript"),
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
