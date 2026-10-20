"""Camera-only pilot dataset, provenance, grouped splits and reproducible EDA. No training."""

import csv
import fcntl
import hashlib
import html
import io
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import UTC, datetime
from uuid import UUID

import numpy as np
from PIL import Image, ImageFilter

from .banner_conditions import MODES, ROOT, TITLES, source_splits
from .contracts import ConflictError

VERSION = "camera-dataset-v1"


def roi_for_panel(panel, position, heading, width, height, root=ROOT):
    center = json.loads((root / "config/hangar.json").read_text())["inspection_points"][panel][
        "panel_xyz"
    ]
    yaw = heading
    cz = 0.90
    camera = np.array(
        [position["x"] + 0.29 * math.cos(yaw), position["y"] + 0.29 * math.sin(yaw), cz]
    )
    rz = np.array(
        [[math.cos(yaw), -math.sin(yaw), 0], [math.sin(yaw), math.cos(yaw), 0], [0, 0, 1]]
    )
    pitch = -0.14
    ry = np.array(
        [[math.cos(pitch), 0, math.sin(pitch)], [0, 1, 0], [-math.sin(pitch), 0, math.cos(pitch)]]
    )
    rotation = rz @ ry
    focal = width / (2 * math.tan(1.5 / 2))
    points = []
    for x, z in [(-0.56, -0.55), (0.56, -0.55), (0.56, 0.55), (-0.56, 0.55)]:
        local = rotation.T @ (np.array([center[0] + x, center[1] - 0.151, center[2] + z]) - camera)
        if local[0] <= 0.05:
            raise ValueError("Tablica za kamerą")
        points.append(
            [width / 2 - focal * local[1] / local[0], height / 2 - focal * local[2] / local[0]]
        )
    left, top = np.floor(np.min(points, axis=0)).astype(int)
    right, bottom = np.ceil(np.max(points, axis=0)).astype(int)
    if (
        left < 0
        or top < 0
        or right > width
        or bottom > height
        or right - left < 80
        or bottom - top < 80
    ):
        raise ValueError("Niepełny widok tablicy; powtórz obserwację")
    return [int(left), int(top), int(right), int(bottom)]


def collect_observation(report, scene, root=ROOT):
    profile = scene["profile"]
    label = scene["panels"][report["panel"]]
    photos = json.loads((root / "data/vision/photos.json").read_text())
    partitions = source_splits(photos)
    if profile["split"] not in ("train", "validation", "test") or any(
        partitions[p["source_sha256"]] != profile["split"] for p in scene["panels"].values()
    ):
        raise ValueError("Niezgodne grupy zdjęć i część zbioru")
    source = root / "data/inspections" / report["id"] / "raw.jpg"
    directory = root / "data/dataset/samples" / report["id"]
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, directory / "frame.jpg")
    image = Image.open(source).convert("RGB")
    crop_status = "pending_review"
    roi = None
    try:
        if report.get("heading") is None:
            raise ValueError("Brak kierunku kamery")
        roi = roi_for_panel(
            report["panel"], report["position"], report["heading"], image.width, image.height, root
        )
        image.crop(roi).save(directory / "crop.jpg", quality=95)
    except ValueError:
        roi = None
        crop_status = "needs_retake"
    record = {
        "id": report["id"],
        "version": VERSION,
        "created_at": report["created_at"],
        "mission_id": report["mission_id"],
        "panel": report["panel"],
        "sector": report["sector"],
        "scene_id": scene["id"],
        "scene_source_groups": sorted({p["source_sha256"] for p in scene["panels"].values()}),
        "condition": label["condition"],
        "split": profile["split"],
        "source_id": label["source_id"],
        "source_group": label["source_sha256"],
        "source_url": label["source_url"],
        "label_origin": "synthetic_scene_manifest",
        "generator": label["generator"],
        "transform_seed": label["transform_seed"],
        "texture_sha256": label["texture_sha256"],
        "camera_sequence": report["camera_sequence"],
        "camera_stamp_s": report["camera_stamp_s"],
        "position": report["position"],
        "warehouse": report.get("warehouse"),
        "collection_mode": report.get("collection_mode", "nav2_inspection"),
        "acquisition_batch": report.get("acquisition_batch"),
        "pose_source": report.get("pose_source", "navigation_localization"),
        "sim_robot_pose": report.get("sim_robot_pose"),
        "heading": report.get("heading"),
        "width": image.width,
        "height": image.height,
        "frame_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "crop_sha256": hashlib.sha256((directory / "crop.jpg").read_bytes()).hexdigest()
        if roi
        else None,
        "roi_xyxy": roi,
        "roi_method": "geometry_estimate_v1",
        "review_status": crop_status,
        "status": "collected",
        "training_ready": False,
        "split_policy": "source-sha256-v1-2026",
        "source_catalog_sha256": hashlib.sha256(
            json.dumps(photos, sort_keys=True).encode()
        ).hexdigest(),
    }
    temp = directory / "metadata.tmp"
    temp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    temp.replace(directory / "metadata.json")
    return record


def samples(root=ROOT):
    rows = []
    for path in sorted((root / "data/dataset/samples").glob("*/metadata.json")):
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("Dowiązania nie są próbkami zbioru")
        row = json.loads(path.read_text())
        if (
            str(UUID(row["id"])) != path.parent.name
            or row["condition"] not in MODES
            or row["split"] not in ("train", "validation", "test")
        ):
            raise ValueError("Nieprawidłowa próbka zbioru")
        rows.append(row)
    return rows


def revision(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


def list_samples(root=ROOT, status="all", split="all", condition="all", page=1, limit=20):
    rows = samples(root)
    rows = [
        r
        for r in rows
        if (
            status == "all"
            or (status == "pending" and r["review_status"] not in ("approved", "rejected"))
            or r["review_status"] == status
        )
        and (split == "all" or r["split"] == split)
        and (condition == "all" or r["condition"] == condition)
    ]
    rows.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)
    total = len(rows)
    page = min(page, max(1, math.ceil(total / limit)))
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [{**r, "revision": revision(r)} for r in rows[(page - 1) * limit : page * limit]],
    }


def review_sample(sample_id, request, root=ROOT):
    identity = str(UUID(str(sample_id)))
    directory = root / "data/dataset/samples" / identity
    if directory.is_symlink() or not directory.is_dir():
        raise FileNotFoundError("Brak próbki")
    path = directory / "metadata.json"
    if path.is_symlink():
        raise ValueError("Nieprawidłowa próbka")
    with (directory / "review.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        row = json.loads(path.read_text())
        if row["id"] != identity:
            raise ValueError("Nieprawidłowa tożsamość próbki")
        if revision(row) != request.expected_revision:
            raise ConflictError("Próbka została zmieniona. Odśwież widok i sprawdź decyzję.")
        if request.decision == "approved":
            if not row.get("roi_xyxy") or not row.get("crop_sha256"):
                raise ValueError("Brak poprawnego wycinka. Odrzuć próbkę i powtórz obserwację.")
            for name, key in [("frame.jpg", "frame_sha256"), ("crop.jpg", "crop_sha256")]:
                image_path = directory / name
                if image_path.is_symlink() or not image_path.is_file():
                    raise ValueError("Brak oryginalnego obrazu próbki")
                if hashlib.sha256(image_path.read_bytes()).hexdigest() != row[key]:
                    raise ValueError("Obraz zmienił się od zebrania próbki")
                with Image.open(image_path) as image:
                    image.verify()
            photos = json.loads((root / "data/vision/photos.json").read_text())
            plan = source_splits(photos)
            if any(plan.get(g) != row["split"] for g in row["scene_source_groups"]):
                raise ValueError("Grupy źródłowe są niezgodne z częścią zbioru")
        row.setdefault("original_condition", row["condition"])
        row.setdefault("original_label_origin", row["label_origin"])
        stamp = datetime.now(UTC).isoformat()
        row.setdefault("review_history", []).append(
            {
                "at": stamp,
                "actor": "local_operator",
                "previous_revision": request.expected_revision,
                "previous_condition": row["condition"],
                "condition": request.condition,
                "previous_status": row["review_status"],
                "decision": request.decision,
                "note": request.note,
            }
        )
        row.update(
            condition=request.condition,
            review_status=request.decision,
            training_ready=request.decision == "approved",
            reviewed_at=stamp,
            label_origin="human_review",
        )
        temp = directory / "review.tmp"
        temp.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n")
        temp.replace(path)
        return {**row, "revision": revision(row)}


def summarize_rows(rows):
    return {
        "samples": len(rows),
        "conditions": dict(Counter(r["condition"] for r in rows)),
        "splits": dict(Counter(r["split"] for r in rows)),
        "review": dict(Counter(r["review_status"] for r in rows)),
        "training_ready": sum(
            r.get("training_ready", False) and r["review_status"] == "approved" for r in rows
        ),
        "pending_review": sum(r["review_status"] not in ("approved", "rejected") for r in rows),
        "rejected": sum(r["review_status"] == "rejected" for r in rows),
    }


def summary(root=ROOT):
    return summarize_rows(samples(root))


def analyze(root=ROOT):
    directory = root / "data/dataset/reports"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "analysis.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _analyze(root)


def _analyze(root=ROOT):
    rows = samples(root)
    errors = []
    groups = defaultdict(set)
    hashes = defaultdict(list)
    metrics = []
    for row in rows:
        for group in row["scene_source_groups"]:
            groups[group].add(row["split"])
        for name in ["frame_sha256", "crop_sha256"]:
            if row.get(name):
                hashes[(name, row[name])].append(row)
        directory = root / "data/dataset/samples" / row["id"]
        file = directory / ("crop.jpg" if row["crop_sha256"] else "frame.jpg")
        gray = Image.open(file).convert("L")
        values = np.asarray(gray, dtype=float)
        edges = np.asarray(gray.filter(ImageFilter.FIND_EDGES), dtype=float)
        metrics.append(
            {
                "id": row["id"],
                "condition": row["condition"],
                "split": row["split"],
                "brightness": round(float(values.mean()), 2),
                "contrast": round(float(values.std()), 2),
                "edge_variance": round(float(edges.var()), 2),
            }
        )
    errors.extend("source_group:" + g for g, parts in groups.items() if len(parts) > 1)
    duplicates = []
    for (kind, digest), items in hashes.items():
        if len(items) > 1:
            duplicates.append({"kind": kind, "sha256": digest, "ids": [r["id"] for r in items]})
            if len({r["split"] for r in items}) > 1:
                errors.append("cross_split_duplicate:" + digest)
    result = {
        **summarize_rows(rows),
        "version": VERSION,
        "leakage_errors": errors,
        "duplicates": duplicates,
        "measurements": metrics,
        "sample_ids": [r["id"] for r in rows],
        "snapshot_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
        "training_allowed": False,
        "training_policy": "EDA nie uruchamia treningu. Osobny pipeline waliduje zatwierdzony snapshot.",
        "missing_conditions": sorted(
            set(["clean", "cracked", "dirty", "occluded", "missing"])
            - {r["condition"] for r in rows}
        ),
        "missing_splits": sorted({"train", "validation", "test"} - {r["split"] for r in rows}),
        "conditions_by_split": {
            part: dict(
                Counter(
                    r["condition"]
                    for r in rows
                    if r["split"] == part and r["review_status"] != "rejected"
                )
            )
            for part in ("train", "validation", "test")
        },
        "approved_missing_by_split": {
            part: sorted(
                set(MODES)
                - {
                    r["condition"]
                    for r in rows
                    if r["split"] == part
                    and r.get("training_ready")
                    and r["review_status"] == "approved"
                }
            )
            for part in ("train", "validation", "test")
        },
        "notes": [
            "Pilot syntetyczny; wymagany przegląd kadrów i etykiet przed treningiem.",
            "Maski SAM nie są ręcznymi etykietami referencyjnymi.",
        ],
    }
    directory = root / "data/dataset/reports"
    directory.mkdir(parents=True, exist_ok=True)
    temp = directory / "eda.tmp"
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    temp.replace(directory / "eda.json")
    fields = [
        "id",
        "condition",
        "split",
        "panel",
        "source_group",
        "scene_id",
        "label_origin",
        "review_status",
        "training_ready",
        "original_condition",
        "reviewed_at",
        "collection_mode",
        "acquisition_batch",
        "pose_source",
        "frame_sha256",
        "crop_sha256",
    ]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows({k: row.get(k) for k in fields} for row in rows)
    temp = directory / "samples.tmp"
    temp.write_text(stream.getvalue())
    temp.replace(directory / "samples.csv")
    catalog_path = root / "data/vision/photos.json"
    photos = json.loads(catalog_path.read_text()) if catalog_path.exists() else []
    plan = {"policy": "source-sha256-v1-2026", "groups": source_splits(photos) if photos else {}}
    temp = directory / "splits.tmp"
    temp.write_text(json.dumps(plan, indent=2))
    temp.replace(directory / "splits.json")
    entries = "".join(
        f"<article><h2>{html.escape(r['panel'])}: {html.escape(TITLES[r['condition']])} / {html.escape(r['split'])}</h2>"
        f"<p>{html.escape(r['review_status'])} · {html.escape(r['label_origin'])}, nie wynik modelu</p>"
        f'<p>Pełna klatka kamery</p><img loading="lazy" src="/api/dataset/{r["id"]}/frame.jpg" alt="Pełna klatka do weryfikacji">'
        + (
            f'<p>Przybliżony wycinek tablicy</p><img loading="lazy" src="/api/dataset/{r["id"]}/crop.jpg" alt="Wycinek tablicy do weryfikacji">'
            if r["crop_sha256"]
            else "<p>Wymagane powtórzenie obserwacji.</p>"
        )
        + "</article>"
        for r in rows[:100]
    )
    quality_table = (
        '<div class="dataset-table"><table><thead><tr><th>Próbka</th><th>Jasność</th><th>Kontrast</th><th>Wariancja krawędzi</th></tr></thead><tbody>'
        + "".join(
            f"<tr><td>{html.escape(m['id'][:8])}</td><td>{m['brightness']}</td><td>{m['contrast']}</td><td>{m['edge_variance']}</td></tr>"
            for m in metrics
        )
        + "</tbody></table></div>"
    )
    page = (
        '<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EDA zbioru RoboInspect</title><link rel="stylesheet" href="/style.css"><main class="dataset-report"><a href="/control">Panel sterowania</a><h1>Dane i EDA</h1><p><a href="/api/dataset-export/eda.json">EDA JSON</a> · <a href="/api/dataset-export/samples.csv">Manifest CSV</a> · <a href="/api/dataset-export/splits.json">Podział źródeł</a></p><p>Próbki: '
        + str(len(rows))
        + " · błędy podziału: "
        + str(len(errors))
        + ". Status przeglądu widoczny poniżej. EDA nie uruchamia treningu. <a href='/classifier'>Zobacz wyniki klasyfikatora</a>.</p><p><a href='/dataset/review'>Przejrzyj próbki</a></p><pre>"
        + html.escape(
            json.dumps(
                {
                    k: result[k]
                    for k in [
                        "conditions",
                        "splits",
                        "review",
                        "missing_conditions",
                        "missing_splits",
                        "conditions_by_split",
                        "approved_missing_by_split",
                        "leakage_errors",
                    ]
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        + "</pre>"
        + quality_table
        + entries
        + "</main></html>"
    )
    temp = directory / "report.tmp"
    temp.write_text(page)
    temp.replace(directory / "report.html")
    try:
        from mlflow.tracking import MlflowClient

        client = MlflowClient(tracking_uri=f"sqlite:///{root / 'data/mlflow.db'}")
        exp = client.get_experiment_by_name("roboinspect-dataset")
        eid = (
            exp.experiment_id
            if exp
            else client.create_experiment(
                "roboinspect-dataset",
                artifact_location=(root / "data/mlflow-artifacts/dataset").as_uri(),
            )
        )
        run = client.create_run(
            eid, tags={"stage": "data-eda", "snapshot": result["snapshot_sha256"]}
        )
        for k, v in {
            "samples": len(rows),
            "source_groups": len(groups),
            "leakage_errors": len(errors),
            "duplicate_groups": len(duplicates),
            "training_ready": result["training_ready"],
        }.items():
            client.log_metric(run.info.run_id, k, v)
        client.log_dict(run.info.run_id, result, "eda.json")
        client.log_artifact(run.info.run_id, str(directory / "samples.csv"))
        client.log_artifact(run.info.run_id, str(directory / "splits.json"))
        client.set_terminated(run.info.run_id)
        result["run_id"] = run.info.run_id
    except Exception:
        result["tracking_error"] = "Nie zapisano pomiarów EDA w MLflow; raport lokalny zachowany"
    return result
