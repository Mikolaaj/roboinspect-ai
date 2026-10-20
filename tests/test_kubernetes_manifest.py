import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "render_kubernetes", Path(__file__).resolve().parents[1] / "scripts/render_kubernetes.py"
)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def test_kubernetes_storage_and_single_owner():
    result = renderer.manifests(
        "/workspace/project",
        {"gateway": "gateway:test", "mlflow": "mlflow:test"},
        1000,
        1000,
        "http://172.18.0.1:18767",
    )
    deployments = {
        item["metadata"]["name"]: item for item in result["items"] if item["kind"] == "Deployment"
    }
    assert set(deployments) == {"gateway", "mlflow", "prometheus"}
    for name in ("gateway", "mlflow"):
        deployment = deployments[name]
        assert deployment["spec"]["replicas"] == 1
        assert deployment["spec"]["strategy"]["type"] == "Recreate"
        pod = deployment["spec"]["template"]["spec"]
        assert pod["automountServiceAccountToken"] is False
        assert not pod.get("hostNetwork", False)
    mlflow = deployments["mlflow"]["spec"]["template"]["spec"]["containers"][0]
    assert "sqlite:////workspace/project/data/mlflow.db" in mlflow["command"]
    assert mlflow["volumeMounts"][0]["mountPath"] == "/workspace/project/data"
    gateway = deployments["gateway"]["spec"]["template"]["spec"]["containers"][0]
    assert gateway["env"][0]["valueFrom"]["secretKeyRef"]["name"] == "bridge"
    assert gateway["readinessProbe"]["httpGet"]["path"] == "/health/ready"
    assert gateway["livenessProbe"]["httpGet"]["path"] == "/health/live"
    pv = next(item for item in result["items"] if item["kind"] == "PersistentVolume")
    assert pv["spec"]["persistentVolumeReclaimPolicy"] == "Retain"


def test_manifest_requires_absolute_storage_path():
    with pytest.raises(ValueError):
        renderer.manifests("relative", {}, 1000, 1000, "http://localhost:8767")
