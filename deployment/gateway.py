"""Local HTTP gateway. ROS and the sole mission executor remain on the host."""

import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

WEB = Path(__file__).resolve().parent / "web"
if not WEB.is_dir():
    WEB = Path(__file__).resolve().parents[1] / "operator/web"
UPSTREAM = os.environ.get("ROBOINSPECT_UPSTREAM", "http://127.0.0.1:8767")
STATIC = {"/": "index.html", "/control": "control.html", "/dataset/review": "dataset-review.html"}
HOP = {
    "connection",
    "keep-alive",
    "transfer-encoding",
    "upgrade",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "content-encoding",
    "content-length",
}


def create_app(transport=None):
    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(
            transport=transport, timeout=httpx.Timeout(120, connect=3)
        ) as client:
            app.state.client = client
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    bridge_token = os.environ.get("ROBOINSPECT_BRIDGE_TOKEN", "")
    upstream_token = os.environ.get("ROBOINSPECT_UPSTREAM_TOKEN", "")
    allowed_hosts = set(
        os.environ.get("ROBOINSPECT_ALLOWED_HOSTS", "127.0.0.1:8765,localhost:8765").split(",")
    )

    @app.middleware("http")
    async def bridge_auth(request: Request, call_next):
        if bridge_token and not secrets.compare_digest(
            request.headers.get("x-bridge-token", ""), bridge_token
        ):
            return JSONResponse({"error": "Bridge authentication required"}, status_code=403)
        return await call_next(request)

    def backend_headers():
        return {"X-Bridge-Token": upstream_token} if upstream_token else {}

    counters = {"requests": 0, "errors": 0, "seconds": 0.0, "active": 0}
    lock = threading.Lock()

    @app.middleware("http")
    async def observe(request: Request, call_next):
        if request.url.path in {"/metrics", "/health/live", "/health/ready"}:
            return await call_next(request)
        start = time.monotonic()
        with lock:
            counters["active"] += 1
        failed = False
        try:
            response = await call_next(request)
            failed = response.status_code >= 500
            return response
        except Exception:
            failed = True
            raise
        finally:
            with lock:
                counters["requests"] += 1
                counters["errors"] += int(failed)
                counters["seconds"] += time.monotonic() - start
                counters["active"] -= 1

    @app.get("/metrics")
    async def metrics(request: Request):
        from fastapi.responses import PlainTextResponse

        try:
            health = await request.app.state.client.get(
                UPSTREAM + "/health", timeout=3, headers=backend_headers()
            )
            ready = health.is_success and health.json().get("executor_healthy") is True
        except (httpx.HTTPError, ValueError):
            ready = False
        with lock:
            snapshot = dict(counters)
        values = {
            "roboinspect_http_requests_total": ("counter", snapshot["requests"]),
            "roboinspect_http_errors_total": ("counter", snapshot["errors"]),
            "roboinspect_http_headers_seconds_total": ("counter", snapshot["seconds"]),
            "roboinspect_http_active_requests": ("gauge", snapshot["active"]),
            "roboinspect_executor_ready": ("gauge", int(ready)),
        }
        body = "".join(
            f"# TYPE {name} {kind}\n{name} {value}\n" for name, (kind, value) in values.items()
        )
        return PlainTextResponse(body, media_type="text/plain; version=0.0.4")

    @app.get("/health/live")
    def live():
        return {"service": "roboinspect-gateway"}

    @app.get("/health/ready")
    async def ready(request: Request):
        try:
            response = await request.app.state.client.get(
                UPSTREAM + "/health", headers=backend_headers()
            )
            healthy = response.is_success and response.json().get("executor_healthy") is True
        except (httpx.HTTPError, ValueError):
            healthy = False
        return JSONResponse({"ready": healthy}, status_code=200 if healthy else 503)

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def proxy(path: str, request: Request):
        host = request.headers.get("host", "")
        if host not in allowed_hosts:
            return JSONResponse({"error": "Host not allowed"}, status_code=403)
        if path.startswith("api/internal"):
            return JSONResponse({"error": "Private endpoint"}, status_code=403)
        if request.method == "POST":
            origin = request.headers.get("origin")
            if origin and origin != "http://" + host:
                return JSONResponse({"error": "Origin not allowed"}, status_code=403)
        filename = STATIC.get("/" + path)
        if not filename and "/" not in path and path.endswith((".js", ".css")):
            filename = path
        if request.method == "GET" and filename and (WEB / filename).is_file():
            return FileResponse(WEB / filename, headers={"Cache-Control": "no-cache"})
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in HOP | {"host", "origin", "x-runtime-token", "x-bridge-token"}
        }
        headers.update(backend_headers())
        url = UPSTREAM + "/" + path
        if request.url.query:
            url += "?" + request.url.query
        try:
            upstream_request = request.app.state.client.build_request(
                request.method, url, headers=headers, content=request.stream()
            )
            response = await request.app.state.client.send(upstream_request, stream=True)
        except httpx.HTTPError:
            return JSONResponse({"error": "Lokalny proces ROS jest niedostępny"}, status_code=503)
        return StreamingResponse(
            response.aiter_bytes(),
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower() not in HOP},
            background=BackgroundTask(response.aclose),
        )

    return app


app = create_app()
