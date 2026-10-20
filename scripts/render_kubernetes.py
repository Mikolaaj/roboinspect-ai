#!/usr/bin/env python3
"""Render manifests for a single-node local kind cluster."""

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NS = "roboinspect"


def manifests(root, images, uid, gid, upstream, fixture=False):
    root = Path(root)
    if not root.is_absolute():
        raise ValueError("Absolute data root required")
    data = str(root / "data")
    items = [{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": NS}}]

    def resource(kind, name, spec=None, **extra):
        obj = {
            "apiVersion": "apps/v1" if kind == "Deployment" else "v1",
            "kind": kind,
            "metadata": {"name": name, "namespace": NS},
            **extra,
        }
        if spec is not None:
            obj["spec"] = spec
        items.append(obj)
        return obj

    resource("ConfigMap", "runtime", data={"ROBOINSPECT_UPSTREAM": upstream})
    # The kind node explicitly mounts this existing directory from the laptop.
    items.append(
        {
            "apiVersion": "v1",
            "kind": "PersistentVolume",
            "metadata": {"name": "roboinspect-data"},
            "spec": {
                "capacity": {"storage": "20Gi"},
                "accessModes": ["ReadWriteOnce"],
                "storageClassName": "",
                "persistentVolumeReclaimPolicy": "Retain",
                "hostPath": {"path": data, "type": "Directory"},
            },
        }
    )
    resource(
        "PersistentVolumeClaim",
        "data",
        {
            "accessModes": ["ReadWriteOnce"],
            "storageClassName": "",
            "volumeName": "roboinspect-data",
            "resources": {"requests": {"storage": "20Gi"}},
        },
    )
    for name, port in [("gateway", 8765), ("mlflow", 5001)]:
        probe = "/health/live" if name == "gateway" else "/health"
        container = {
            "name": name,
            "image": images[name],
            "imagePullPolicy": "IfNotPresent",
            "ports": [{"name": "http", "containerPort": port}],
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": 10001 if name == "gateway" else uid,
                "runAsGroup": 10001 if name == "gateway" else gid,
                "allowPrivilegeEscalation": False,
                "capabilities": {"drop": ["ALL"]},
            },
            "resources": {
                "requests": {"cpu": "100m", "memory": "128Mi" if name == "gateway" else "512Mi"},
                "limits": {"cpu": "2", "memory": "512Mi" if name == "gateway" else "2Gi"},
            },
            "startupProbe": {
                "httpGet": {"path": probe, "port": port},
                "failureThreshold": 60,
                "periodSeconds": 5,
            },
            "livenessProbe": {"httpGet": {"path": probe, "port": port}, "periodSeconds": 15},
            "readinessProbe": {
                "httpGet": {
                    "path": "/health/ready" if name == "gateway" else "/health",
                    "port": port,
                },
                "timeoutSeconds": 5,
                "periodSeconds": 5,
            },
        }
        if name == "mlflow":
            for field in ("startupProbe", "livenessProbe", "readinessProbe"):
                container[field]["httpGet"]["httpHeaders"] = [
                    {"name": "Host", "value": "localhost:5001"}
                ]
        pod = {
            "automountServiceAccountToken": False,
            "containers": [container],
            "terminationGracePeriodSeconds": 30,
        }
        if name == "gateway":
            container["command"] = [
                "uvicorn",
                "gateway:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
            ]
            container["envFrom"] = [{"configMapRef": {"name": "runtime"}}]
            if not fixture:
                container["env"] = [
                    {
                        "name": "ROBOINSPECT_UPSTREAM_TOKEN",
                        "valueFrom": {"secretKeyRef": {"name": "bridge", "key": "token"}},
                    }
                ]
            container["securityContext"]["readOnlyRootFilesystem"] = True
            if fixture:
                pod["containers"].append(
                    {
                        "name": "operator-fixture",
                        "image": images[name],
                        "imagePullPolicy": "IfNotPresent",
                        "command": ["python", "/app/ci_operator.py"],
                    }
                )
        else:
            container["env"] = [{"name": "HOME", "value": "/tmp"}]
            container["command"] = [
                "mlflow",
                "server",
                "--backend-store-uri",
                f"sqlite:///{data}/mlflow.db",
                "--default-artifact-root",
                data + "/mlflow-artifacts",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
                "--workers",
                "1",
                "--allowed-hosts",
                "127.0.0.1:5001,localhost:5001,mlflow:5001,mlflow.roboinspect.svc.cluster.local:5001",
            ]
            container["volumeMounts"] = [{"name": "data", "mountPath": data}]
            pod["volumes"] = [{"name": "data", "persistentVolumeClaim": {"claimName": "data"}}]
        resource(
            "Deployment",
            name,
            {
                "replicas": 1,
                "revisionHistoryLimit": 5,
                "strategy": {"type": "Recreate"},
                "selector": {"matchLabels": {"app": name}},
                "template": {"metadata": {"labels": {"app": name}}, "spec": pod},
            },
        )
        resource(
            "Service",
            name,
            {
                "selector": {"app": name},
                "ports": [{"name": "http", "port": port, "targetPort": port}],
            },
        )
    monitor = (
        (ROOT / "deployment/monitoring/prometheus.yml")
        .read_text()
        .replace("127.0.0.1:8765", "gateway:8765")
    )
    resource(
        "ConfigMap",
        "monitoring",
        data={
            "prometheus.yml": monitor,
            "alerts.yml": (ROOT / "deployment/monitoring/alerts.yml").read_text(),
        },
    )
    resource(
        "Deployment",
        "prometheus",
        {
            "replicas": 1,
            "selector": {"matchLabels": {"app": "prometheus"}},
            "template": {
                "metadata": {"labels": {"app": "prometheus"}},
                "spec": {
                    "automountServiceAccountToken": False,
                    "containers": [
                        {
                            "name": "prometheus",
                            "image": "prom/prometheus:v3.5.0",
                            "args": [
                                "--config.file=/etc/prometheus/prometheus.yml",
                                "--storage.tsdb.path=/prometheus",
                                "--storage.tsdb.retention.time=7d",
                            ],
                            "ports": [{"containerPort": 9090}],
                            "resources": {
                                "requests": {"cpu": "50m", "memory": "128Mi"},
                                "limits": {"cpu": "500m", "memory": "512Mi"},
                            },
                            "readinessProbe": {"httpGet": {"path": "/-/ready", "port": 9090}},
                            "volumeMounts": [
                                {
                                    "name": "config",
                                    "mountPath": "/etc/prometheus",
                                    "readOnly": True,
                                },
                                {"name": "metrics", "mountPath": "/prometheus"},
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": "config", "configMap": {"name": "monitoring"}},
                        {"name": "metrics", "emptyDir": {"sizeLimit": "1Gi"}},
                    ],
                },
            },
        },
    )
    resource(
        "Service",
        "prometheus",
        {"selector": {"app": "prometheus"}, "ports": [{"port": 9090, "targetPort": 9090}]},
    )
    return {"apiVersion": "v1", "kind": "List", "items": items}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gateway-image", required=True)
    p.add_argument("--mlflow-image", required=True)
    p.add_argument("--upstream", required=True)
    a = p.parse_args()
    print(
        json.dumps(
            manifests(
                ROOT,
                {"gateway": a.gateway_image, "mlflow": a.mlflow_image},
                os.getuid(),
                os.getgid(),
                a.upstream,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
