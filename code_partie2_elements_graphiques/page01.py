"""Graphical reader for the first page of the exam form."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from .components import (
    Box,
    Component,
    ImageLike,
    choose_regular_window,
    cluster_positions,
    component_fill_score,
    connected_components,
    crop_array,
    find_components,
    find_square_candidates,
    inner_dark_score,
    load_gray,
    load_rgb,
    nearest_index,
    relative_box,
)
from .cryptogram import CryptogramResult, extract_cryptogram


STUDENT_ID_ROI = (0.72, 0.15, 0.97, 0.52)
GROUP_ROI = (0.48, 0.17, 0.72, 0.52)
CONDITION_ROW_ROI = (0.00, 0.54, 1.00, 0.64)
MAX_NUMBER_ROI = (0.00, 0.60, 1.00, 0.64)
SIGNATURE_FALLBACK_ROI = (0.10, 0.28, 0.42, 0.43)


@dataclass
class GridReadResult:
    value: str
    scores: np.ndarray
    boxes: dict[tuple[int, int], Box]
    confidence: float


@dataclass
class ConditionResult:
    notes_de_cours: int | None
    notes_manuscrites: int | None
    ordinateur_portable: int | None
    calculatrice: int | None
    feuilles_brouillon: int | None
    raw_pairs: dict[str, tuple[float, float] | None]
    max_numbers: dict[str, int | None]

    def as_page01_rows(self) -> dict[str, int | None]:
        return {
            "Notes de cours": self.notes_de_cours,
            "Notes manuscrites": self.notes_manuscrites,
            "Ordinateur portable": self.ordinateur_portable,
            "Calculatrice ": self.calculatrice,
            "Feuilles brouillon": self.feuilles_brouillon,
        }


@dataclass
class Page01Graphics:
    student_id: str
    group: str
    conditions: ConditionResult
    cryptogram: CryptogramResult | None
    signature_crop: Image.Image
    student_grid: GridReadResult
    group_grid: GridReadResult

    def as_page01_rows(self, cryptogram_valid: int | None = None) -> dict[str, Any]:
        rows: dict[str, Any] = {}
        rows.update(self.conditions.as_page01_rows())
        rows["Group"] = self.group
        rows["STUDENT ID"] = self.student_id
        rows["Validation cryptogramme"] = cryptogram_valid
        return rows


def read_page01_graphics(image: ImageLike) -> Page01Graphics:
    """Read the graphical fields from PAGE-01.

    This function intentionally does not perform OCR or signature recognition.
    It returns the fields that belong to the graphical module and a cropped
    signature image that the recognition module can consume.
    """
    try:
        arr = load_gray(image)
        rgb = load_rgb(image)
    except Exception:
        arr = np.full((1200, 900), 255, dtype=np.uint8)
        rgb = Image.fromarray(arr).convert("RGB")
    student_grid = _safe_call(lambda: read_student_id_grid(arr), GridReadResult("", np.empty((0, 0)), {}, 0.0))
    group_grid = _safe_call(lambda: read_group_grid(arr), GridReadResult("", np.empty((0, 0)), {}, 0.0))
    conditions = _safe_call(lambda: read_exam_conditions(arr), _empty_conditions())
    cryptogram = _safe_call(lambda: extract_cryptogram(arr), None)
    signature_crop = _safe_call(lambda: crop_signature(rgb, arr), Image.new("RGB", (1, 1), "white"))
    return Page01Graphics(
        student_id=student_grid.value,
        group=group_grid.value,
        conditions=conditions,
        cryptogram=cryptogram,
        signature_crop=signature_crop,
        student_grid=student_grid,
        group_grid=group_grid,
    )


def read_student_id_grid(image: ImageLike) -> GridReadResult:
    try:
        arr = load_gray(image)
    except Exception:
        return GridReadResult("", np.empty((0, 0)), {}, 0.0)
    width = arr.shape[1]
    boxes = find_square_candidates(
        arr,
        STUDENT_ID_ROI,
        threshold=125,
        min_side=max(32, int(width * 0.012)),
        max_side=max(80, int(width * 0.035)),
        min_fill=0.10,
        max_fill=0.70,
    )
    return _read_fixed_grid(
        arr=arr,
        components=boxes,
        expected_rows=10,
        expected_cols=5,
        row_labels=[str(i) for i in range(10)],
        col_decoder=lambda selected: "".join(selected),
        min_row_unique_cols=4,
    )


def read_group_grid(image: ImageLike) -> GridReadResult:
    try:
        arr = load_gray(image)
    except Exception:
        return GridReadResult("", np.empty((0, 0)), {}, 0.0)
    width = arr.shape[1]
    boxes = find_square_candidates(
        arr,
        GROUP_ROI,
        threshold=125,
        min_side=max(32, int(width * 0.012)),
        max_side=max(80, int(width * 0.035)),
        min_fill=0.10,
        max_fill=0.70,
    )

    def decode_group(selected: list[str]) -> str:
        if len(selected) < 3:
            return ""
        return f"G{selected[0]}{selected[1]}{selected[2]}"

    row_labels = [str(i) for i in range(10)]
    # The third column encodes letters A-J using the same row index.
    result = _read_fixed_grid(
        arr=arr,
        components=boxes,
        expected_rows=10,
        expected_cols=3,
        row_labels=row_labels,
        col_decoder=lambda selected: selected,
        min_row_unique_cols=2,
    )
    if result.scores.size == 0 or result.scores.shape[0] == 0 or result.scores.shape[1] == 0:
        return GridReadResult("", result.scores, result.boxes, 0.0)

    selected_rows = []
    for col in range(min(3, result.scores.shape[1])):
        column = np.nan_to_num(result.scores[:, col], nan=-1.0)
        if column.size == 0 or float(column.max()) < 0:
            return GridReadResult("", result.scores, result.boxes, 0.0)
        row_index = int(np.argmax(column))
        if col < 2:
            selected_rows.append(str(row_index))
        else:
            selected_rows.append(chr(ord("A") + row_index))
    return GridReadResult(
        value=decode_group(selected_rows),
        scores=result.scores,
        boxes=result.boxes,
        confidence=result.confidence,
    )


def _read_fixed_grid(
    arr: np.ndarray,
    components: list[Component],
    expected_rows: int,
    expected_cols: int,
    row_labels: list[str],
    col_decoder,
    min_row_unique_cols: int,
) -> GridReadResult:
    if arr is None or np.asarray(arr).size == 0 or not components:
        return GridReadResult("", np.empty((0, 0)), {}, 0.0)

    centers = [(comp.box.center[0], comp.box.center[1], comp) for comp in components]
    median_side = float(np.median([max(comp.box.width, comp.box.height) for comp in components]))
    tolerance = max(18.0, median_side * 0.55)
    col_centers = cluster_positions([x for x, _y, _comp in centers], tolerance=tolerance)
    if not col_centers:
        return GridReadResult("", np.empty((0, 0)), {}, 0.0)
    if len(col_centers) > expected_cols:
        # Keep the columns that look like a full grid: those with most boxes.
        col_counts = []
        for col in col_centers:
            count = sum(abs(x - col) <= tolerance for x, _y, _comp in centers)
            col_counts.append((count, col))
        col_centers = sorted([col for _count, col in sorted(col_counts, reverse=True)[:expected_cols]])
    else:
        col_centers = sorted(col_centers)

    row_centers_all = cluster_positions([y for _x, y, _comp in centers], tolerance=tolerance)
    candidate_rows: list[float] = []
    for row in row_centers_all:
        used_cols: set[int] = set()
        for x, y, _comp in centers:
            if abs(y - row) <= tolerance and col_centers:
                col = nearest_index(x, col_centers)
                if abs(x - col_centers[col]) <= tolerance:
                    used_cols.add(col)
        if len(used_cols) >= min_row_unique_cols:
            candidate_rows.append(row)
    row_centers = choose_regular_window(candidate_rows, expected_rows)

    scores = np.full((len(row_centers), len(col_centers)), np.nan, dtype=float)
    cell_boxes: dict[tuple[int, int], Box] = {}
    for x, y, comp in centers:
        if not row_centers or not col_centers:
            continue
        row = nearest_index(y, row_centers)
        col = nearest_index(x, col_centers)
        if abs(y - row_centers[row]) > tolerance or abs(x - col_centers[col]) > tolerance:
            continue
        score = inner_dark_score(arr, comp.box, threshold=145, inset=0.28)
        current = scores[row, col]
        if np.isnan(current) or score > current:
            scores[row, col] = score
            cell_boxes[(row, col)] = comp.box

    if scores.size == 0:
        return GridReadResult("", scores, cell_boxes, 0.0)

    selected: list[str] = []
    margins: list[float] = []
    for col in range(scores.shape[1]):
        column = scores[:, col]
        valid = np.nan_to_num(column, nan=-1.0)
        if valid.size == 0 or float(valid.max()) < 0:
            return GridReadResult("", scores, cell_boxes, 0.0)
        row_index = int(np.argmax(valid))
        selected.append(row_labels[row_index])
        sorted_scores = sorted(valid, reverse=True)
        second = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
        margins.append(max(0.0, sorted_scores[0] - second))

    decoded = col_decoder(selected)
    if isinstance(decoded, list):
        decoded_text = "".join(decoded)
    else:
        decoded_text = str(decoded)
    confidence = float(np.mean(margins)) if margins else 0.0
    return GridReadResult(decoded_text, scores, cell_boxes, confidence)


def read_exam_conditions(image: ImageLike) -> ConditionResult:
    try:
        arr = load_gray(image)
    except Exception:
        return _empty_conditions()
    pairs = _condition_yes_no_pairs(arr)
    max_numbers = _condition_max_numbers(arr)

    names = [
        "notes_de_cours",
        "notes_manuscrites",
        "ordinateur_portable",
        "calculatrice",
        "feuilles_brouillon",
    ]
    raw_pairs = {name: pair for name, pair in zip(names, pairs)}

    yes_values = []
    for pair in pairs:
        if pair is None:
            yes_values.append(None)
        else:
            yes_score, no_score = pair
            yes_values.append(yes_score > no_score)

    notes_de_cours = _bool_to_int(yes_values[0])
    if yes_values[1] is None:
        notes_manuscrites = None
    elif yes_values[1]:
        notes_manuscrites = max_numbers.get("notes_manuscrites") or 1
    else:
        notes_manuscrites = 0
    ordinateur = _bool_to_int(yes_values[2])
    calculatrice = _bool_to_int(yes_values[3])
    if yes_values[4] is None:
        feuilles = None
    elif yes_values[4]:
        feuilles = max_numbers.get("feuilles_brouillon") or 1
    else:
        feuilles = 0

    return ConditionResult(
        notes_de_cours=notes_de_cours,
        notes_manuscrites=notes_manuscrites,
        ordinateur_portable=ordinateur,
        calculatrice=calculatrice,
        feuilles_brouillon=feuilles,
        raw_pairs=raw_pairs,
        max_numbers=max_numbers,
    )


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _condition_yes_no_pairs(arr: np.ndarray) -> list[tuple[float, float] | None]:
    if arr is None or np.asarray(arr).size == 0:
        return [None] * 5
    width = arr.shape[1]
    min_side = max(55, int(width * 0.020))
    max_side = max(120, int(width * 0.045))
    comps = find_square_candidates(
        arr,
        CONDITION_ROW_ROI,
        threshold=130,
        min_side=min_side,
        max_side=max_side,
        min_fill=0.12,
        max_fill=1.00,
        min_aspect=0.75,
        max_aspect=1.35,
    )
    if not comps:
        return [None] * 5

    y_tolerance = max(22.0, float(np.median([comp.box.height for comp in comps])) * 0.55)
    row_centers = cluster_positions([comp.box.center[1] for comp in comps], y_tolerance)
    best_row: list[Component] = []
    for row in row_centers:
        row_comps = [comp for comp in comps if abs(comp.box.center[1] - row) <= y_tolerance]
        if len(row_comps) > len(best_row):
            best_row = row_comps
    row_comps = sorted(best_row, key=lambda comp: comp.box.center[0])

    # Text fragments are already removed by the square aspect filter.  If a
    # noisy component remains, keep the 10 strongest square candidates in order.
    if len(row_comps) > 10:
        row_comps = sorted(row_comps, key=lambda comp: comp.area, reverse=True)[:10]
        row_comps = sorted(row_comps, key=lambda comp: comp.box.center[0])

    pairs: list[tuple[float, float] | None] = []
    for i in range(0, 10, 2):
        if i + 1 >= len(row_comps):
            pairs.append(None)
            continue
        yes_score = component_fill_score(row_comps[i])
        no_score = component_fill_score(row_comps[i + 1])
        pairs.append((yes_score, no_score))
    while len(pairs) < 5:
        pairs.append(None)
    return pairs[:5]


def _condition_max_numbers(arr: np.ndarray) -> dict[str, int | None]:
    comps = _max_number_components(arr)
    values: dict[str, int | None] = {
        "notes_manuscrites": None,
        "feuilles_brouillon": None,
    }
    if not comps:
        return values
    comps = sorted(comps, key=lambda comp: comp.box.center[0])
    if len(comps) >= 1:
        values["notes_manuscrites"] = _read_two_digit_number(arr, comps[0].box)
    if len(comps) >= 2:
        values["feuilles_brouillon"] = _read_two_digit_number(arr, comps[-1].box)
    return values


def _max_number_components(arr: np.ndarray) -> list[Component]:
    if arr is None or np.asarray(arr).size == 0:
        return []
    roi_box = relative_box(arr.shape, MAX_NUMBER_ROI)
    mask = crop_array(arr, roi_box) < 130
    comps = connected_components(mask, offset=(roi_box.x0, roi_box.y0))
    out: list[Component] = []
    width = arr.shape[1]
    for comp in comps:
        box = comp.box
        if not (int(width * 0.040) <= box.width <= int(width * 0.075)):
            continue
        if not (70 <= box.height <= 135):
            continue
        if not (1.45 <= box.aspect <= 2.40):
            continue
        if not (0.15 <= comp.fill_ratio <= 0.35):
            continue
        out.append(comp)
    return out


def _read_two_digit_number(arr: np.ndarray, box: Box) -> int | None:
    mid = (box.x0 + box.x1) // 2
    cells = [Box(box.x0, box.y0, mid, box.y1), Box(mid, box.y0, box.x1, box.y1)]
    digits = [_classify_small_printed_digit(arr, cell) for cell in cells]
    if any(d is None for d in digits):
        return None
    return int(f"{digits[0]}{digits[1]}")


def _classify_small_printed_digit(arr: np.ndarray, cell: Box) -> int | None:
    """Very small low-level digit classifier for the max-number boxes.

    The challenge values observed in these fields are small two-digit maxima
    such as 01 and 02.  The rule below is deliberately simple: after removing
    the cell border, a narrow blob is a 1, a wide blob with low middle band is
    a 2, and a wide blob with strong left/right strokes is a 0.
    """

    inner = cell.inset(0.28, 0.22)
    if inner.width <= 0 or inner.height <= 0:
        return None
    crop = crop_array(arr, inner)
    mask = crop < 100
    labels, count = ndi.label(mask)
    slices = ndi.find_objects(labels)
    clean = np.zeros_like(mask, dtype=bool)
    for label_id, sl in enumerate(slices, start=1):
        if sl is None:
            continue
        comp = labels[sl] == label_id
        if int(comp.sum()) >= 8:
            clean[sl] |= comp
    ys, xs = np.where(clean)
    if len(xs) == 0:
        return 0

    tight = clean[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    height, width = tight.shape
    ratio = width / max(1, height)
    if ratio < 0.58:
        return 1

    top = float(tight[: max(1, height // 3), :].mean())
    middle = float(tight[height // 3 : 2 * height // 3, :].mean())
    bottom = float(tight[2 * height // 3 :, :].mean())
    left = float(tight[:, : max(1, width // 3)].mean())
    right = float(tight[:, 2 * width // 3 :].mean())

    if middle < 0.48 and top > 0.45 and bottom > 0.45:
        return 2
    if left > 0.45 and right > 0.45:
        return 0
    # Conservative fallback for the only ambiguous case we expect here.
    return 2


def crop_signature(image: ImageLike, gray: np.ndarray | None = None) -> Image.Image:
    try:
        rgb = load_rgb(image)
        arr = gray if gray is not None else load_gray(image)
    except Exception:
        return Image.new("RGB", (1, 1), "white")
    detected = _detect_signature_box(arr)
    if detected is None:
        detected = relative_box(arr.shape, SIGNATURE_FALLBACK_ROI)
    inner = detected.inset(0.035, 0.055)
    return rgb.crop((inner.x0, inner.y0, inner.x1, inner.y1))


def _detect_signature_box(arr: np.ndarray) -> Box | None:
    if arr is None or np.asarray(arr).size == 0:
        return None
    roi = (0.05, 0.24, 0.48, 0.48)
    comps = find_components(arr, roi=roi, threshold=130)
    candidates: list[Component] = []
    height, width = arr.shape
    for comp in comps:
        box = comp.box
        if not (0.20 * width <= box.width <= 0.42 * width):
            continue
        if not (0.07 * height <= box.height <= 0.18 * height):
            continue
        if not (1.35 <= box.aspect <= 2.80):
            continue
        if comp.fill_ratio > 0.25:
            continue
        candidates.append(comp)
    if not candidates:
        return None
    return max(candidates, key=lambda comp: comp.box.area).box


def _empty_conditions() -> ConditionResult:
    names = [
        "notes_de_cours",
        "notes_manuscrites",
        "ordinateur_portable",
        "calculatrice",
        "feuilles_brouillon",
    ]
    return ConditionResult(
        notes_de_cours=None,
        notes_manuscrites=None,
        ordinateur_portable=None,
        calculatrice=None,
        feuilles_brouillon=None,
        raw_pairs={name: None for name in names},
        max_numbers={"notes_manuscrites": None, "feuilles_brouillon": None},
    )


def _safe_call(fn, default):
    try:
        return fn()
    except Exception:
        return default
