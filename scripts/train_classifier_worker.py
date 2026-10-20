#!/usr/bin/env python3
"""GPU-only worker boundary: fit pilot classifiers, select on validation, then evaluate test."""

import argparse
import hashlib
import json
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torchvision.models import resnet18
from torchvision.transforms import functional as TF

from roboinspect.classifier import (
    CLASSES,
    PREPROCESS,
    classification_metrics,
    fit_ridge,
    image_features,
    preprocess_image,
    ridge_scores,
    verify_snapshot,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 1 <= args.epochs <= 100:
        raise ValueError("Epochs outside 1..100")
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    torch.set_num_threads(2)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; choose explicit CPU profile in a later experiment")
    torch.cuda.manual_seed_all(args.seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    manifest = verify_snapshot(args.snapshot)
    rows = {
        part: [r for r in manifest["records"] if r["split"] == part]
        for part in ("train", "validation", "test")
    }

    def images(part):
        return [Image.open(args.snapshot / r["image"]).convert("RGB") for r in rows[part]]

    train_images = images("train")
    validation_images = images("validation")
    labels = {part: np.asarray([r["class_index"] for r in group]) for part, group in rows.items()}
    train_features = np.stack([image_features(im) for im in train_images])
    val_features = np.stack([image_features(im) for im in validation_images])
    baseline_candidates = []
    for alpha in [0.1, 1.0, 10.0]:
        candidate = fit_ridge(train_features, labels["train"], alpha)
        metrics = classification_metrics(
            labels["validation"], ridge_scores(candidate, val_features).argmax(1)
        )
        baseline_candidates.append({"alpha": alpha, "validation": metrics})
    best_index = max(
        range(len(baseline_candidates)),
        key=lambda i: (
            baseline_candidates[i]["validation"]["macro_f1"],
            baseline_candidates[i]["validation"]["accuracy"],
            -i,
        ),
    )
    baseline = fit_ridge(train_features, labels["train"], baseline_candidates[best_index]["alpha"])
    np.savez(out / "baseline.npz", **baseline)
    weights_sha = hashlib.sha256(args.weights.read_bytes()).hexdigest()
    if not weights_sha.startswith("f37072fd"):
        raise ValueError("Not the pinned official ResNet18 ImageNet checkpoint")
    model = resnet18(weights=None)
    model.load_state_dict(torch.load(args.weights, map_location="cpu", weights_only=True))
    for parameter in model.parameters():
        parameter.requires_grad = False
    model.fc = nn.Linear(model.fc.in_features, len(CLASSES))
    for parameter in model.layer4.parameters():
        parameter.requires_grad = True
    model = model.to("cuda")
    torch.cuda.reset_peak_memory_stats()
    optimizer = torch.optim.AdamW(
        [
            {"params": model.layer4.parameters(), "lr": 1e-4},
            {"params": model.fc.parameters(), "lr": 1e-3},
        ],
        weight_decay=1e-3,
    )
    mean = torch.tensor(PREPROCESS["mean"]).view(3, 1, 1)
    std = torch.tensor(PREPROCESS["std"]).view(3, 1, 1)

    def tensor(im, augment=False):
        im = preprocess_image(im)
        if augment:
            if random.random() < 0.5:
                im = TF.hflip(im)
            im = TF.rotate(im, random.uniform(-3, 3), fill=[128, 128, 128])
            im = TF.adjust_brightness(im, random.uniform(0.9, 1.1))
        return (TF.pil_to_tensor(im).float() / 255 - mean) / std

    val_tensor = torch.stack([tensor(im) for im in validation_images])

    def scores(value):
        model.eval()
        parts = []
        with torch.inference_mode():
            for batch in value.split(16):
                parts.append(model(batch.to("cuda")).cpu().numpy())
        return np.concatenate(parts)

    history = []
    best = None
    best_key = (-1.0, -1.0)
    stale = 0
    started = time.monotonic()
    for epoch in range(1, args.epochs + 1):
        model.eval()
        model.layer4.train()
        model.fc.train()
        # Preserve pretrained batch-normalization running statistics on this tiny dataset.
        for module in model.modules():
            if isinstance(module, nn.BatchNorm2d):
                module.eval()
        order = np.random.permutation(len(train_images))
        loss_sum = 0.0
        for start in range(0, len(order), 16):
            indices = order[start : start + 16]
            x = torch.stack([tensor(train_images[i], True) for i in indices]).to("cuda")
            y = torch.tensor(labels["train"][indices], dtype=torch.long, device="cuda")
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.cross_entropy(model(x), y)
            loss.backward()
            optimizer.step()
            loss_sum += loss.item() * len(indices)
        validation = classification_metrics(labels["validation"], scores(val_tensor).argmax(1))
        key = (validation["macro_f1"], validation["accuracy"])
        row = {
            "epoch": epoch,
            "train_loss": loss_sum / len(train_images),
            "validation_accuracy": validation["accuracy"],
            "validation_macro_f1": validation["macro_f1"],
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        if key > best_key:
            best_key = key
            best = epoch
            stale = 0
            torch.save(
                {
                    "state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
                    "classes": CLASSES,
                    "preprocess": PREPROCESS,
                    "architecture": "resnet18",
                    "snapshot_id": manifest["snapshot_id"],
                    "weights_sha256": weights_sha,
                    "seed": args.seed,
                    "best_epoch": epoch,
                },
                out / "resnet18.pt",
            )
        else:
            stale += 1
        if stale >= 6:
            break
    checkpoint = torch.load(out / "resnet18.pt", map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["state_dict"])
    model.to("cuda")
    validation_cnn = classification_metrics(labels["validation"], scores(val_tensor).argmax(1))
    validation_baseline = baseline_candidates[best_index]["validation"]
    # Tie goes to the simpler baseline. This choice is frozen before any test prediction.
    selected = (
        "resnet18"
        if (validation_cnn["macro_f1"], validation_cnn["accuracy"])
        > (validation_baseline["macro_f1"], validation_baseline["accuracy"])
        else "baseline"
    )
    selection = {
        "selected": selected,
        "criterion": "validation macro_f1, then accuracy; tie -> baseline",
        "snapshot_id": manifest["snapshot_id"],
        "best_epoch": best,
        "baseline_alpha": baseline_candidates[best_index]["alpha"],
        "validation": {"baseline": validation_baseline, "resnet18": validation_cnn},
    }
    (out / "selection.json").write_text(json.dumps(selection, indent=2))
    # First use of held-out test pixels for prediction is after the model choice is fixed above.
    test_images = images("test")
    test_tensor = torch.stack([tensor(im) for im in test_images])
    predictions = {
        "baseline": ridge_scores(
            baseline, np.stack([image_features(im) for im in test_images])
        ).argmax(1),
        "resnet18": scores(test_tensor).argmax(1),
    }
    results = {
        name: classification_metrics(labels["test"], pred) for name, pred in predictions.items()
    }
    records = [
        {
            "id": r["id"],
            "source_group": r["source_group"],
            "true": r["condition"],
            **{name: CLASSES[int(pred[i])] for name, pred in predictions.items()},
        }
        for i, r in enumerate(rows["test"])
    ]
    report = {
        "selection": selection,
        "test": results,
        "baseline_candidates": baseline_candidates,
        "history": history,
        "training_seconds": time.monotonic() - started,
        "device": torch.cuda.get_device_name(0),
        "cuda_peak_memory_mib": torch.cuda.max_memory_allocated() / 2**20,
        "torch_version": torch.__version__,
        "numpy_version": np.__version__,
        "seed": args.seed,
        "epochs_limit": args.epochs,
        "weights_sha256": weights_sha,
        "split_counts": {k: len(v) for k, v in rows.items()},
        "source_group_counts": {k: len({r["source_group"] for r in v}) for k, v in rows.items()},
        "predictions": records,
        "limitations": manifest["limitations"]
        + ["Uncalibrated model scores; pilot only; no automatic deployment or robot control."],
    }
    (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        "FINISHED",
        json.dumps(
            {
                "selected": selected,
                "test": {
                    k: {m: v[m] for m in ("accuracy", "macro_f1")} for k, v in results.items()
                },
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
