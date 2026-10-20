#!/usr/bin/env python3
"""Render standard confusion matrices and learning curves from measured classifier results."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from roboinspect.classifier import CLASSES

parser = argparse.ArgumentParser()
parser.add_argument("--run", type=Path, required=True)
args = parser.parse_args()
report = json.loads((args.run / "results.json").read_text())
for name in ("baseline", "resnet18"):
    for split in ("validation", "test"):
        values = (
            report["test"][name] if split == "test" else report["selection"]["validation"][name]
        )
        matrix = np.asarray(values["confusion_matrix"])
        fig, ax = plt.subplots(figsize=(6.3, 5.5), layout="constrained")
        ax.imshow(matrix, cmap="Blues", vmin=0, vmax=max(1, matrix.max()))
        ax.set(
            xticks=range(5),
            yticks=range(5),
            xticklabels=CLASSES,
            yticklabels=CLASSES,
            xlabel="Predicted class",
            ylabel="True class",
            title=f"{name} / {split} (n={values['n']})",
        )
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        for i in range(5):
            for j in range(5):
                ax.text(
                    j,
                    i,
                    str(matrix[i, j]),
                    ha="center",
                    va="center",
                    color="white" if matrix[i, j] > matrix.max() / 2 else "black",
                )
        fig.savefig(args.run / f"{name}-{split}-confusion.svg")
        plt.close(fig)
fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
history = report["history"]
epochs = [r["epoch"] for r in history]
axes[0].plot(epochs, [r["train_loss"] for r in history], marker="o")
axes[0].set(xlabel="Epoch", ylabel="Training cross-entropy", title="ResNet18 training loss")
axes[1].plot(epochs, [r["validation_macro_f1"] for r in history], marker="o", label="Macro F1")
axes[1].plot(epochs, [r["validation_accuracy"] for r in history], marker=".", label="Accuracy")
axes[1].axvline(
    report["selection"]["best_epoch"], color="gray", linestyle=":", label="Selected epoch"
)
axes[1].set(xlabel="Epoch", ylabel="Validation score", ylim=(0, 1.05), title="Validation selection")
axes[1].legend()
fig.savefig(args.run / "learning-curves.svg")
plt.close(fig)
