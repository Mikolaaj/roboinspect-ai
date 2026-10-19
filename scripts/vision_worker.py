#!/usr/bin/env python3
"""Local GPU detector consumes only robot camera frames; never reads banner assignments."""

import argparse
import base64
import hashlib
import io
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, ConfigDict
from ultralytics import YOLO
from sam_segmenter import Segmenter

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--operator-port", type=int, default=8765)
parser.add_argument("--port", type=int, default=8766)
args = parser.parse_args()
torch.set_num_threads(2)

weights = ROOT / "data/vision/yolo11s.pt"
if (
    hashlib.sha256(weights.read_bytes()).hexdigest()
    != "85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5"
):
    raise RuntimeError("Niezgodna suma kontrolna modelu YOLO11s")
model = YOLO(str(ROOT / "data/vision/yolo11s.pt"))
device = 0 if torch.cuda.is_available() else "cpu"
segmenter = Segmenter(device)
lock = threading.Lock()
state_lock = threading.Lock()
stop = threading.Event()
latest = {
    "ready": False,
    "model": "YOLO11s",
    "device": "cuda:0" if device == 0 else "cpu",
    "message": "Oczekiwanie na kamerę",
}
jpeg = None
base = f"http://127.0.0.1:{args.operator_port}"
token = os.environ["ROBOINSPECT_RUNTIME_TOKEN"]


def predict(data, size, segment=False):
    picture = Image.open(io.BytesIO(data)).convert("RGB")
    started = time.monotonic()
    with lock:
        result = model.predict(
            picture,
            imgsz=size,
            conf=0.30,
            iou=0.5,
            device=device,
            half=device == 0,
            verbose=False,
            max_det=50,
        )[0]
    boxes = []
    counts = {}
    for b in result.boxes:
        label = result.names[int(b.cls.item())]
        number = counts.get(label, 0) + 1
        counts[label] = number
        boxes.append(
            {
                "label": label,
                "instance": number,
                "confidence": round(float(b.conf.item()), 4),
                "xyxy": [round(float(v), 1) for v in b.xyxy[0].tolist()],
            }
        )
    annotated = Image.fromarray(result.plot()[:, :, ::-1])
    output = io.BytesIO()
    annotated.save(output, format="JPEG", quality=90)
    detection_seconds = round(time.monotonic() - started, 3)
    segmentation = {}
    if segment:
        with lock:
            segmentation = segmenter.run(picture, boxes)
    return {
        **segmentation,
        "detections": boxes,
        "counts": counts,
        "total": len(boxes),
        "width": picture.width,
        "height": picture.height,
        "inference_seconds": detection_seconds,
        "model": "YOLO11s",
        "device": "cuda:0" if device == 0 else "cpu",
    }, output.getvalue()


def camera(client):
    status = client.get(base + "/api/status")
    status.raise_for_status()
    s = status.json()
    cam = s.get("cameras", {}).get("fpv", {})
    if s.get("transitioning") or not cam or cam.get("age_s", 99) > 2:
        raise RuntimeError("Oczekiwanie na aktualną kamerę robota")
    r = client.get(base + "/api/frame/fpv.jpg")
    r.raise_for_status()
    return r.content, s, cam


def loop():
    global jpeg
    with httpx.Client(timeout=4, trust_env=False) as client:
        while not stop.is_set():
            try:
                data, s, cam = camera(client)
                result, image = predict(data, 640)
                result.update(
                    ready=True,
                    at=time.time(),
                    camera_sequence=cam["sequence"],
                    camera_stamp_s=cam["stamp_s"],
                    warehouse=s.get("warehouse"),
                    message="Detekcja z kamery robota",
                )
                with state_lock:
                    latest.clear()
                    latest.update(result)
                    jpeg = image
            except Exception as exc:
                with state_lock:
                    latest.update(ready=False, message=str(exc)[:180])
            stop.wait(0.15)


@asynccontextmanager
async def lifespan(app):
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    yield
    stop.set()
    thread.join(timeout=5)


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def protect(request, call_next):
    import secrets

    if not secrets.compare_digest(request.headers.get("x-runtime-token", ""), token):
        return Response(status_code=403)
    return await call_next(request)


class Capture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    panel: str


@app.get("/latest")
def current():
    with state_lock:
        return dict(
            latest,
            sam={"available": segmenter.available, "model": "SAM 2.1 Tiny", "mode": "inspection"},
        )


@app.get("/frame.jpg")
def frame():
    with state_lock:
        if jpeg is None or time.time() - latest.get("at", 0) > 4:
            raise HTTPException(503, "Oczekiwanie na detektor")
        return Response(
            jpeg,
            media_type="image/jpeg",
            headers={"X-Frame-Sequence": str(latest.get("camera_sequence", 0))},
        )


@app.post("/capture")
def capture(body: Capture):
    if body.panel not in ["P1", "P2", "P3", "P4", "P5"]:
        raise HTTPException(422, "Nieznana tablica")
    with httpx.Client(timeout=5, trust_env=False) as client:
        data, s, cam = camera(client)
        velocity = s.get("velocity", {})
        if abs(velocity.get("linear", 1)) > 0.02 or abs(velocity.get("angular", 1)) > 0.02:
            raise HTTPException(409, "Robot nie jest zatrzymany")
        import json
        import math

        goals = json.loads((ROOT / "config/navigation-goals.json").read_text())["poses"]
        point = goals[body.panel]
        pose = s.get("map_position") or {}
        if not pose or math.hypot(pose["x"] - point[0], pose["y"] - point[1]) > 0.55:
            raise HTTPException(409, "Robot nie znajduje się przy wskazanej tablicy")
        heading = s.get("map_heading")
        if (
            heading is None
            or abs(math.atan2(math.sin(heading - point[2]), math.cos(heading - point[2]))) > 0.35
        ):
            raise HTTPException(409, "Robot nie patrzy w kierunku wskazanej tablicy")
        result, image = predict(data, 960, segment=True)
    result.update(
        raw_jpeg=base64.b64encode(data).decode(),
        annotated_jpeg=base64.b64encode(image).decode(),
        camera_stamp_s=cam["stamp_s"],
        camera_sequence=cam["sequence"],
        warehouse=s.get("warehouse"),
        position=s.get("map_position"),
    )
    return result


uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
