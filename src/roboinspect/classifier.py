"""Versioned, approved camera datasets and small classifier math. No robot control."""

import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from .banner_conditions import MODES, ROOT, source_splits
from .dataset import samples

CLASSES = list(MODES)
SPLITS = ("train", "validation", "test")
PREPROCESS = {
    "version": "letterbox-rgb-224-v1",
    "size": 224,
    "padding_rgb": [128, 128, 128],
    "mean": [0.485, 0.456, 0.406],
    "std": [0.229, 0.224, 0.225],
}


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_hash(manifest):
    body = {k: v for k, v in manifest.items() if k != "snapshot_id"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def freeze_dataset(root=ROOT):
    rows = [
        r for r in samples(root) if r["review_status"] == "approved" and r.get("training_ready")
    ]
    if not rows:
        raise ValueError("Brak zatwierdzonych próbek")
    plan = source_splits(json.loads((root / "data/vision/photos.json").read_text()))
    groups = defaultdict(set)
    hashes = defaultdict(set)
    records = []
    for row in sorted(rows, key=lambda r: r["id"]):
        source = root / "data/dataset/samples" / row["id"]
        if not row.get("crop_sha256") or not row.get("roi_xyxy"):
            raise ValueError("Brak wycinka: " + row["id"])
        for name, key in [("frame.jpg", "frame_sha256"), ("crop.jpg", "crop_sha256")]:
            path = source / name
            if path.is_symlink() or not path.is_file() or digest_file(path) != row[key]:
                raise ValueError("Zmieniony lub brakujący obraz: " + row["id"])
            with Image.open(path) as image:
                image.verify()
            hashes[(key, row[key])].add(row["split"])
        if row["source_group"] not in row["scene_source_groups"]:
            raise ValueError("Niepełne pochodzenie")
        for group in row["scene_source_groups"]:
            if plan.get(group) != row["split"]:
                raise ValueError("Niezgodny podział źródeł")
            groups[group].add(row["split"])
        records.append(
            {
                **row,
                "class_index": CLASSES.index(row["condition"]),
                "image": "images/" + row["id"] + ".jpg",
            }
        )
    if any(len(v) > 1 for v in groups.values()) or any(len(v) > 1 for v in hashes.values()):
        raise ValueError("Przeciek pomiędzy częściami zbioru")
    counts = {
        part: dict(Counter(r["condition"] for r in records if r["split"] == part))
        for part in SPLITS
    }
    if any(set(counts[part]) != set(CLASSES) for part in SPLITS):
        raise ValueError("Każda część zatwierdzonego zbioru musi zawierać wszystkie klasy")
    manifest = {
        "version": "classifier-snapshot-v1",
        "classes": CLASSES,
        "preprocess": PREPROCESS,
        "counts": counts,
        "source_partition": plan,
        "records": records,
        "limitations": [
            "Synthetic variants of 24 source photos; observations are correlated.",
            "Pilot review; earlier user bulk approvals are retained in review_history.",
            "No claim of real-world defect performance.",
        ],
    }
    manifest["snapshot_id"] = frozen_hash(manifest)
    parent = root / "data/classifier/snapshots"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / manifest["snapshot_id"]
    if target.exists():
        verify_snapshot(target)
        return target
    temporary = parent / ("building-" + str(uuid4()))
    (temporary / "images").mkdir(parents=True)
    try:
        for row in records:
            shutil.copyfile(
                root / "data/dataset/samples" / row["id"] / "crop.jpg", temporary / row["image"]
            )
            if digest_file(temporary / row["image"]) != row["crop_sha256"]:
                raise ValueError("Obraz zmieniony podczas kopiowania")
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        )
        temporary.rename(target)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    verify_snapshot(target)
    return target


def verify_snapshot(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        manifest["snapshot_id"] != frozen_hash(manifest)
        or manifest["classes"] != CLASSES
        or manifest["preprocess"] != PREPROCESS
    ):
        raise ValueError("Niezgodny manifest snapshotu")
    counts = {part: Counter() for part in SPLITS}
    groups = defaultdict(set)
    seen = set()
    hashes = defaultdict(set)
    for row in manifest["records"]:
        identity = str(UUID(row["id"]))
        if (
            identity in seen
            or row["split"] not in SPLITS
            or row["class_index"] != CLASSES.index(row["condition"])
        ):
            raise ValueError("Nieprawidłowy rekord snapshotu")
        seen.add(identity)
        if row["review_status"] != "approved" or not row.get("training_ready"):
            raise ValueError("Niezatwierdzona próbka w snapshocie")
        if row["image"] != "images/" + identity + ".jpg":
            raise ValueError("Nieprawidłowa ścieżka obrazu")
        path = directory / row["image"]
        if path.is_symlink() or not path.is_file() or digest_file(path) != row["crop_sha256"]:
            raise ValueError("Zmieniony obraz snapshotu")
        counts[row["split"]][row["condition"]] += 1
        for group in row["scene_source_groups"]:
            if manifest["source_partition"].get(group) != row["split"]:
                raise ValueError("Niezgodne źródło snapshotu")
            groups[group].add(row["split"])
        for key in ("frame_sha256", "crop_sha256"):
            hashes[(key, row[key])].add(row["split"])
    if any(len(v) > 1 for v in groups.values()) or any(len(v) > 1 for v in hashes.values()):
        raise ValueError("Przeciek snapshotu")
    if {k: dict(v) for k, v in counts.items()} != manifest["counts"] or any(
        set(v) != set(CLASSES) for v in counts.values()
    ):
        raise ValueError("Niepełny zbiór klas")
    return manifest


def preprocess_image(image):
    """Same full-board letterbox in training and inference; no center crop."""
    return ImageOps.pad(
        image.convert("RGB"), (224, 224), method=Image.Resampling.BILINEAR, color=(128, 128, 128)
    )


def image_features(image):
    image = preprocess_image(image).resize((64, 64), Image.Resampling.BILINEAR)
    rgb = np.asarray(image, dtype=float) / 255
    gray = np.asarray(image.convert("L"), dtype=float) / 255
    edges = np.asarray(image.convert("L").filter(ImageFilter.FIND_EDGES), dtype=float) / 255
    features = []
    for channel in range(3):
        features.extend(
            np.histogram(rgb[:, :, channel], bins=12, range=(0, 1), density=False)[0] / 4096
        )
        features.extend([rgb[:, :, channel].mean(), rgb[:, :, channel].std()])
    for y in range(0, 64, 16):
        for x in range(0, 64, 16):
            patch = gray[y : y + 16, x : x + 16]
            edge = edges[y : y + 16, x : x + 16]
            features.extend([patch.mean(), patch.std(), edge.mean(), edge.std()])
    return np.asarray(features, dtype=np.float64)


def fit_ridge(features, labels, alpha):
    mean = features.mean(axis=0)
    std = features.std(axis=0)
    std[std < 1e-8] = 1
    x = np.column_stack([(features - mean) / std, np.ones(len(features))])
    y = np.eye(len(CLASSES))[labels]
    penalty = np.eye(x.shape[1]) * alpha
    penalty[-1, -1] = 0
    weights = np.linalg.solve(x.T @ x + penalty, x.T @ y)
    return {"mean": mean, "std": std, "weights": weights, "alpha": np.asarray(alpha)}


def ridge_scores(model, features):
    x = np.column_stack([(features - model["mean"]) / model["std"], np.ones(len(features))])
    return x @ model["weights"]


def classification_metrics(labels, predictions):
    labels = np.asarray(labels, dtype=int)
    predictions = np.asarray(predictions, dtype=int)
    if not len(labels) or len(labels) != len(predictions):
        raise ValueError("Brak zgodnych predykcji")
    if (
        np.any(labels < 0)
        or np.any(labels >= len(CLASSES))
        or np.any(predictions < 0)
        or np.any(predictions >= len(CLASSES))
    ):
        raise ValueError("Nieznana klasa")
    matrix = np.zeros((len(CLASSES), len(CLASSES)), dtype=int)
    np.add.at(matrix, (labels, predictions), 1)
    per = {}
    for i, name in enumerate(CLASSES):
        tp = int(matrix[i, i])
        support = int(matrix[i].sum())
        predicted = int(matrix[:, i].sum())
        precision = tp / predicted if predicted else 0
        recall = tp / support if support else 0
        per[name] = {
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
            "support": support,
        }
    return {
        "accuracy": float(np.trace(matrix) / len(labels)),
        "macro_f1": float(np.mean([v["f1"] for v in per.values()])),
        "balanced_accuracy": float(np.mean([v["recall"] for v in per.values()])),
        "per_class": per,
        "confusion_matrix": matrix.tolist(),
        "n": len(labels),
    }
