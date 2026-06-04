"""Cryptogram extraction and comparison."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .components import (
    Box,
    Component,
    ImageLike,
    crop_array,
    find_components,
    load_gray,
    resize_binary,
)


CRYPTOGRAM_ROI = (0.10, 0.80, 0.45, 0.99)


@dataclass
class CryptogramResult:
    box: Box
    crop: Image.Image
    pattern: np.ndarray


@dataclass
class CryptogramValidation:
    valid: bool
    distances: list[float]
    reference: CryptogramResult | None
    cryptograms: list[CryptogramResult]


def extract_cryptogram(image: ImageLike) -> CryptogramResult | None:
    """Find and crop the small cryptogram printed near the bottom of a page."""

    arr = load_gray(image)
    comps = find_components(arr, roi=CRYPTOGRAM_ROI, threshold=120)
    candidates: list[Component] = []
    for comp in comps:
        box = comp.box
        if not (50 <= box.width <= 260 and 50 <= box.height <= 260):
            continue
        if not (0.65 <= box.aspect <= 1.35):
            continue
        if comp.area < 1000:
            continue
        candidates.append(comp)
    if not candidates:
        return None

    comp = max(candidates, key=lambda c: c.area)
    box = comp.box.inflate(8, shape=arr.shape)
    crop_arr = crop_array(arr, box)
    crop_img = Image.fromarray(crop_arr).convert("L")
    pattern = cryptogram_pattern(crop_arr)
    return CryptogramResult(box=box, crop=crop_img, pattern=pattern)


def cryptogram_pattern(crop_arr: np.ndarray, size: tuple[int, int] = (32, 32)) -> np.ndarray:
    """Create a normalized binary pattern for comparison."""

    if crop_arr.size == 0:
        return np.zeros(size, dtype=bool)
    threshold = min(150, int(np.percentile(crop_arr, 35)))
    mask = crop_arr < threshold
    return resize_binary(mask, size=size)


def cryptogram_distance(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        raise ValueError("Cryptogram patterns must have the same shape")
    return float(np.mean(a != b))


def validate_cryptograms(
    pages: list[ImageLike],
    threshold: float = 0.18,
) -> CryptogramValidation:
    """Validate that all page cryptograms match the first detected one."""

    cryptograms = [c for page in pages if (c := extract_cryptogram(page)) is not None]
    if not cryptograms:
        return CryptogramValidation(False, [], None, [])
    reference = cryptograms[0]
    distances = [cryptogram_distance(reference.pattern, c.pattern) for c in cryptograms[1:]]
    valid = len(cryptograms) == len(pages) and all(d <= threshold for d in distances)
    return CryptogramValidation(valid, distances, reference, cryptograms)
