import importlib.util
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location(
    "gateway", Path(__file__).resolve().parents[1] / "deployment/gateway.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_gateway_preserves_queries_and_streams():
    def upstream(request):
        assert request.url.port == 8767
        assert request.url.query == b"limit=2"
        assert "x-runtime-token" not in request.headers
        return httpx.Response(200, content=b"frame", headers={"content-type": "image/jpeg"})

    with TestClient(
        module.create_app(httpx.MockTransport(upstream)), base_url="http://127.0.0.1:8765"
    ) as client:
        response = client.get("/api/frame/robot.jpg?limit=2", headers={"x-runtime-token": "secret"})
        assert response.content == b"frame"
        assert response.headers["content-type"] == "image/jpeg"


def test_gateway_blocks_private_and_cross_origin():
    with TestClient(module.create_app(), base_url="http://127.0.0.1:8765") as client:
        assert client.post("/api/internal/reset").status_code == 403
        assert (
            client.post("/api/missions", headers={"origin": "https://evil.test"}).status_code == 403
        )
        assert client.get("/control", headers={"host": "evil.test"}).status_code == 403
        assert client.get("/control").status_code == 200


def test_gateway_readiness_requires_executor():
    def upstream(request):
        return httpx.Response(200, json={"executor_healthy": False})

    with TestClient(module.create_app(httpx.MockTransport(upstream))) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503


def test_gateway_rewrites_valid_origin_for_local_executor():
    def upstream(request):
        assert "origin" not in request.headers
        assert request.headers["host"] == "127.0.0.1:8767"
        return httpx.Response(200, json={"ok": True})

    with TestClient(
        module.create_app(httpx.MockTransport(upstream)), base_url="http://localhost:8765"
    ) as client:
        assert (
            client.post(
                "/api/chat", json={}, headers={"origin": "http://localhost:8765"}
            ).status_code
            == 200
        )


def test_metrics_report_failures_and_executor_readiness():
    def upstream(request):
        if request.url.path == "/health":
            return httpx.Response(200, json={"executor_healthy": True})
        return httpx.Response(503, json={"error": "unavailable"})

    with TestClient(
        module.create_app(httpx.MockTransport(upstream)), base_url="http://localhost:8765"
    ) as client:
        client.get("/api/status")
        text = client.get("/metrics").text
        assert "roboinspect_http_requests_total 1" in text
        assert "roboinspect_http_errors_total 1" in text
        assert "roboinspect_executor_ready 1" in text
        assert "roboinspect_http_active_requests 0" in text
        assert "unavailable" not in text


def test_bridge_requires_token_and_replaces_untrusted_outbound_token(monkeypatch):
    monkeypatch.setenv("ROBOINSPECT_BRIDGE_TOKEN", "expected")
    monkeypatch.setenv("ROBOINSPECT_UPSTREAM_TOKEN", "upstream-secret")

    def upstream(request):
        assert request.headers["x-bridge-token"] == "upstream-secret"
        return httpx.Response(200, json={"ok": True})

    with TestClient(
        module.create_app(httpx.MockTransport(upstream)), base_url="http://localhost:8765"
    ) as client:
        assert client.get("/health/live").status_code == 403
        assert client.get("/api/status", headers={"x-bridge-token": "wrong"}).status_code == 403
        assert client.get("/api/status", headers={"x-bridge-token": "expected"}).status_code == 200
