"""Project-scoped Kubernetes tooling. Does not change the user's kubeconfig."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "data/deploy/bin"
STATE = ROOT / "data/deploy"
CLUSTER = "roboinspect"


def env():
    return dict(
        os.environ,
        PATH=str(BIN) + os.pathsep + os.environ["PATH"],
        KUBECONFIG=str(STATE / "kubeconfig"),
        ROBOINSPECT_ROOT=str(ROOT),
        ROBOINSPECT_UID=str(os.getuid()),
        ROBOINSPECT_GID=str(os.getgid()),
    )


def run(*args, input=None):
    return subprocess.check_output(args, cwd=ROOT, env=env(), text=True, input=input)


def kubectl(*args, input=None):
    return run("kubectl", "--context", "kind-" + CLUSTER, *args, input=input)


def ensure_cluster():
    STATE.mkdir(parents=True, exist_ok=True)
    if not (BIN / "kind").exists() or not (BIN / "kubectl").exists():
        raise RuntimeError("Najpierw wykonaj bash scripts/setup_kubernetes_tools.sh")
    if CLUSTER not in run("kind", "get", "clusters").splitlines():
        (ROOT / "data").mkdir(exist_ok=True)
        config = {
            "kind": "Cluster",
            "apiVersion": "kind.x-k8s.io/v1alpha4",
            "nodes": [
                {
                    "role": "control-plane",
                    "extraMounts": [
                        {"hostPath": str(ROOT / "data"), "containerPath": str(ROOT / "data")}
                    ],
                }
            ],
        }
        path = STATE / "kind.json"
        path.write_text(json.dumps(config))
        run(
            "kind",
            "create",
            "cluster",
            "--name",
            CLUSTER,
            "--image",
            "kindest/node:v1.34.0",
            "--config",
            str(path),
            "--wait",
            "120s",
        )
    run(
        "kind", "export", "kubeconfig", "--name", CLUSTER, "--kubeconfig", str(STATE / "kubeconfig")
    )
    (STATE / "kubeconfig").chmod(0o600)


def bridge_ip():
    import ipaddress

    config = json.loads(run("docker", "network", "inspect", "kind"))[0]["IPAM"]["Config"]
    for subnet in config:
        gateway = subnet.get("Gateway", "")
        if gateway and ipaddress.ip_address(gateway).version == 4:
            return gateway
    raise RuntimeError("Brak bramy IPv4 w sieci kind")
