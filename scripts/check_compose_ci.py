#!/usr/bin/env python3
"""Build real images; check HTTP and MLflow persistence in an isolated stack."""

import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs)


def request(url, body=None, host=None):
    headers = {"Content-Type": "application/json"}
    if host:
        headers["Host"] = host
    req = urllib.request.Request(
        url, data=json.dumps(body).encode() if body is not None else None, headers=headers
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.read()


def main():
    report_dir = ROOT / "artifacts/compose-ci"
    report_dir.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        ROBOINSPECT_ROOT=str(ROOT),
        ROBOINSPECT_UID=str(os.getuid()),
        ROBOINSPECT_GID=str(os.getgid()),
    )
    config = json.loads(run("docker", "compose", "config", "--format", "json", cwd=ROOT, env=env))
    # Build from the production Dockerfiles before deriving isolated runtime settings.
    run("docker", "compose", "-p", "roboinspect-ci-images", "build", cwd=ROOT, env=env)
    with tempfile.TemporaryDirectory(prefix="roboinspect-ci-") as temporary:
        temp = Path(temporary)
        data = temp / "data"
        data.mkdir()
        services = config["services"]
        for name, service in services.items():
            service["image"] = f"roboinspect-ci-images-{name}"
            service.pop("network_mode", None)
            service.pop("healthcheck", None)
        gateway = services["gateway"]
        gateway["command"] = ["uvicorn", "gateway:app", "--host", "0.0.0.0", "--port", "8765"]
        gateway["environment"] = {"ROBOINSPECT_UPSTREAM": "http://operator-fixture:8767"}
        gateway["ports"] = ["127.0.0.1::8765"]
        mlflow = services["mlflow"]
        mlflow["volumes"] = [f"{data}:{data}"]
        mlflow["command"] = [
            "mlflow",
            "server",
            "--backend-store-uri",
            f"sqlite:///{data}/mlflow.db",
            "--default-artifact-root",
            str(data / "artifacts"),
            "--host",
            "0.0.0.0",
            "--port",
            "5001",
            "--workers",
            "1",
        ]
        mlflow["ports"] = ["127.0.0.1::5001"]
        services["operator-fixture"] = {
            "image": gateway["image"],
            "command": ["python", "/app/ci_operator.py"],
        }
        config_path = temp / "compose.json"
        config_path.write_text(json.dumps({"services": services}))
        project = "roboinspect-ci-" + uuid.uuid4().hex[:10]
        compose = ["docker", "compose", "-p", project, "-f", str(config_path)]

        def dc(*args):
            return run(*compose, *args, cwd=ROOT, env=env)

        def address(service, port):
            return "http://" + dc("port", service, str(port)).strip()

        def wait_ready(url, host=None):
            for _ in range(90):
                try:
                    return request(url, host=host)
                except (OSError, urllib.error.URLError):
                    time.sleep(1)
            raise RuntimeError(f"Not ready: {url}")

        try:
            dc("up", "-d", "--no-build")
            gateway_url = address("gateway", 8765)
            mlflow_url = address("mlflow", 5001)
            wait_ready(gateway_url + "/health/ready")
            wait_ready(mlflow_url + "/health")
            assert b"RoboInspect" in request(gateway_url + "/control", host="127.0.0.1:8765")
            assert json.loads(request(gateway_url + "/api/status", host="127.0.0.1:8765"))[
                "fixture"
            ]
            try:
                request(gateway_url + "/api/internal/runtime", {}, "127.0.0.1:8765")
            except urllib.error.HTTPError as exc:
                assert exc.code == 403
            else:
                raise AssertionError("Private endpoint exposed")
            experiment = json.loads(
                request(mlflow_url + "/api/2.0/mlflow/experiments/create", {"name": project})
            )["experiment_id"]
            created = json.loads(
                request(mlflow_url + "/api/2.0/mlflow/runs/create", {"experiment_id": experiment})
            )
            run_id = created["run"]["info"]["run_id"]
            request(
                mlflow_url + "/api/2.0/mlflow/runs/log-metric",
                {
                    "run_id": run_id,
                    "key": "ci_smoke",
                    "value": 1,
                    "timestamp": int(time.time() * 1000),
                    "step": 0,
                },
            )
            # Verify an artifact using the same client and storage as the server.
            artifact_code = (
                "from mlflow import MlflowClient; from pathlib import Path; "
                "p=Path('/tmp/ci-proof.txt'); p.write_text('persistent-proof'); "
                f"MlflowClient(tracking_uri='http://127.0.0.1:5001').log_artifact('{run_id}', str(p))"
            )
            dc("exec", "-T", "mlflow", "python", "-c", artifact_code)
            dc("down")
            dc("up", "-d", "--no-build")
            mlflow_url = address("mlflow", 5001)
            wait_ready(mlflow_url + "/health")
            saved = json.loads(request(mlflow_url + "/api/2.0/mlflow/runs/get?run_id=" + run_id))
            assert saved["run"]["data"]["metrics"][0]["value"] == 1
            verify_code = (
                "from mlflow import MlflowClient; from pathlib import Path; "
                f"p=MlflowClient(tracking_uri='http://127.0.0.1:5001').download_artifacts('{run_id}', 'ci-proof.txt', '/tmp'); "
                "assert Path(p).read_text() == 'persistent-proof'"
            )
            dc("exec", "-T", "mlflow", "python", "-c", verify_code)
            result = {
                "gateway_http": True,
                "private_routes_blocked": True,
                "mlflow_run_persisted": True,
                "mlflow_artifact_persisted": True,
                "ros_tested": False,
            }
            (report_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result))
        finally:
            try:
                (report_dir / "containers.log").write_text(dc("logs", "--no-color"))
            finally:
                dc("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
