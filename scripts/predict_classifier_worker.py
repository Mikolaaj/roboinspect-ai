#!/usr/bin/env python3
"""Read-only pilot prediction on one board crop. Never accepts robot commands."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from roboinspect.classifier import (
    CLASSES,
    PREPROCESS,
    digest_file,
    image_features,
    preprocess_image,
    ridge_scores,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--model", choices=["selected", "baseline", "resnet18"], default="selected")
    args = parser.parse_args()
    report = json.loads((args.run / "results.json").read_text())
    model = report["selection"]["selected"] if args.model == "selected" else args.model
    image = Image.open(args.image).convert("RGB")
    if model == "baseline":
        path = args.run / "baseline.npz"
        if digest_file(path) != report["model_sha256"]["baseline"]:
            raise ValueError("Model checksum mismatch")
        with np.load(path, allow_pickle=False) as data:
            scores = ridge_scores(data, np.stack([image_features(image)]))[0]
        softmax_label = "softmax_of_ridge_scores_not_calibrated"
    else:
        import torch
        from torchvision.models import resnet18
        from torchvision.transforms import functional as TF

        path = args.run / "resnet18.pt"
        if digest_file(path) != report["model_sha256"]["resnet18"]:
            raise ValueError("Model checksum mismatch")
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        if (
            checkpoint["classes"] != CLASSES
            or checkpoint["preprocess"] != PREPROCESS
            or checkpoint["snapshot_id"] != report["config"]["snapshot_id"]
        ):
            raise ValueError("Incompatible model metadata")
        network = resnet18(weights=None)
        network.fc = torch.nn.Linear(network.fc.in_features, len(CLASSES))
        network.load_state_dict(checkpoint["state_dict"])
        network.eval()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        network.to(device)
        torch.set_num_threads(2)
        value = TF.pil_to_tensor(preprocess_image(image)).float() / 255
        value = (value - torch.tensor(PREPROCESS["mean"]).view(3, 1, 1)) / torch.tensor(
            PREPROCESS["std"]
        ).view(3, 1, 1)
        with torch.inference_mode():
            scores = network(value.unsqueeze(0).to(device))[0].cpu().numpy()
        softmax_label = "uncalibrated_softmax"
    probabilities = np.exp(scores - scores.max())
    probabilities /= probabilities.sum()
    print(
        json.dumps(
            {
                "model": model,
                "condition": CLASSES[int(scores.argmax())],
                "scores": {name: float(probabilities[i]) for i, name in enumerate(CLASSES)},
                "score_kind": softmax_label,
                "snapshot_id": report["config"]["snapshot_id"],
                "model_sha256": report["model_sha256"][model],
                "pilot_only": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
