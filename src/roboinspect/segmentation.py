"""Typed segmentation evidence and bounded lossless mask artifacts."""

import io
import zipfile
from typing import Literal

import numpy as np
from PIL import Image
from pydantic import Field

from .contracts import StrictModel


class ObjectMask(StrictModel):
    detection_index: int = Field(ge=1, le=50)
    pixels: int = Field(ge=1)
    image_fraction: float = Field(gt=0, le=1)
    predicted_iou: float = Field(ge=0, le=10)
    color: tuple[int, int, int]


class SegmentationResult(StrictModel):
    model: str
    weights_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    device: str
    status: Literal["complete", "partial", "no_detections", "unavailable", "error"]
    masks: list[ObjectMask] = Field(default_factory=list, max_length=50)
    seconds: float = Field(ge=0, le=120)
    message: str = Field(max_length=300)
    gpu_allocated_mib: float = Field(ge=0)
    gpu_peak_allocated_mib: float = Field(ge=0)


def validate_artifacts(overlay, index_png, packed_npz, width, height, count, masks):
    """Bound archive expansion before np.load; preserve separate overlapping masks."""
    if count * width * height > 64_000_000:
        raise ValueError("Zbyt duży zestaw masek")
    for data in [overlay, index_png]:
        with Image.open(io.BytesIO(data)) as image:
            if image.size != (width, height):
                raise ValueError("Niezgodny rozmiar maski lub nakładki")
            image.load()
    with Image.open(io.BytesIO(index_png)) as image:
        labels = np.asarray(image)
        if labels.ndim != 2 or labels.max(initial=0) > count:
            raise ValueError("Niezgodne identyfikatory masek")
    with zipfile.ZipFile(io.BytesIO(packed_npz)) as archive:
        if archive.namelist() != ["packed.npy"]:
            raise ValueError("Nieznane dane w archiwum masek")
        if archive.infolist()[0].file_size > count * height * ((width + 7) // 8) + 1024:
            raise ValueError("Zbyt duże archiwum masek")
    with np.load(io.BytesIO(packed_npz), allow_pickle=False) as archive:
        packed = archive["packed"]
        if packed.dtype != np.uint8 or packed.shape != (count, height, (width + 7) // 8):
            raise ValueError("Niezgodny kształt masek")
        actual = np.unpackbits(packed, axis=2, count=width)
    observed = {i + 1: int(mask.sum()) for i, mask in enumerate(actual) if mask.any()}
    if observed != {m["detection_index"]: m["pixels"] for m in masks}:
        raise ValueError("Niezgodne pola powierzchni masek")
    for index in range(1, count + 1):
        if np.any((labels == index) & ~actual[index - 1].astype(bool)):
            raise ValueError("Identyfikator poza maską obiektu")
