"""SAM is prompted only with YOLO boxes from the exact same raw camera image."""

import base64
import gc
import hashlib
import io
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw
from ultralytics.models.sam import SAM2Predictor

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/sam.json").read_text())
COLORS = [
    (66, 211, 146),
    (255, 185, 60),
    (83, 171, 255),
    (221, 111, 236),
    (255, 112, 112),
    (84, 220, 216),
]


def encoded(picture, fmt):
    buffer = io.BytesIO()
    picture.save(buffer, format=fmt)
    return base64.b64encode(buffer.getvalue()).decode()


class Segmenter:
    def __init__(self, device):
        self.device = device
        self.predictor = None
        weights = ROOT / "data/vision" / CONFIG["weights"]
        self.available = (
            weights.is_file()
            and hashlib.sha256(weights.read_bytes()).hexdigest() == CONFIG["sha256"]
        )

    @torch.inference_mode()
    def run(self, picture, detections):
        started = time.monotonic()
        meta = dict(
            model=CONFIG["model"],
            weights_sha256=CONFIG["sha256"],
            device="cuda:0" if self.device == 0 else "cpu",
            status="unavailable",
            masks=[],
            seconds=0.0,
            message="Przygotuj model SAM",
            gpu_allocated_mib=0.0,
            gpu_peak_allocated_mib=0.0,
        )
        if not self.available:
            return {"segmentation": meta}
        if not detections:
            meta.update(status="no_detections", message="Brak ramek YOLO, nie uruchomiono SAM")
            return {"segmentation": meta}
        if self.device == 0:
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        try:
            if self.predictor is None:
                self.predictor = SAM2Predictor(
                    overrides=dict(
                        model=str(ROOT / "data/vision" / CONFIG["weights"]),
                        task="segment",
                        mode="predict",
                        imgsz=CONFIG["image_size"],
                        device=self.device,
                        conf=0.0,
                        verbose=False,
                        save=False,
                        half=False,
                    )
                )
            # numpy sources in Ultralytics use BGR. Cache one encoder result per capture.
            self.predictor.set_image(np.asarray(picture)[:, :, ::-1].copy())
            masks = np.zeros((len(detections), picture.height, picture.width), dtype=bool)
            scores = {}
            for offset in range(0, len(detections), CONFIG["prompt_batch"]):
                batch = detections[offset : offset + CONFIG["prompt_batch"]]
                result = self.predictor(bboxes=[d["xyxy"] for d in batch])[0]
                if result.masks is not None:
                    for mask, box in zip(result.masks.data, result.boxes):
                        index = offset + int(box.cls.item())
                        if index >= offset + len(batch):
                            raise ValueError("Mask prompt association mismatch")
                        masks[index] = mask.cpu().numpy().astype(bool)
                        scores[index] = float(box.conf.item())
            if self.device == 0:
                torch.cuda.synchronize()
            meta.update(
                seconds=round(time.monotonic() - started, 4),
                gpu_allocated_mib=round(torch.cuda.memory_allocated() / 1024**2, 1)
                if self.device == 0
                else 0,
                gpu_peak_allocated_mib=round(torch.cuda.max_memory_allocated() / 1024**2, 1)
                if self.device == 0
                else 0,
            )
            overlay = np.array(picture).copy()
            index_mask = np.zeros((picture.height, picture.width), dtype=np.uint8)
            for index, (mask, detection) in enumerate(zip(masks, detections)):
                area = int(mask.sum())
                if not area:
                    continue
                color = COLORS[index % len(COLORS)]
                # First (higher YOLO confidence) owns overlap in the preview; packed masks preserve all overlaps.
                visible = mask & (index_mask == 0)
                overlay[visible] = (
                    overlay[visible] * (1 - CONFIG["alpha"]) + np.array(color) * CONFIG["alpha"]
                ).astype(np.uint8)
                index_mask[visible] = index + 1
                contours, _ = cv2.findContours(
                    mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                cv2.drawContours(overlay, contours, -1, color, 2)
                meta["masks"].append(
                    dict(
                        detection_index=index + 1,
                        pixels=area,
                        image_fraction=round(area / (picture.width * picture.height), 6),
                        predicted_iou=round(scores[index], 4),
                        color=list(color),
                    )
                )
            meta.update(
                status="complete" if len(meta["masks"]) == len(detections) else "partial",
                message="Maski z ramek YOLO; wynik nie jest oceną jakości względem etykiet",
            )
            image = Image.fromarray(overlay)
            draw = ImageDraw.Draw(image)
            for index, d in enumerate(detections):
                color = COLORS[index % len(COLORS)]
                draw.rectangle(d["xyxy"], outline=color, width=2)
                draw.text(
                    (d["xyxy"][0] + 3, d["xyxy"][1] + 3),
                    f"{d['label']} {d['instance']} {d['confidence']:.0%}",
                    fill=color,
                    stroke_width=1,
                    stroke_fill="black",
                )
            buffer = io.BytesIO()
            np.savez_compressed(buffer, packed=np.packbits(masks, axis=2))
            return {
                "segmentation": meta,
                "segmented_jpeg": encoded(image, "JPEG"),
                "mask_png": encoded(Image.fromarray(index_mask), "PNG"),
                "masks_npz": base64.b64encode(buffer.getvalue()).decode(),
            }
        except Exception as exc:
            meta.update(
                status="error",
                message="Segmentacja nie powiodła się: " + type(exc).__name__,
                masks=[],
                seconds=round(time.monotonic() - started, 4),
            )
            # A SAM failure must not take the existing YOLO worker down.
            self.predictor = None
            gc.collect()
            if self.device == 0:
                torch.cuda.empty_cache()
            return {"segmentation": meta}
        finally:
            if self.predictor is not None:
                self.predictor.reset_image()
