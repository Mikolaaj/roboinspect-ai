from fastapi.testclient import TestClient

from roboinspect.api import create_app


def test_api_contract_and_idempotency(service):
    with TestClient(create_app(service), base_url="http://127.0.0.1:8765") as client:
        payload = {"name": "A i baza", "steps": [{"target": "A"}, {"target": "BASE"}]}
        first = client.post("/api/missions", json=payload, headers={"Idempotency-Key": "test"})
        assert first.status_code == 202
        duplicate = client.post("/api/missions", json=payload, headers={"Idempotency-Key": "test"})
        assert duplicate.status_code == 200
        assert duplicate.json()["id"] == first.json()["id"]
        assert client.post("/api/goal", json={"goal": "B"}).status_code == 409
        assert client.get("/api/missions").json()[0]["name"] == "A i baza"
        assert client.get(f"/api/missions/{first.json()['id']}/events").json()
        assert client.get("/openapi.json").json()["components"]["schemas"]["MissionPlan"]
        assert client.get("/control?name=../../.git/config").text.startswith("<!doctype html>")
        assert client.post("/api/cancel", json={}).status_code in (200, 202)


def test_invalid_commands_and_origin(service):
    with TestClient(create_app(service), base_url="http://127.0.0.1:8765") as client:
        assert client.post("/api/goal", json={"goal": "UNKNOWN"}).status_code == 400
        assert client.post("/api/missions", json={"steps": []}).status_code == 422
        assert (
            client.post(
                "/api/goal", json={"goal": "A"}, headers={"Origin": "https://example.com"}
            ).status_code
            == 403
        )
        assert client.post("/api/cancel", content="{}").status_code == 415
        assert client.get("/api/missions/00000000-0000-0000-0000-000000000000").status_code == 404
        assert client.get("/api/frame/fpv.jpg").status_code == 404


def test_map_endpoint_before_and_after_first_grid(service):
    import threading
    from types import SimpleNamespace

    operator = SimpleNamespace(lock=threading.RLock(), map_png=None)
    with TestClient(create_app(service, operator), base_url="http://127.0.0.1:8765") as client:
        assert client.get("/api/map.png").status_code == 503
        operator.map_png = b"example-png-bytes"
        response = client.get("/api/map.png")
        assert response.headers["content-type"] == "image/png"
        assert response.content == operator.map_png
