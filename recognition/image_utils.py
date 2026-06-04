from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple, Union

import cv2
import numpy as np


ImageInput = Union[str, Path, np.ndarray]


def load_gray(image: ImageInput) -> np.ndarray:
    """Load a path or array as uint8 grayscale."""
    if image is None:
        raise ValueError("Cannot read image: input is None")
    if isinstance(image, (str, Path)):
        arr = _imread_unicode(image)
        if arr is None:
            raise ValueError(f"Cannot read image: {image}")
        return _sanitize_gray(arr)
    arr = np.asarray(image)
    if arr.size == 0:
        raise ValueError("Cannot read image: input array is empty")
    if arr.ndim == 3:
        arr = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    return _sanitize_gray(arr)


def binarize_ink(gray: np.ndarray, invert: bool = True) -> np.ndarray:
    """Return a binary image where foreground ink is 1."""
    gray = load_gray(gray)
    if gray.size == 0:
        return np.zeros((0, 0), dtype=np.uint8)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if invert:
        th = 255 - th
    return (th > 0).astype(np.uint8)


def crop_foreground(binary: np.ndarray, pad: int = 8) -> np.ndarray:
    """Crop around foreground pixels. If no foreground exists, return input."""
    if binary is None:
        return np.zeros((0, 0), dtype=np.uint8)
    binary = np.asarray(binary)
    if binary.size == 0:
        return np.zeros((0, 0), dtype=np.uint8)
    ys, xs = np.where(binary > 0)
    if len(xs) == 0 or len(ys) == 0:
        return binary
    y0, y1 = max(0, ys.min() - pad), min(binary.shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(binary.shape[1], xs.max() + pad + 1)
    return binary[y0:y1, x0:x1]


def resize_keep_ratio(binary: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    """Resize binary foreground to fit size=(width, height), preserving ratio."""
    target_w, target_h = size
    if binary is None:
        return np.zeros((target_h, target_w), dtype=np.uint8)
    binary = np.asarray(binary)
    if binary.size == 0:
        return np.zeros((target_h, target_w), dtype=np.uint8)
    h, w = binary.shape[:2]
    if h == 0 or w == 0:
        return np.zeros((target_h, target_w), dtype=np.uint8)
    scale = min(target_w / w, target_h / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(binary, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((target_h, target_w), dtype=np.uint8)
    y0 = (target_h - new_h) // 2
    x0 = (target_w - new_w) // 2
    canvas[y0 : y0 + new_h, x0 : x0 + new_w] = (resized > 0).astype(np.uint8)
    return canvas


def normalize_vector(vector: Iterable[float], eps: float = 1e-8) -> np.ndarray:
    arr = np.asarray(list(vector), dtype=np.float32)
    mean = float(arr.mean()) if arr.size else 0.0
    std = float(arr.std()) if arr.size else 1.0
    return (arr - mean) / (std + eps)


def split_connected_components(binary: np.ndarray, min_area: int = 12) -> list[np.ndarray]:
    """Split foreground components from left to right."""
    if binary is None:
        return []
    binary = np.asarray(binary)
    if binary.size == 0:
        return []
    num, labels, stats, _ = cv2.connectedComponentsWithStats(binary.astype(np.uint8), 8)
    boxes = []
    for idx in range(1, num):
        x, y, w, h, area = stats[idx]
        if area >= min_area and w > 1 and h > 3:
            boxes.append((x, y, w, h))
    boxes.sort(key=lambda b: b[0])
    chars = []
    for x, y, w, h in boxes:
        chars.append(binary[y : y + h, x : x + w])
    return chars


def _sanitize_gray(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr)
    if arr.size == 0:
        raise ValueError("Cannot read image: grayscale array is empty")
    arr = np.nan_to_num(arr, nan=255.0, posinf=255.0, neginf=0.0)
    return np.clip(arr, 0, 255).astype(np.uint8)


def _imread_unicode(path: str | Path) -> np.ndarray | None:
    """Read an image from a path that may contain non-ASCII characters.

    OpenCV's `imread` can fail on Windows paths containing characters such as
    Chinese usernames.  Reading bytes with numpy and decoding them keeps the
    recognition pipeline independent from the current filesystem encoding.
    """

    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
