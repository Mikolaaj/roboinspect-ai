#!/usr/bin/env python3
"""Update the local cluster to a published SHA, with automatic image rollback."""

import argparse
import json
import re
import subprocess

from kube_common import CLUSTER, STATE, kubectl, run


def update_images(images, namespace="roboinspect", timeout="240s"):
    previous = {}
    for name in images:
        resource = json.loads(kubectl("-n", namespace, "get", "deployment", name, "-o", "json"))
        previous[name] = next(
            c["image"]
            for c in resource["spec"]["template"]["spec"]["containers"]
            if c["name"] == name
        )
    try:
        for name, image in images.items():
            kubectl("-n", namespace, "set", "image", "deployment/" + name, name + "=" + image)
        for name in images:
            kubectl(
                "-n", namespace, "rollout", "status", "deployment/" + name, "--timeout=" + timeout
            )
    except subprocess.CalledProcessError:
        for name, image in previous.items():
            kubectl("-n", namespace, "set", "image", "deployment/" + name, name + "=" + image)
        for name in previous:
            kubectl("-n", namespace, "rollout", "status", "deployment/" + name, "--timeout=240s")
        raise RuntimeError("Wdrożenie nieudane. Przywrócono poprzednie obrazy.") from None
    return previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.revision):
        raise SystemExit("Podaj pełny 40-znakowy SHA commita.")
    if args.rollback:
        for name in ("gateway", "mlflow"):
            print(kubectl("-n", "roboinspect", "rollout", "undo", "deployment/" + name))
        for name in ("gateway", "mlflow"):
            print(
                kubectl(
                    "-n", "roboinspect", "rollout", "status", "deployment/" + name, "--timeout=240s"
                )
            )
        restored = {}
        for name in ("gateway", "mlflow"):
            value = json.loads(
                kubectl("-n", "roboinspect", "get", "deployment", name, "-o", "json")
            )
            restored[name] = next(
                c["image"]
                for c in value["spec"]["template"]["spec"]["containers"]
                if c["name"] == name
            )
        (STATE / "release.json").write_text(json.dumps(restored))
    else:
        images = {
            name: f"ghcr.io/mikolaaj/roboinspect-ai-{name}:sha-{args.revision}"
            for name in ("gateway", "mlflow")
        }
        # Pull using the caller's registry credentials, then preload kind.
        # Private images need no long-lived imagePullSecret in the cluster.
        for image in images.values():
            run("docker", "pull", image)
        run("kind", "load", "docker-image", "--name", CLUSTER, *images.values())
        previous = update_images(images)
        (STATE / "release.json").write_text(json.dumps(images))
        print("Wdrożono:", json.dumps(images))
        print("Poprzednie obrazy:", json.dumps(previous))


if __name__ == "__main__":
    main()
