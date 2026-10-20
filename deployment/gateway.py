"""Local HTTP gateway. ROS and the sole mission executor remain on the host."""

import os
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

    @app.get("/health/live")
    def live():
        return {"service": "roboinspect-gateway"}

    @app.get("/health/ready")
    async def ready(request: Request):
        try:
            response = await request.app.state.client.get(UPSTREAM + "/health")
            healthy = response.is_success and response.json().get("executor_healthy") is True
        except (httpx.HTTPError, ValueError):
            healthy = False
        return JSONResponse({"ready": healthy}, status_code=200 if healthy else 503)

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def proxy(path: str, request: Request):
        host = request.headers.get("host", "")
        if host not in {"127.0.0.1:8765", "localhost:8765"}:
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
            if k.lower() not in HOP | {"host", "origin", "x-runtime-token"}
        }
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
