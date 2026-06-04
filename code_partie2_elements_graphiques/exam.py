"""Generic checkbox reader for exam answer pages."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .components import (
    Box,
    Component,
    ImageLike,
    choose_regular_window,
    cluster_positions,
    crop_array,
    find_components,
    find_square_candidates,
    inner_dark_score,
    load_gray,
    nearest_index,
    relative_box,
)


@dataclass
class ExamQuestionChoices:
    question: int
    choices: dict[str, int]
    scores: dict[str, float]
    boxes: dict[str, Box]


def read_exam_choices(
    image: ImageLike,
    choice_labels: str = "ABCDEFGH",
    roi: tuple[float, float, float, float] = (0.04, 0.08, 0.96, 0.92),
    min_questions: int | None = None,
    checked_threshold: float = 0.12,
    debug_dir: str | None = None,
    source_name: str = "exam",
) -> list[ExamQuestionChoices]:
    """Read choice boxes from a semi-structured exam page.

    The function detects square checkbox components, clusters them into rows
    and columns, and scores the ink inside each box.  It is intentionally
    layout-light: if the final integration module crops a smaller answer-table
    region first, pass it through `roi` for better precision.
    """

    try:
        arr = load_gray(image)
    except Exception:
        return []
    width = arr.shape[1]
    raw_comps = _form_box_candidates(arr, roi=roi)
    comps, debug_records = _filter_checkbox_candidates(arr, raw_comps)
    if not comps:
        _write_qcm_candidates_debug(arr, debug_records, debug_dir, source_name)
        return []

    vertical_questions = _read_vertical_choice_stacks(
        arr,
        comps,
        debug_records,
        choice_labels=choice_labels,
        checked_threshold=checked_threshold,
    )
    if vertical_questions:
        _write_qcm_candidates_debug(arr, debug_records, debug_dir, source_name)
        return vertical_questions

    rows, cols = _cluster_exam_grid(comps, expected_cols=len(choice_labels))
    if min_questions is not None and len(rows) > min_questions:
        rows = choose_regular_window(rows, min_questions)
    if not rows or not cols:
        for record in debug_records:
            if record["reason"] == "candidate":
                record["reason"] = "no_regular_grid"
        _write_qcm_candidates_debug(arr, debug_records, debug_dir, source_name)
        return []

    median_side = float(np.median([max(comp.box.width, comp.box.height) for comp in comps]))
    tolerance = max(18.0, median_side * 0.65)
    cell_scores = np.full((len(rows), len(cols)), np.nan)
    cell_boxes: dict[tuple[int, int], Box] = {}
    assigned_candidates: set[tuple[int, int, int, int]] = set()
    selected_candidates: set[tuple[int, int, int, int]] = set()
    for comp in comps:
        x, y = comp.box.center
        row = nearest_index(y, rows)
        col = nearest_index(x, cols)
        if abs(y - rows[row]) > tolerance or abs(x - cols[col]) > tolerance:
            continue
        assigned_candidates.add(_box_key(comp.box))
        score = inner_dark_score(arr, comp.box, threshold=145, inset=0.28)
        current = cell_scores[row, col]
        if np.isnan(current) or score > current:
            cell_scores[row, col] = score
            cell_boxes[(row, col)] = comp.box
            selected_candidates.add(_box_key(comp.box))

    for record in debug_records:
        if record["reason"] != "candidate":
            continue
        key = (record["x"], record["y"], record["x"] + record["w"], record["y"] + record["h"])
        if key in selected_candidates:
            record["accepted"] = 1
            record["reason"] = "accepted"
        elif key in assigned_candidates:
            record["reason"] = "duplicate_or_lower_score"
        else:
            record["reason"] = "not_in_grid"
    _write_qcm_candidates_debug(arr, debug_records, debug_dir, source_name)

    questions: list[ExamQuestionChoices] = []
    for row_index in range(cell_scores.shape[0]):
        scores: dict[str, float] = {}
        choices: dict[str, int] = {}
        boxes: dict[str, Box] = {}
        row_scores = np.nan_to_num(cell_scores[row_index], nan=0.0)
        max_score = float(row_scores.max()) if row_scores.size else 0.0
        adaptive_threshold = max(checked_threshold, max_score * 0.45 if max_score > 0.20 else checked_threshold)
        for col_index, label in enumerate(choice_labels[: cell_scores.shape[1]]):
            score = float(row_scores[col_index])
            scores[label] = score
            choices[label] = 1 if score >= adaptive_threshold and score >= checked_threshold else 0
            if (row_index, col_index) in cell_boxes:
                boxes[label] = cell_boxes[(row_index, col_index)]
        questions.append(
            ExamQuestionChoices(
                question=row_index + 1,
                choices=choices,
                scores=scores,
                boxes=boxes,
            )
        )
    return questions


def _cluster_exam_grid(comps: list[Component], expected_cols: int) -> tuple[list[float], list[float]]:
    median_side = float(np.median([max(comp.box.width, comp.box.height) for comp in comps]))
    tolerance = max(18.0, median_side * 0.65)
    centers = [(comp.box.center[0], comp.box.center[1]) for comp in comps]
    col_centers = cluster_positions([x for x, _y in centers], tolerance=tolerance)
    if len(col_centers) > expected_cols:
        counts = []
        for col in col_centers:
            counts.append((sum(abs(x - col) <= tolerance for x, _y in centers), col))
        col_centers = sorted([col for _count, col in sorted(counts, reverse=True)[:expected_cols]])

    row_centers_all = cluster_positions([y for _x, y in centers], tolerance=tolerance)
    rows: list[float] = []
    for row in row_centers_all:
        used_cols: set[int] = set()
        for x, y in centers:
            if abs(y - row) <= tolerance and col_centers:
                col = nearest_index(x, col_centers)
                if abs(x - col_centers[col]) <= tolerance:
                    used_cols.add(col)
        if len(used_cols) >= max(3, min(5, expected_cols // 2 + 1)):
            rows.append(row)
    return rows, col_centers


def _read_vertical_choice_stacks(
    arr: np.ndarray,
    comps: list[Component],
    debug_records: list[dict],
    choice_labels: str,
    checked_threshold: float,
) -> list[ExamQuestionChoices]:
    """Read real FORM pages where A-D boxes are stacked vertically.

    The rule is intentionally low-level: a QCM question is a regular vertical
    stack of checkbox-sized components with nearly the same x coordinate.
    Header artifacts such as the small boxes around "QUESTION" do not form this
    vertical pattern and are rejected as `not_in_vertical_stack`.
    """

    option_count = min(4, len(choice_labels))
    if option_count < 3:
        return []
    median_side = float(np.median([max(comp.box.width, comp.box.height) for comp in comps]))
    if not np.isfinite(median_side) or median_side <= 0:
        return []
    x_tolerance = max(18.0, median_side * 0.80)
    min_gap = max(20.0, median_side * 0.65)
    max_gap = max(115.0, median_side * 3.20)
    centers = [(comp.box.center[0], comp.box.center[1], comp) for comp in comps]
    x_centers = cluster_positions([x for x, _y, _comp in centers], tolerance=x_tolerance)

    windows: list[tuple[float, list[Component]]] = []
    used_keys: set[tuple[int, int, int, int]] = set()
    for x_center in x_centers:
        column = [comp for x, _y, comp in centers if abs(x - x_center) <= x_tolerance]
        column = sorted(column, key=lambda comp: comp.box.center[1])
        groups: list[list[Component]] = []
        current: list[Component] = []
        for comp in column:
            if current:
                gap = comp.box.center[1] - current[-1].box.center[1]
                if gap > max_gap * 1.45:
                    groups.append(current)
                    current = []
            current.append(comp)
        if current:
            groups.append(current)

        for group in groups:
            if len(group) < option_count:
                continue
            best_window: tuple[float, list[Component]] | None = None
            for start in range(0, len(group) - option_count + 1):
                window = group[start : start + option_count]
                y_values = [comp.box.center[1] for comp in window]
                x_values = [comp.box.center[0] for comp in window]
                gaps = np.diff(y_values)
                if not np.all((gaps >= min_gap) & (gaps <= max_gap)):
                    continue
                if max(x_values) - min(x_values) > x_tolerance:
                    continue
                mean_gap = float(np.mean(gaps))
                regularity = float(np.std(gaps) / max(1.0, mean_gap))
                if regularity > 0.45:
                    continue
                score = regularity + abs(float(np.mean(x_values)) - x_center) / max(1.0, arr.shape[1])
                if best_window is None or score < best_window[0]:
                    best_window = (score, window)
            if best_window is None:
                continue
            window_keys = {_box_key(comp.box) for comp in best_window[1]}
            if window_keys & used_keys:
                continue
            used_keys.update(window_keys)
            windows.append((float(np.mean([comp.box.center[1] for comp in best_window[1]])), best_window[1]))

    if not windows:
        for record in debug_records:
            if record["reason"] == "candidate":
                record["reason"] = "not_in_vertical_stack"
        return []

    questions: list[ExamQuestionChoices] = []
    selected_keys: set[tuple[int, int, int, int]] = set()
    for question_index, (_y, window) in enumerate(sorted(windows, key=lambda item: item[0]), start=1):
        scores: dict[str, float] = {}
        choices: dict[str, int] = {}
        boxes: dict[str, Box] = {}
        raw_scores = [inner_dark_score(arr, comp.box, threshold=145, inset=0.28) for comp in window]
        max_score = float(max(raw_scores)) if raw_scores else 0.0
        adaptive_threshold = max(checked_threshold, max_score * 0.45 if max_score > 0.20 else checked_threshold)
        for idx, comp in enumerate(window):
            label = choice_labels[idx]
            score = float(raw_scores[idx])
            scores[label] = score
            choices[label] = 1 if score >= adaptive_threshold and score >= checked_threshold else 0
            boxes[label] = comp.box
            selected_keys.add(_box_key(comp.box))
        questions.append(ExamQuestionChoices(question=question_index, choices=choices, scores=scores, boxes=boxes))

    for record in debug_records:
        if record["reason"] != "candidate":
            continue
        key = (record["x"], record["y"], record["x"] + record["w"], record["y"] + record["h"])
        if key in selected_keys:
            record["accepted"] = 1
            record["reason"] = "accepted"
        else:
            record["reason"] = "not_in_vertical_stack"
    return questions


def _form_box_candidates(
    arr: np.ndarray,
    roi: tuple[float, float, float, float],
) -> list[Component]:
    """Collect low-level form-box candidates, including numeric rectangles.

    This deliberately starts wider than real checkboxes so numeric-answer
    rectangles are visible in the debug CSV and can be rejected explicitly.
    """

    if arr is None or arr.size == 0:
        return []
    height, width = arr.shape[:2]
    min_side = max(18, int(width * 0.008))
    max_width = min(max(650, int(width * 0.20)), width)
    max_height = min(max(220, int(height * 0.07)), height)
    pool: list[Component] = []
    for comp in find_components(arr, roi=relative_box(arr.shape, roi), threshold=125):
        box = comp.box
        if box.width < min_side or box.height < min_side:
            continue
        if box.width > max_width or box.height > max_height:
            continue
        if box.aspect < 0.25 or box.aspect > 5.5:
            continue
        if comp.fill_ratio < 0.01 or comp.fill_ratio > 0.92:
            continue
        if _border_presence_score(arr, box) < 0.08:
            continue
        pool.append(comp)
    return pool


def _filter_checkbox_candidates(arr: np.ndarray, comps: list[Component]) -> tuple[list[Component], list[dict]]:
    if not comps:
        return [], []
    checkbox_like = [comp for comp in comps if _candidate_reason(arr, comp, median_side=None) == "candidate"]
    sides = np.asarray([max(comp.box.width, comp.box.height) for comp in checkbox_like], dtype=float)
    median_side = float(np.median(sides)) if sides.size else float("nan")
    out: list[Component] = []
    records: list[dict] = []
    height, width = arr.shape
    for idx, comp in enumerate(comps):
        box = comp.box
        reason = _candidate_reason(arr, comp, median_side=median_side)
        accepted = 0
        if reason == "candidate":
            out.append(comp)
        record = {
            "index": idx,
            "x": int(box.x0),
            "y": int(box.y0),
            "w": int(box.width),
            "h": int(box.height),
            "area": int(box.area),
            "dark_area": int(comp.area),
            "aspect_ratio": round(float(box.aspect), 4),
            "fill_ratio": round(float(comp.fill_ratio), 4),
            "inner_dark_score": round(float(inner_dark_score(arr, box, threshold=145, inset=0.28)), 4),
            "border_score": round(float(_border_presence_score(arr, box)), 4),
            "page_zone": _page_zone(box, width, height),
            "accepted": accepted,
            "reason": reason,
        }
        records.append(record)
    return out, records


def _candidate_reason(arr: np.ndarray, comp: Component, median_side: float | None) -> str:
    height, width = arr.shape
    box = comp.box
    checkbox_min_side = max(18, int(width * 0.008))
    checkbox_max_side = min(max(70, int(width * 0.026)), 95)
    if box.width < checkbox_min_side or box.height < checkbox_min_side:
        return "too_small"
    if box.width > checkbox_max_side or box.height > checkbox_max_side:
        return "size_not_checkbox"
    if box.x0 < width * 0.02 or box.x1 > width * 0.98:
        return "outside_horizontal_zone"
    if box.y0 < height * 0.04 or box.y1 > height * 0.96:
        return "outside_vertical_zone"
    if box.aspect < 0.78 or box.aspect > 1.25:
        return "aspect_not_square"
    if comp.fill_ratio < 0.08:
        return "fill_too_low"
    if comp.fill_ratio > 0.95:
        return "fill_too_high"
    if median_side is not None and np.isfinite(median_side) and median_side > 0:
        side = max(box.width, box.height)
        if side > median_side * 2.50 or side < median_side * 0.45:
            return "side_inconsistent"
    return "candidate"


def _write_qcm_candidates_debug(
    arr: np.ndarray,
    records: list[dict],
    debug_dir: str | None,
    source_name: str,
) -> None:
    if not debug_dir or not records:
        return
    root = Path(debug_dir)
    accepted_dir = root / "accepted_candidates"
    rejected_dir = root / "rejected_candidates"
    accepted_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir.mkdir(parents=True, exist_ok=True)
    csv_path = root / "qcm_candidates.csv"
    fieldnames = [
        "source",
        "index",
        "x",
        "y",
        "w",
        "h",
        "area",
        "dark_area",
        "aspect_ratio",
        "fill_ratio",
        "inner_dark_score",
        "border_score",
        "page_zone",
        "accepted",
        "decision",
        "reason",
        "debug_path",
    ]
    rows = []
    for record in records:
        box = Box(record["x"], record["y"], record["x"] + record["w"], record["y"] + record["h"])
        folder = accepted_dir if record.get("accepted") else rejected_dir
        filename = f"{_safe_name(source_name)}_{record['index']:04d}_{record['reason']}.png"
        crop_path = folder / filename
        try:
            crop = crop_array(arr, box.inflate(6, arr.shape))
            if crop.size:
                Image.fromarray(crop).convert("L").save(crop_path)
                debug_path = str(crop_path)
            else:
                debug_path = ""
        except Exception:
            debug_path = ""
        row = {
            "source": source_name,
            **record,
            "decision": "accepted" if record.get("accepted") else "rejected",
            "debug_path": debug_path,
        }
        rows.append(row)

    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def _page_zone(box: Box, width: int, height: int) -> str:
    x_center, y_center = box.center
    x_zone = "left" if x_center < width / 3 else "center" if x_center < 2 * width / 3 else "right"
    y_zone = "upper" if y_center < height / 3 else "middle" if y_center < 2 * height / 3 else "lower"
    return f"{y_zone}-{x_zone}"


def _border_presence_score(arr: np.ndarray, box: Box) -> float:
    crop = crop_array(arr, box)
    if crop.size == 0 or crop.ndim < 2:
        return 0.0
    h, w = crop.shape[:2]
    border = max(2, min(h, w) // 8)
    if h <= border * 2 or w <= border * 2:
        return 0.0
    top = float((crop[:border, :] < 145).mean())
    bottom = float((crop[-border:, :] < 145).mean())
    left = float((crop[:, :border] < 145).mean())
    right = float((crop[:, -border:] < 145).mean())
    return min(top, bottom, left, right)


def _box_key(box: Box) -> tuple[int, int, int, int]:
    return (int(box.x0), int(box.y0), int(box.x1), int(box.y1))


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(value))
