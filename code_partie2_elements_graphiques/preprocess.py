"""Basic preprocessing helpers: thresholding, morphology and deskew."""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from .components import ImageLike, load_gray


def otsu_threshold(arr: np.ndarray) -> int:
    """Compute Otsu's threshold from a grayscale image."""

    hist, _ = np.histogram(arr.ravel(), bins=256, range=(0, 256))
    total = arr.size
    sum_total = float(np.dot(np.arange(256), hist))
    sum_background = 0.0
    weight_background = 0.0
    best_var = -1.0
    best_threshold = 127
    for threshold in range(256):
        weight_background += hist[threshold]
        if weight_background == 0:
            continue
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break
        sum_background += threshold * hist[threshold]
        mean_background = sum_background / weight_background
        mean_foreground = (sum_total - sum_background) / weight_foreground
        between = weight_background * weight_foreground * (mean_background - mean_foreground) ** 2
        if between > best_var:
            best_var = between
            best_threshold = threshold
    return int(best_threshold)


def binary_morphology(
    mask: np.ndarray,
    operation: str = "closing",
    size: int = 3,
    iterations: int = 1,
) -> np.ndarray:
    """Apply a small square-structuring-element morphology operation."""

    structure = np.ones((size, size), dtype=bool)
    if operation == "opening":
        return ndi.binary_opening(mask, structure=structure, iterations=iterations)
    if operation == "closing":
        return ndi.binary_closing(mask, structure=structure, iterations=iterations)
    if operation == "erosion":
        return ndi.binary_erosion(mask, structure=structure, iterations=iterations)
    if operation == "dilation":
        return ndi.binary_dilation(mask, structure=structure, iterations=iterations)
    raise ValueError(f"Unknown morphology operation: {operation}")


def estimate_skew_angle(
    image: ImageLike,
    angle_min: float = -4.0,
    angle_max: float = 4.0,
    step: float = 0.25,
) -> float:
    """Estimate page skew by maximizing horizontal projection contrast."""

    arr = load_gray(image)
    threshold = min(160, otsu_threshold(arr))
    mask = arr < threshold
    angles = np.arange(angle_min, angle_max + 1e-9, step)
    best_angle = 0.0
    best_score = -1.0
    for angle in angles:
        rotated = ndi.rotate(mask.astype(float), angle, reshape=False, order=0, cval=0.0)
        projection = rotated.sum(axis=1)
        score = float(np.var(projection))
        if score > best_score:
            best_score = score
            best_angle = float(angle)
    return best_angle


def deskew_image(image: ImageLike, angle: float | None = None) -> Image.Image:
    """Rotate an image to compensate a small skew angle."""

    pil = Image.open(image).convert("RGB") if not isinstance(image, Image.Image) else image.convert("RGB")
    if angle is None:
        angle = estimate_skew_angle(pil)
    return pil.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=(255, 255, 255))
