#!/usr/bin/env python3
"""Keep a loopback-only port forward alive across pod replacement."""

import argparse
import signal
import subprocess
import threading

from kube_common import env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service")
    parser.add_argument("port", type=int)
    args = parser.parse_args()
    stopping = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())
    while not stopping.is_set():
        process = subprocess.Popen(
            [
                "kubectl",
                "--context",
                "kind-roboinspect",
                "-n",
                "roboinspect",
                "port-forward",
                "--address",
                "127.0.0.1",
                "service/" + args.service,
                f"{args.port}:{args.port}",
            ],
            env=env(),
        )
        try:
            while process.poll() is None and not stopping.wait(0.5):
                pass
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        stopping.wait(1)


if __name__ == "__main__":
    main()
