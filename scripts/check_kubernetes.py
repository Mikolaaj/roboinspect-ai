#!/usr/bin/env python3
"""Integration check: Kubernetes readiness, storage, monitoring and failed rollout recovery."""

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid

from deploy_kubernetes import update_images
from kube_common import CLUSTER, ROOT, ensure_cluster, env, kubectl, run
from render_kubernetes import manifests


def request(url, body=None, host=None):
    headers = {"Content-Type": "application/json"}
    if host:
        headers["Host"] = host
    req = urllib.request.Request(
        url, data=json.dumps(body).encode() if body is not None else None, headers=headers
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.read()


def wait(url, host=None):
    for _ in range(90):
        try:
            return request(url, host=host)
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise RuntimeError("Brak gotowości " + url)


def main():
    ensure_cluster()
    run("docker", "compose", "-p", "roboinspect-kube", "build")
    images = {name: f"roboinspect-kube-{name}:latest" for name in ("gateway", "mlflow")}
    run("kind", "load", "docker-image", "--name", CLUSTER, *images.values())
    name = "roboinspect-ci-" + uuid.uuid4().hex[:8]
    root = ROOT / "data/deploy/smoke" / name
    (root / "data").mkdir(parents=True)
    resources = manifests(
        root, images, os.getuid(), os.getgid(), "http://127.0.0.1:8767", fixture=True
    )
    for item in resources["items"]:
        metadata = item["metadata"]
        if item["kind"] == "Namespace":
            metadata["name"] = name
        elif item["kind"] == "PersistentVolume":
            metadata["name"] = name + "-data"
        else:
            metadata["namespace"] = name
        if item["kind"] == "PersistentVolumeClaim":
            item["spec"]["volumeName"] = name + "-data"
    processes = []
    reports = ROOT / "artifacts/kubernetes-check"
    reports.mkdir(parents=True, exist_ok=True)

    def forward(service, remote):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        log = (reports / (service + "-forward.log")).open("w")
        proc = subprocess.Popen(
            [
                "kubectl",
                "--context",
                "kind-" + CLUSTER,
                "-n",
                name,
                "port-forward",
                "--address",
                "127.0.0.1",
                "service/" + service,
                f"{port}:{remote}",
            ],
            env=env(),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        processes.append((proc, log))
        return f"http://127.0.0.1:{port}"

    try:
        kubectl("apply", "-f", "-", input=json.dumps(resources))
        for service in ("mlflow", "gateway", "prometheus"):
            kubectl("-n", name, "rollout", "status", "deployment/" + service, "--timeout=300s")
        gateway = forward("gateway", 8765)
        mlflow = forward("mlflow", 5001)
        prometheus = forward("prometheus", 9090)
        wait(gateway + "/health/ready")
        wait(mlflow + "/health", host="127.0.0.1:5001")
        wait(prometheus + "/-/ready")
        assert b"RoboInspect" in request(gateway + "/control", host="127.0.0.1:8765")
        assert b"roboinspect_executor_ready 1" in request(gateway + "/metrics")
        experiment = json.loads(
            request(mlflow + "/api/2.0/mlflow/experiments/create", {"name": name}, "127.0.0.1:5001")
        )["experiment_id"]
        created = json.loads(
            request(
                mlflow + "/api/2.0/mlflow/runs/create",
                {"experiment_id": experiment},
                "127.0.0.1:5001",
            )
        )
        run_id = created["run"]["info"]["run_id"]
        request(
            mlflow + "/api/2.0/mlflow/runs/log-metric",
            {
                "run_id": run_id,
                "key": "k8s_smoke",
                "value": 1,
                "timestamp": int(time.time() * 1000),
                "step": 0,
            },
            "127.0.0.1:5001",
        )
        kubectl("-n", name, "delete", "pod", "-l", "app=mlflow", "--wait=true")
        kubectl("-n", name, "rollout", "status", "deployment/mlflow", "--timeout=240s")
        mlflow = forward("mlflow", 5001)
        wait(mlflow + "/health", host="127.0.0.1:5001")
        saved = json.loads(
            request(mlflow + "/api/2.0/mlflow/runs/get?run_id=" + run_id, host="127.0.0.1:5001")
        )
        assert saved["run"]["data"]["metrics"][0]["value"] == 1
        for _ in range(45):
            data = json.loads(
                request(prometheus + "/api/v1/query?query=roboinspect_executor_ready")
            )
            if data["data"]["result"] and data["data"]["result"][0]["value"][1] == "1":
                break
            time.sleep(1)
        else:
            raise AssertionError("Prometheus nie zbiera metryk")
        print(
            "Test kontrolowany: błędny obraz ma nie osiągnąć gotowości; oczekiwany jest timeout i rollback.",
            flush=True,
        )
        try:
            update_images(
                {"gateway": "roboinspect-invalid:nonexistent"}, namespace=name, timeout="15s"
            )
        except RuntimeError as exc:
            assert "Przywrócono" in str(exc)
        else:
            raise AssertionError("Nie wykryto błędnego wdrożenia")
        result = {
            "kubernetes_ready": True,
            "http": True,
            "mlflow_pvc_persistence": True,
            "prometheus_scrape": True,
            "failed_rollout_recovered": True,
            "ros_tested": False,
        }
        (reports / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
    finally:
        for service in ("gateway", "mlflow", "prometheus"):
            try:
                (reports / (service + ".log")).write_text(
                    kubectl(
                        "-n",
                        name,
                        "logs",
                        "deployment/" + service,
                        "--all-containers=true",
                        "--tail=200",
                    )
                )
            except subprocess.CalledProcessError:
                pass
        for proc, log in processes:
            proc.terminate()
            proc.wait(timeout=10)
            log.close()
        kubectl("delete", "namespace", name, "--wait=true", "--timeout=120s")
        kubectl("delete", "pv", name + "-data", "--wait=true")
        shutil.rmtree(root)


if __name__ == "__main__":
    main()
