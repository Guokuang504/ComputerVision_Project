from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from statistics import median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FORMS = ["FORM1", "FORM2", "FORM3"]
OUTPUT_COLUMNS = [
    "form",
    "source_file",
    "page",
    "item_id",
    "predicted_value",
    "confidence",
    "status",
    "debug_image_path",
    "reason_for_review",
    "ground_truth",
    "comment",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Select prioritized manual review samples from debug CSVs.")
    parser.add_argument("--forms", nargs="+", default=DEFAULT_FORMS, help="Forms to inspect, e.g. FORM1 FORM2 FORM3")
    parser.add_argument("--max-per-task", type=int, default=120, help="Maximum rows per output review CSV")
    parser.add_argument("--output-dir", default="annotations/review_samples")
    args = parser.parse_args()

    output_dir = _path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    forms = list(args.forms)

    outputs = {
        "printed_ocr_review_samples.csv": select_printed_ocr(forms, args.max_per_task),
        "handwritten_review_samples.csv": select_handwritten(forms, args.max_per_task),
        "signature_review_samples.csv": select_signatures(forms, args.max_per_task),
        "qcm_review_samples.csv": select_qcm(forms, args.max_per_task),
    }
    for filename, rows in outputs.items():
        path = output_dir / filename
        _write_csv(path, rows, OUTPUT_COLUMNS)
        print(f"{path}: {len(rows)} rows")


def select_printed_ocr(forms: list[str], limit: int) -> list[dict[str, Any]]:
    selected = []
    for form in forms:
        for row in _read_result_csv(form, "printed_ocr_debug.csv"):
            status = row.get("status", "")
            text = row.get("predicted_text", "")
            quality = row.get("crop_quality", "")
            reasons = []
            score = 0
            if status == "invalid_crop":
                reasons.append("invalid_crop")
                score += 120
            if status == "failed":
                reasons.append("ocr_failed")
                score += 105
            if status == "low_confidence":
                reasons.append("low_confidence")
                score += 90
            if not text.strip():
                reasons.append("empty_ocr")
                score += 80
            if quality and quality != "valid":
                reasons.append(f"crop_quality_{quality}")
                score += 55
            if _is_suspicious_text(text, row.get("field_name", "")):
                reasons.append("suspicious_text")
                score += 45
            if form == "FORM3":
                reasons.append("FORM3_sample")
                score += 15
            if score <= 0:
                continue
            selected.append(
                _review_row(
                    form=form,
                    source_file=row.get("source_file") or row.get("name", ""),
                    page="1",
                    item_id=row.get("field_name") or row.get("name", ""),
                    predicted_value=text,
                    confidence=row.get("confidence", ""),
                    status=status,
                    debug_image_path=row.get("crop_path", ""),
                    reason_for_review=";".join(reasons),
                    score=score,
                )
            )
    return _top_rows(selected, limit)


def select_handwritten(forms: list[str], limit: int) -> list[dict[str, Any]]:
    selected = []
    for form in forms:
        for row in _read_result_csv(form, "handwritten_debug.csv"):
            name = row.get("name", "")
            source_file, page, crop_id, field_name = _parse_handwritten_name(name)
            status = row.get("status", "")
            quality = row.get("crop_quality", "")
            reasons = []
            score = 0
            if status == "failed":
                reasons.append("failed")
                score += 120
            if status == "low_confidence":
                reasons.append("low_confidence")
                score += 95
            if quality in {"empty", "too_small", "too_noisy", "border_contamination", "low_contrast", "invalid"}:
                reasons.append(f"crop_quality_{quality}")
                score += 80
            if form == "FORM3" and status == "failed":
                reasons.append("FORM3_failed_priority")
                score += 60
            elif form == "FORM3":
                reasons.append("FORM3_sample")
                score += 15
            if not row.get("value", "").strip():
                reasons.append("empty_prediction")
                score += 35
            if score <= 0:
                continue
            selected.append(
                _review_row(
                    form=form,
                    source_file=source_file,
                    page=page,
                    item_id=crop_id or field_name or name,
                    predicted_value=row.get("value", ""),
                    confidence=row.get("confidence", ""),
                    status=status,
                    debug_image_path=row.get("debug_path", ""),
                    reason_for_review=";".join(reasons),
                    score=score,
                )
            )
    return _top_rows(selected, limit)


def select_signatures(forms: list[str], limit: int) -> list[dict[str, Any]]:
    selected = []
    for form in forms:
        for row in _read_result_csv(form, "signature_scores.csv"):
            status = row.get("status", "")
            margin = _float(row.get("margin"))
            top1 = _float(row.get("top1_score"))
            top2 = _float(row.get("top2_score"))
            reasons = []
            score = 0
            if status in {"rejected", "ambiguous", "invalid_input"}:
                reasons.append(status)
                score += {"rejected": 105, "ambiguous": 120, "invalid_input": 130}.get(status, 80)
            if margin < 0.03:
                reasons.append("low_margin")
                score += 75
            if abs(top1 - top2) < 0.03:
                reasons.append("top1_top2_close")
                score += 70
            if score <= 0:
                continue
            selected.append(
                _review_row(
                    form=form,
                    source_file=row.get("source_file") or row.get("name", ""),
                    page="",
                    item_id="signature",
                    predicted_value=row.get("predicted_student_id", ""),
                    confidence=row.get("confidence", ""),
                    status=status,
                    debug_image_path=row.get("debug_path", ""),
                    reason_for_review=";".join(reasons),
                    score=score,
                )
            )
    return _top_rows(selected, limit)


def select_qcm(forms: list[str], limit: int) -> list[dict[str, Any]]:
    selected = []
    all_rows_by_form = {form: _read_result_csv(form, "qcm_candidates.csv") for form in forms}
    medians = {}
    for form, rows in all_rows_by_form.items():
        areas = [_float(row.get("area")) for row in rows if row.get("area")]
        fills = [_float(row.get("fill_ratio")) for row in rows if row.get("fill_ratio")]
        medians[form] = {
            "area": median(areas) if areas else 0.0,
            "fill": median(fills) if fills else 0.0,
        }

    for form, rows in all_rows_by_form.items():
        median_area = medians[form]["area"]
        for row in rows:
            source_file, page = _parse_source_page(row.get("source", ""))
            decision = row.get("decision") or ("accepted" if row.get("accepted") == "1" else "rejected")
            area = _float(row.get("area"))
            aspect = _float(row.get("aspect_ratio"))
            fill = _float(row.get("fill_ratio"))
            inner = _float(row.get("inner_dark_score"))
            reason = row.get("reason", "")
            reasons = []
            score = 0
            if decision == "accepted":
                if median_area and (area > median_area * 1.8 or area < median_area * 0.55):
                    reasons.append("accepted_abnormal_area")
                    score += 90
                if aspect < 0.72 or aspect > 1.32:
                    reasons.append("accepted_abnormal_aspect")
                    score += 90
                if fill > 0.82 or fill < 0.08:
                    reasons.append("accepted_abnormal_fill")
                    score += 80
                if 0.35 <= inner <= 0.48:
                    reasons.append("close_to_checked_threshold")
                    score += 45
            else:
                if reason == "size_not_checkbox":
                    reasons.append("rejected_size_not_checkbox")
                    score += 75
                if aspect > 1.35 or area > max(1800, median_area * 1.7):
                    reasons.append("possible_numeric_box")
                    score += 70
            if form in {"FORM2", "FORM3"}:
                reasons.append(f"{form}_sample")
                score += 10
            if score <= 0:
                continue
            selected.append(
                _review_row(
                    form=form,
                    source_file=source_file,
                    page=page,
                    item_id=f"candidate_{row.get('index', '')}",
                    predicted_value=decision,
                    confidence=row.get("inner_dark_score", ""),
                    status=reason or decision,
                    debug_image_path=row.get("debug_path", ""),
                    reason_for_review=";".join(reasons),
                    score=score,
                )
            )
    return _top_rows(selected, limit)


def _read_result_csv(form: str, filename: str) -> list[dict[str, str]]:
    path = PROJECT_ROOT / "output" / f"verification_{form}_FINAL" / filename
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _review_row(**kwargs: Any) -> dict[str, Any]:
    row = dict(kwargs)
    row.setdefault("ground_truth", "")
    row.setdefault("comment", "")
    return row


def _top_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda row: (-int(row.get("score", 0)), row.get("form", ""), row.get("source_file", ""), row.get("item_id", "")))
    for row in rows:
        row.pop("score", None)
    return rows[:limit]


def _parse_source_page(source: str) -> tuple[str, str]:
    match = re.match(r"(?P<source>.+)_p(?P<page>\d+)$", source)
    if match:
        return match.group("source"), match.group("page")
    return source, ""


def _parse_handwritten_name(name: str) -> tuple[str, str, str, str]:
    match = re.match(r"(?P<source>.+)_p(?P<page>\d+)_(?P<crop>z\d+_(?P<field>.+))$", name)
    if match:
        return match.group("source"), match.group("page"), match.group("crop"), match.group("field")
    source, page = _parse_source_page(name)
    return source, page, name, ""


def _is_suspicious_text(text: str, field_name: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return True
    if field_name in {"module", "professor", "date", "code"} and len(cleaned) < 2:
        return True
    if field_name in {"note_max", "note_valid"} and not any(ch.isdigit() for ch in cleaned):
        return True
    return False


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


if __name__ == "__main__":
    main()
