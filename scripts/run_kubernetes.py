#!/usr/bin/env python3
"""Run the local robot with Kubernetes HTTP services, MLflow and monitoring."""

import argparse
import json
import os
import secrets
import signal
import subprocess
import threading
import urllib.request
import webbrowser
from pathlib import Path

from kube_common import CLUSTER, ROOT, STATE, bridge_ip, ensure_cluster, env, kubectl, run
from render_kubernetes import manifests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--revision", help="Published full commit SHA")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / "artifacts/kubernetes-runtime.json"
    runtime.parent.mkdir(exist_ok=True)
    import fcntl

    lock = (STATE / "manager.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Kubernetes kokpit już działa.")
    if (ROOT / "artifacts/cockpit-runtime.json").exists():
        raise SystemExit("Zatrzymaj poprzedni kokpit: bash scripts/stop_compose.sh")
    # Do not replace another listener or start a duplicate MLflow database writer.
    import socket

    for port in (8765, 8767, 5001, 9090):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as exc:
                raise SystemExit(f"Port {port} jest zajęty. Zatrzymaj poprzedni tryb.") from exc
    stopping = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())
    children = []
    logdir = ROOT / "artifacts/kubernetes"
    logdir.mkdir(exist_ok=True)
    handles = []

    def start(name, command, child_env=None):
        handle = (logdir / (name + ".log")).open("w")
        handles.append(handle)
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=child_env or env(),
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        children.append(process)
        return process

    cluster_ready = False
    try:
        ensure_cluster()
        cluster_ready = True
        token = secrets.token_urlsafe(32)
        host = bridge_ip()
        relay_env = dict(
            env(),
            ROBOINSPECT_UPSTREAM="http://127.0.0.1:8767",
            ROBOINSPECT_BRIDGE_TOKEN=token,
            ROBOINSPECT_ALLOWED_HOSTS=f"{host}:18767",
        )
        start(
            "bridge",
            [
                str(ROOT / ".venv/bin/uvicorn"),
                "deployment.gateway:app",
                "--host",
                host,
                "--port",
                "18767",
            ],
            relay_env,
        )
        # Namespace and Secret are created without logging the token.
        kubectl(
            "apply",
            "-f",
            "-",
            input=json.dumps(
                {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "roboinspect"}}
            ),
        )
        kubectl(
            "apply",
            "-f",
            "-",
            input=json.dumps(
                {
                    "apiVersion": "v1",
                    "kind": "Secret",
                    "metadata": {"name": "bridge", "namespace": "roboinspect"},
                    "stringData": {"token": token},
                }
            ),
        )
        release = STATE / "release.json"
        if args.revision:
            import re

            if not re.fullmatch("[0-9a-f]{40}", args.revision):
                raise RuntimeError("Podaj pełny SHA commita")
            images = {
                name: f"ghcr.io/mikolaaj/roboinspect-ai-{name}:sha-{args.revision}"
                for name in ("gateway", "mlflow")
            }
        elif release.exists():
            images = json.loads(release.read_text())
        else:
            run("docker", "compose", "-p", "roboinspect-kube", "build")
            images = {name: f"roboinspect-kube-{name}:latest" for name in ("gateway", "mlflow")}
            run("kind", "load", "docker-image", "--name", CLUSTER, *images.values())
        desired = manifests(ROOT, images, os.getuid(), os.getgid(), f"http://{host}:18767")
        (logdir / "manifest.json").write_text(json.dumps(desired, indent=2))
        kubectl("apply", "-f", "-", input=json.dumps(desired))
        # Reload the local image even when the tag has not changed.
        kubectl(
            "-n", "roboinspect", "rollout", "restart", "deployment/gateway", "deployment/mlflow"
        )
        start(
            "ros",
            [
                "bash",
                "scripts/run_cockpit.sh",
                "--port",
                "8767",
                "--external-mlflow",
                "--no-browser",
            ],
        )
        for name in ("mlflow", "gateway", "prometheus"):
            print(
                f"Czekam na gotowość: {name}. Pierwszy start może potrwać kilka minut.", flush=True
            )
            kubectl(
                "-n", "roboinspect", "rollout", "status", "deployment/" + name, "--timeout=240s"
            )
        for name, port in [("gateway", 8765), ("mlflow", 5001), ("prometheus", 9090)]:
            start(
                "forward-" + name,
                [str(ROOT / ".venv/bin/python"), "scripts/forward_kubernetes.py", name, str(port)],
            )
        for _ in range(30):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8765/health/ready", timeout=3):
                    break
            except OSError:
                if stopping.wait(1):
                    return
        else:
            raise RuntimeError("Brama nie zgłosiła gotowości; sprawdź artifacts/kubernetes")
        runtime.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "start": Path(f"/proc/{os.getpid()}/stat").read_text().split()[21],
                }
            )
        )
        print(
            "Gotowe: kokpit http://127.0.0.1:8765/ | sterowanie /control | MLflow :5001 | monitoring :9090. Ctrl+C zamyka całość.",
            flush=True,
        )
        if not args.no_browser:
            webbrowser.open("http://127.0.0.1:8765/")
            webbrowser.open("http://127.0.0.1:8765/control")
        while not stopping.wait(1):
            if any(p.poll() is not None for p in children):
                raise RuntimeError("Proces zakończył się; sprawdź artifacts/kubernetes")
    except subprocess.CalledProcessError:
        if not stopping.is_set():
            raise
        print("Przerwano uruchamianie przez Ctrl+C. Zamykanie usług…", flush=True)
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
        for process in reversed(children):
            try:
                process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=15)
        if cluster_ready:
            kubectl("-n", "roboinspect", "scale", "deployment", "--all", "--replicas=0")
        runtime.unlink(missing_ok=True)
        for handle in handles:
            handle.close()
        print("Kokpit zatrzymany. Dane i klaster zachowane.", flush=True)


if __name__ == "__main__":
    main()
