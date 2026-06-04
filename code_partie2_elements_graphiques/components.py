"""Low-level image primitives used by the graphical reader.

The project statement asks us to avoid high-level rectangle or checkbox
detectors.  This module therefore keeps the building blocks explicit:
thresholding, connected components, simple morphology-friendly geometry and
projection/cluster grouping.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, Union

import numpy as np
from PIL import Image
from scipy import ndimage as ndi


ImageLike = Union[str, Path, Image.Image, np.ndarray]
RelativeRoi = tuple[float, float, float, float]


@dataclass(frozen=True)
class Box:
    """Axis-aligned rectangle in image coordinates."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    @property
    def aspect(self) -> float:
        return self.width / max(1, self.height)

    def inset(self, x_frac: float, y_frac: float | None = None) -> "Box":
        if y_frac is None:
            y_frac = x_frac
        dx = int(round(self.width * x_frac))
        dy = int(round(self.height * y_frac))
        return Box(self.x0 + dx, self.y0 + dy, self.x1 - dx, self.y1 - dy)

    def inflate(self, pixels: int, shape: tuple[int, int] | None = None) -> "Box":
        x0 = self.x0 - pixels
        y0 = self.y0 - pixels
        x1 = self.x1 + pixels
        y1 = self.y1 + pixels
        if shape is not None:
            height, width = shape
            x0 = max(0, x0)
            y0 = max(0, y0)
            x1 = min(width, x1)
            y1 = min(height, y1)
        return Box(x0, y0, x1, y1)


@dataclass(frozen=True)
class Component:
    """Connected component summary after thresholding."""

    box: Box
    area: int

    @property
    def fill_ratio(self) -> float:
        return self.area / max(1, self.box.area)


def load_gray(image: ImageLike) -> np.ndarray:
    """Load an image-like object as an 8-bit grayscale numpy array."""

    if image is None:
        raise ValueError("Invalid image: None")
    if isinstance(image, np.ndarray):
        arr = image
        if arr.size == 0:
            raise ValueError("Invalid image: empty array")
        if arr.ndim == 3:
            arr = np.asarray(Image.fromarray(arr).convert("L"))
        return _sanitize_uint8(arr)
    if isinstance(image, Image.Image):
        if image.width <= 0 or image.height <= 0:
            raise ValueError("Invalid image: empty PIL image")
        return _sanitize_uint8(np.asarray(image.convert("L")))
    return _sanitize_uint8(np.asarray(Image.open(image).convert("L")))


def load_rgb(image: ImageLike) -> Image.Image:
    """Load an image-like object as a PIL RGB image."""

    if image is None:
        raise ValueError("Invalid image: None")
    if isinstance(image, Image.Image):
        if image.width <= 0 or image.height <= 0:
            raise ValueError("Invalid image: empty PIL image")
        return image.convert("RGB")
    if isinstance(image, np.ndarray):
        arr = image
        if arr.size == 0:
            raise ValueError("Invalid image: empty array")
        arr = _sanitize_uint8(arr)
        if arr.ndim == 2:
            return Image.fromarray(arr).convert("RGB")
        return Image.fromarray(arr[..., :3]).convert("RGB")
    return Image.open(image).convert("RGB")


def relative_box(shape: tuple[int, int], roi: RelativeRoi) -> Box:
    """Convert a relative ROI `(x0, y0, x1, y1)` to a pixel `Box`."""

    if len(shape) < 2:
        return Box(0, 0, 0, 0)
    height, width = shape[:2]
    x0 = int(round(roi[0] * width))
    y0 = int(round(roi[1] * height))
    x1 = int(round(roi[2] * width))
    y1 = int(round(roi[3] * height))
    x0 = max(0, min(width, x0))
    x1 = max(0, min(width, x1))
    y0 = max(0, min(height, y0))
    y1 = max(0, min(height, y1))
    return Box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def crop_array(arr: np.ndarray, box: Box) -> np.ndarray:
    if arr is None:
        return np.zeros((0, 0), dtype=np.uint8)
    arr = np.asarray(arr)
    if arr.size == 0 or arr.ndim < 2:
        return np.zeros((0, 0), dtype=np.uint8)
    h, w = arr.shape[:2]
    x0 = max(0, min(w, box.x0))
    x1 = max(0, min(w, box.x1))
    y0 = max(0, min(h, box.y0))
    y1 = max(0, min(h, box.y1))
    return arr[min(y0, y1) : max(y0, y1), min(x0, x1) : max(x0, x1)]


def threshold_dark(arr: np.ndarray, threshold: int = 125) -> np.ndarray:
    """Binary mask of dark ink/paper marks."""

    if arr is None:
        return np.zeros((0, 0), dtype=bool)
    arr = np.asarray(arr)
    if arr.size == 0:
        return np.zeros((0, 0), dtype=bool)
    return arr < threshold


def connected_components(mask: np.ndarray, offset: tuple[int, int] = (0, 0)) -> list[Component]:
    """Return connected components from a binary mask.

    The implementation is the classic connected-component labelling operation;
    it does not use any semantic detector for forms or boxes.
    """

    if mask is None:
        return []
    mask = np.asarray(mask, dtype=bool)
    if mask.size == 0:
        return []
    labels, count = ndi.label(mask)
    slices = ndi.find_objects(labels)
    ox, oy = offset
    comps: list[Component] = []
    for label_id, sl in enumerate(slices, start=1):
        if sl is None:
            continue
        ys, xs = sl
        box = Box(ox + xs.start, oy + ys.start, ox + xs.stop, oy + ys.stop)
        area = int((labels[sl] == label_id).sum())
        comps.append(Component(box=box, area=area))
    return comps


def find_components(
    arr: np.ndarray,
    roi: RelativeRoi | Box | None = None,
    threshold: int = 125,
) -> list[Component]:
    """Threshold a region and return its connected components."""

    if arr is None:
        return []
    arr = np.asarray(arr)
    if arr.size == 0 or arr.ndim < 2:
        return []
    if roi is None:
        box = Box(0, 0, arr.shape[1], arr.shape[0])
    elif isinstance(roi, Box):
        box = roi
    else:
        box = relative_box(arr.shape, roi)
    mask = threshold_dark(crop_array(arr, box), threshold=threshold)
    return connected_components(mask, offset=(box.x0, box.y0))


def find_square_candidates(
    arr: np.ndarray,
    roi: RelativeRoi | Box,
    threshold: int = 125,
    min_side: int | None = None,
    max_side: int | None = None,
    min_fill: float = 0.08,
    max_fill: float = 0.75,
    min_aspect: float = 0.70,
    max_aspect: float = 1.35,
) -> list[Component]:
    """Find square-ish connected components inside a region."""

    height, width = arr.shape
    min_side = min_side if min_side is not None else max(12, int(width * 0.010))
    max_side = max_side if max_side is not None else max(30, int(width * 0.040))
    out: list[Component] = []
    for comp in find_components(arr, roi=roi, threshold=threshold):
        box = comp.box
        if not (min_side <= box.width <= max_side and min_side <= box.height <= max_side):
            continue
        if not (min_aspect <= box.aspect <= max_aspect):
            continue
        if not (min_fill <= comp.fill_ratio <= max_fill):
            continue
        out.append(comp)
    return out


def cluster_positions(values: Iterable[float], tolerance: float) -> list[float]:
    """Cluster sorted scalar positions with a fixed tolerance."""

    sorted_values = sorted(float(v) for v in values if np.isfinite(v))
    clusters: list[list[float]] = []
    for value in sorted_values:
        if not clusters or abs(value - float(np.mean(clusters[-1]))) > tolerance:
            clusters.append([value])
        else:
            clusters[-1].append(value)
    return [float(np.mean(cluster)) for cluster in clusters]


def nearest_index(value: float, centers: Sequence[float]) -> int:
    if not centers:
        raise ValueError("No centers available")
    return min(range(len(centers)), key=lambda i: abs(value - centers[i]))


def inner_dark_score(
    arr: np.ndarray,
    box: Box,
    threshold: int = 145,
    inset: float = 0.28,
) -> float:
    """Ink ratio inside a checkbox, excluding its printed border."""

    inner = box.inset(inset)
    if inner.width <= 0 or inner.height <= 0:
        return 0.0
    region = crop_array(arr, inner)
    if region.size == 0:
        return 0.0
    return float((region < threshold).mean())


def component_fill_score(comp: Component) -> float:
    """Score useful for filled/empty square boxes."""

    return comp.fill_ratio


def choose_regular_window(rows: Sequence[float], expected_rows: int) -> list[float]:
    """Choose the most regularly spaced consecutive row window."""

    rows = list(sorted(rows))
    if len(rows) <= expected_rows:
        return rows
    best: tuple[float, int] | None = None
    for start in range(0, len(rows) - expected_rows + 1):
        window = rows[start : start + expected_rows]
        diffs = np.diff(window)
        mean_step = float(np.mean(diffs)) if len(diffs) else 1.0
        regularity = float(np.std(diffs) / max(1.0, mean_step))
        # Prefer regularity first, then the lower window.  Extra handwritten
        # boxes above a grid usually have fewer columns and are filtered before
        # this step, but this tie-break keeps the behaviour deterministic.
        score = regularity + start * 1e-4
        if best is None or score < best[0]:
            best = (score, start)
    assert best is not None
    return rows[best[1] : best[1] + expected_rows]


def resize_binary(mask: np.ndarray, size: tuple[int, int] = (32, 32)) -> np.ndarray:
    """Resize a binary mask with nearest-neighbour sampling."""

    image = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    image = image.resize(size, Image.Resampling.NEAREST)
    return np.asarray(image) > 0


def _sanitize_uint8(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr)
    if arr.size == 0:
        raise ValueError("Invalid image: empty array")
    arr = np.nan_to_num(arr, nan=255.0, posinf=255.0, neginf=0.0)
    return np.clip(arr, 0, 255).astype(np.uint8)
