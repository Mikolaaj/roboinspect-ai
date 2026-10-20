#!/usr/bin/env python3
"""Freeze reviewed data, run isolated PyTorch training, log results and artifacts in MLflow."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

from mlflow.tracking import MlflowClient

from roboinspect.classifier import digest_file, freeze_dataset

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_URL = "https://download.pytorch.org/models/resnet18-f37072fd.pth"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 1 <= args.epochs <= 100:
        raise ValueError("Epochs must be 1..100")
    env_python = ROOT / "data/vision/env/bin/python"
    if not env_python.is_file():
        raise RuntimeError("Najpierw uruchom bash scripts/setup_vision.sh")
    snapshot = freeze_dataset(ROOT)
    print("SNAPSHOT", snapshot.name, flush=True)
    run_dir = ROOT / "data/classifier/runs" / str(uuid4())
    run_dir.mkdir(parents=True)
    cached = Path.home() / ".cache/torch/hub/checkpoints/resnet18-f37072fd.pth"
    weights = ROOT / "data/classifier/pretrained/resnet18-f37072fd.pth"
    weights.parent.mkdir(parents=True, exist_ok=True)
    if not weights.exists():
        temp = weights.with_suffix(".tmp")
        if cached.exists():
            shutil.copyfile(cached, temp)
        else:
            with urlopen(WEIGHTS_URL, timeout=60) as response, temp.open("wb") as output:
                shutil.copyfileobj(response, output)
        if not digest_file(temp).startswith("f37072fd"):
            raise RuntimeError("Niezgodne wagi ResNet18")
        temp.replace(weights)
    if not digest_file(weights).startswith("f37072fd"):
        raise RuntimeError("Niezgodne wagi ResNet18")
    client = MlflowClient(tracking_uri=f"sqlite:///{ROOT / 'data/mlflow.db'}")
    experiment = client.get_experiment_by_name("roboinspect-classifier")
    eid = (
        experiment.experiment_id
        if experiment
        else client.create_experiment(
            "roboinspect-classifier",
            artifact_location=(ROOT / "data/mlflow-artifacts/classifier").as_uri(),
        )
    )
    parent = client.create_run(
        eid,
        tags={
            "mlflow.runName": "pilot-classifier-" + snapshot.name[:8],
            "stage": "pilot-training",
            "snapshot_id": snapshot.name,
            "selection_split": "validation",
            "automatic_deployment": "false",
        },
    )
    parent_id = parent.info.run_id
    children = []
    config = {
        "seed": args.seed,
        "epochs_limit": args.epochs,
        "snapshot_id": snapshot.name,
        "weights_url": WEIGHTS_URL,
        "weights_sha256": digest_file(weights),
        "worker_sha256": digest_file(ROOT / "scripts/train_classifier_worker.py"),
        "classifier_module_sha256": digest_file(ROOT / "src/roboinspect/classifier.py"),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "dirty_checkout": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        ),
        "baseline_alphas": [0.1, 1.0, 10.0],
        "cnn_layer4_lr": 1e-4,
        "cnn_fc_lr": 1e-3,
        "weight_decay": 1e-3,
        "batch_size": 16,
        "early_stopping_patience": 6,
    }
    client.log_dict(parent_id, config, "config.json")
    client.log_artifact(parent_id, str(snapshot / "manifest.json"), "dataset")
    client.log_artifact(parent_id, str(ROOT / "src/roboinspect/classifier.py"), "source")
    client.log_artifact(parent_id, str(ROOT / "scripts/train_classifier_worker.py"), "source")
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        env["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        with (run_dir / "training.log").open("w") as log:
            process = subprocess.Popen(
                [
                    str(env_python),
                    str(ROOT / "scripts/train_classifier_worker.py"),
                    "--snapshot",
                    str(snapshot),
                    "--output",
                    str(run_dir),
                    "--weights",
                    str(weights),
                    "--epochs",
                    str(args.epochs),
                    "--seed",
                    str(args.seed),
                ],
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                for line in process.stdout:
                    print(line, end="", flush=True)
                    log.write(line)
                    log.flush()
                if process.wait() != 0:
                    raise RuntimeError(
                        "Trening zakończony błędem; sprawdź " + str(run_dir / "training.log")
                    )
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                raise
        result = json.loads((run_dir / "results.json").read_text())
        subprocess.run(
            [
                str(env_python),
                str(ROOT / "scripts/plot_classifier_results.py"),
                "--run",
                str(run_dir),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
        for name in ("baseline", "resnet18"):
            run = client.create_run(
                eid,
                tags={
                    "mlflow.runName": name,
                    "mlflow.parentRunId": parent_id,
                    "snapshot_id": snapshot.name,
                    "model_family": name,
                    "pilot": "true",
                },
            )
            rid = run.info.run_id
            children.append(rid)
            for key, value in config.items():
                client.log_param(
                    rid, key, json.dumps(value) if isinstance(value, (list, dict)) else value
                )
            for split, metrics in [
                ("validation", result["selection"]["validation"][name]),
                ("test", result["test"][name]),
            ]:
                for metric in ("accuracy", "macro_f1", "balanced_accuracy", "n"):
                    client.log_metric(rid, split + "_" + metric, metrics[metric])
                for label, values in metrics["per_class"].items():
                    for metric, value in values.items():
                        client.log_metric(rid, split + "_" + label + "_" + metric, value)
                client.log_artifact(rid, str(run_dir / f"{name}-{split}-confusion.svg"))
                client.log_dict(rid, metrics, split + "-metrics.json")
            if name == "resnet18":
                client.log_artifact(rid, str(run_dir / "learning-curves.svg"))
                for epoch in result["history"]:
                    for key in ("train_loss", "validation_accuracy", "validation_macro_f1"):
                        client.log_metric(rid, key, epoch[key], step=epoch["epoch"])
                client.log_metric(rid, "cuda_peak_memory_mib", result["cuda_peak_memory_mib"])
                client.log_param(rid, "best_epoch", result["selection"]["best_epoch"])
            model_path = run_dir / ("resnet18.pt" if name == "resnet18" else "baseline.npz")
            client.log_artifact(rid, str(model_path), "model")
            client.log_param(rid, "model_sha256", digest_file(model_path))
            client.set_terminated(rid)
        result["mlflow"] = {
            "experiment": "roboinspect-classifier",
            "parent_run_id": parent_id,
            "child_run_ids": children,
        }
        result["run_directory"] = str(run_dir)
        result["snapshot_directory"] = str(snapshot)
        result["config"] = config
        result["model_sha256"] = {
            name: digest_file(run_dir / file)
            for name, file in [("baseline", "baseline.npz"), ("resnet18", "resnet18.pt")]
        }
        (run_dir / "results.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        )
        client.log_artifact(parent_id, str(run_dir / "results.json"))
        client.log_artifact(parent_id, str(run_dir / "selection.json"))
        client.log_artifact(parent_id, str(run_dir / "training.log"))
        client.set_tag(parent_id, "selected_model", result["selection"]["selected"])
        client.set_terminated(parent_id)
        index = ROOT / "data/classifier/latest.json"
        temp = index.with_suffix(".tmp")
        temp.write_text(
            json.dumps(
                {
                    "results": str(run_dir / "results.json"),
                    "snapshot_id": snapshot.name,
                    "mlflow_parent_run_id": parent_id,
                },
                indent=2,
            )
        )
        temp.replace(index)
        proof = {
            k: result[k]
            for k in (
                "selection",
                "test",
                "split_counts",
                "source_group_counts",
                "device",
                "cuda_peak_memory_mib",
                "training_seconds",
                "mlflow",
                "model_sha256",
                "limitations",
                "config",
            )
        }
        (ROOT / "docs/verification/classifier-training.json").write_text(
            json.dumps(proof, ensure_ascii=False, indent=2) + "\n"
        )
        print("WYNIKI", run_dir / "results.json", flush=True)
        print("MLFLOW", parent_id, flush=True)
    except BaseException:
        for rid in children:
            if client.get_run(rid).info.status == "RUNNING":
                client.set_terminated(rid, status="FAILED")
        client.set_terminated(parent_id, status="FAILED")
        raise


if __name__ == "__main__":
    main()
