from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FORMS = ["FORM1", "FORM2", "FORM3"]
DEFAULT_ANNOTATIONS = {
    "printed_ocr": "annotations/printed_ocr_ground_truth.csv",
    "handwritten": "annotations/handwritten_ground_truth.csv",
    "signature": "annotations/signature_ground_truth.csv",
    "qcm": "annotations/qcm_review.csv",
}
TEMPLATES = {
    "printed_ocr": "annotations/templates/printed_ocr_ground_truth_template.csv",
    "handwritten": "annotations/templates/handwritten_ground_truth_template.csv",
    "signature": "annotations/templates/signature_ground_truth_template.csv",
    "qcm": "annotations/templates/qcm_review_template.csv",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate predictions when ground-truth annotations are available.")
    parser.add_argument("--task", choices=["all", "printed_ocr", "handwritten", "signature", "qcm"], default="all")
    parser.add_argument("--annotations", default=None, help="Annotation CSV for a single task")
    parser.add_argument("--output-dir", default="output/evaluation_with_ground_truth")
    parser.add_argument("--forms", nargs="+", default=DEFAULT_FORMS)
    args = parser.parse_args()

    output_dir = _path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = ["printed_ocr", "handwritten", "signature", "qcm"] if args.task == "all" else [args.task]

    summaries = {}
    for task in tasks:
        annotation_path = _path(args.annotations) if args.annotations and len(tasks) == 1 else _path(DEFAULT_ANNOTATIONS[task])
        if not annotation_path.exists():
            template_path = _path(TEMPLATES[task])
            print(f"Missing annotation file: {annotation_path}. Use {template_path} as template.")
            summaries[task] = {"status": "missing_annotations", "annotation_file": str(annotation_path)}
            continue
        if task == "printed_ocr":
            summaries[task] = evaluate_printed_ocr(annotation_path, output_dir, args.forms)
        elif task == "handwritten":
            summaries[task] = evaluate_handwritten(annotation_path, output_dir, args.forms)
        elif task == "signature":
            summaries[task] = evaluate_signature(annotation_path, output_dir, args.forms)
        elif task == "qcm":
            summaries[task] = evaluate_qcm(annotation_path, output_dir, args.forms)

    summary_path = output_dir / "evaluation_summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summaries, indent=2, ensure_ascii=False))
    print(f"saved: {summary_path}")


def evaluate_printed_ocr(annotation_path: Path, output_dir: Path, forms: list[str]) -> dict[str, Any]:
    predictions = {}
    for form in forms:
        for row in _read_result_csv(form, "printed_ocr_debug.csv"):
            key = (form, _norm_source(row.get("source_file", "")), row.get("field_name", ""))
            predictions[key] = row

    rows = _read_csv(annotation_path)
    errors = []
    field_counts: dict[str, Counter[str]] = defaultdict(Counter)
    exact = normalized = failed_empty = matched = 0
    for ann in rows:
        form = ann.get("form", "")
        field = ann.get("field_name", "")
        key = (form, _norm_source(ann.get("pdf_file", "")), field)
        pred = predictions.get(key)
        gt = ann.get("ground_truth_text", "")
        pred_text = pred.get("predicted_text", "") if pred else ""
        status = pred.get("status", "missing_prediction") if pred else "missing_prediction"
        if pred:
            matched += 1
        if pred_text == gt:
            exact += 1
            field_counts[field]["exact"] += 1
        if _normalize_text(pred_text) == _normalize_text(gt):
            normalized += 1
            field_counts[field]["normalized"] += 1
        if status in {"failed", "invalid_crop", "ocr_unavailable"} or not pred_text.strip():
            failed_empty += 1
        field_counts[field]["total"] += 1
        if _normalize_text(pred_text) != _normalize_text(gt):
            errors.append(_merge_case(ann, pred, predicted_value=pred_text, ground_truth=gt, status=status))

    _write_csv(output_dir / "printed_ocr_error_cases.csv", errors)
    _write_metric_rows(output_dir / "printed_ocr_field_accuracy.csv", field_counts)
    summary = {
        "annotations": len(rows),
        "matched_predictions": matched,
        "exact_match_accuracy": _rate(exact, len(rows)),
        "normalized_text_accuracy": _rate(normalized, len(rows)),
        "failed_empty_rate": _rate(failed_empty, len(rows)),
        "error_cases_csv": str(output_dir / "printed_ocr_error_cases.csv"),
    }
    _write_summary_csv(output_dir / "printed_ocr_summary.csv", summary)
    return summary


def evaluate_handwritten(annotation_path: Path, output_dir: Path, forms: list[str]) -> dict[str, Any]:
    predictions = {}
    for form in forms:
        for row in _read_result_csv(form, "handwritten_debug.csv"):
            source, page, crop_id, field = _parse_handwritten_name(row.get("name", ""))
            row = dict(row)
            row.update({"source_file": source, "page": page, "crop_id": crop_id, "field_name": field})
            keys = [
                (form, _norm_source(source), page, crop_id),
                (form, _norm_source(source), page, field),
            ]
            for key in keys:
                predictions[key] = row

    rows = _read_csv(annotation_path)
    errors = []
    field_counts: dict[str, Counter[str]] = defaultdict(Counter)
    confusion: Counter[tuple[str, str]] = Counter()
    confidence_bins: Counter[str] = Counter()
    correct = failed = matched = 0
    for ann in rows:
        form = ann.get("form", "")
        source = _norm_source(ann.get("pdf_file", ""))
        page = str(ann.get("page", ""))
        crop_or_field = ann.get("crop_id") or ann.get("field_name", "")
        pred = predictions.get((form, source, page, crop_or_field)) or predictions.get((form, source, page, ann.get("field_name", "")))
        gt = ann.get("ground_truth_value", "")
        pred_value = pred.get("value", "") if pred else ""
        status = pred.get("status", "missing_prediction") if pred else "missing_prediction"
        field = ann.get("field_name") or (pred.get("field_name", "") if pred else "")
        if pred:
            matched += 1
        if _normalize_number_text(pred_value) == _normalize_number_text(gt):
            correct += 1
            field_counts[field]["correct"] += 1
        else:
            errors.append(_merge_case(ann, pred, predicted_value=pred_value, ground_truth=gt, status=status))
        if status in {"failed", "invalid_input"} or not pred_value.strip():
            failed += 1
        field_counts[field]["total"] += 1
        confusion[(gt, pred_value)] += 1
        confidence_bins[_confidence_bin(_float(pred.get("confidence", 0.0) if pred else 0.0))] += 1

    _write_csv(output_dir / "handwritten_error_cases.csv", errors)
    _write_metric_rows(output_dir / "handwritten_field_accuracy.csv", field_counts)
    _write_counter_csv(output_dir / "handwritten_confidence_distribution.csv", confidence_bins, ["confidence_bin", "count"])
    _write_confusion_csv(output_dir / "handwritten_confusion_matrix.csv", confusion)
    summary = {
        "annotations": len(rows),
        "matched_predictions": matched,
        "accuracy": _rate(correct, len(rows)),
        "failed_crop_rate": _rate(failed, len(rows)),
        "error_cases_csv": str(output_dir / "handwritten_error_cases.csv"),
    }
    _write_summary_csv(output_dir / "handwritten_summary.csv", summary)
    return summary


def evaluate_signature(annotation_path: Path, output_dir: Path, forms: list[str]) -> dict[str, Any]:
    predictions = {}
    for form in forms:
        for row in _read_result_csv(form, "signature_scores.csv"):
            key = (form, _norm_source(row.get("source_file") or row.get("name", "")))
            predictions[key] = row

    rows = _read_csv(annotation_path)
    errors = []
    correct_top1 = false_rejection = false_acceptance = ambiguous = matched = 0
    scored = []
    for ann in rows:
        form = ann.get("form", "")
        source = _norm_source(ann.get("source_file", ""))
        pred = predictions.get((form, source))
        expected = ann.get("expected_student_id", "")
        genuine = _truthy(ann.get("is_genuine", "true"))
        status = pred.get("status", "missing_prediction") if pred else "missing_prediction"
        predicted_id = pred.get("predicted_student_id", "") if pred else ""
        distance = _float(pred.get("distance", 999.0) if pred else 999.0)
        if pred:
            matched += 1
            scored.append((distance, predicted_id, expected, genuine))
        if predicted_id == expected:
            correct_top1 += 1
        if genuine and status != "matched":
            false_rejection += 1
        if (not genuine and status == "matched") or (genuine and status == "matched" and predicted_id != expected):
            false_acceptance += 1
        if status == "ambiguous":
            ambiguous += 1
        if (genuine and (status != "matched" or predicted_id != expected)) or (not genuine and status == "matched"):
            errors.append(_merge_case(ann, pred, predicted_value=predicted_id, ground_truth=expected, status=status))

    curve, recommended = _signature_threshold_curve(scored)
    _write_csv(output_dir / "signature_error_cases.csv", errors)
    _write_csv(output_dir / "signature_threshold_curve.csv", curve)
    summary = {
        "annotations": len(rows),
        "matched_predictions": matched,
        "top1_accuracy": _rate(correct_top1, len(rows)),
        "false_rejection_rate": _rate(false_rejection, len(rows)),
        "false_acceptance_rate": _rate(false_acceptance, len(rows)),
        "ambiguous_rate": _rate(ambiguous, len(rows)),
        "recommended_threshold": recommended,
        "threshold_curve_csv": str(output_dir / "signature_threshold_curve.csv"),
    }
    _write_summary_csv(output_dir / "signature_summary.csv", summary)
    return summary


def evaluate_qcm(annotation_path: Path, output_dir: Path, forms: list[str]) -> dict[str, Any]:
    predictions = {}
    for form in forms:
        for row in _read_result_csv(form, "qcm_candidates.csv"):
            source, page = _parse_source_page(row.get("source", ""))
            index = row.get("index", "")
            keys = [
                (form, _norm_source(source), page, index),
                (form, _norm_source(source), page, f"candidate_{index}"),
            ]
            for key in keys:
                predictions[key] = row

    rows = _read_csv(annotation_path)
    errors = []
    correct = false_positive = false_negative = matched = unsupported = 0
    for ann in rows:
        form = ann.get("form", "")
        source = _norm_source(ann.get("pdf_file", ""))
        page = str(ann.get("page", ""))
        qid = str(ann.get("question_id", ""))
        expected_raw = ann.get("expected_choice", "")
        expected = _normalize_decision(expected_raw)
        pred = predictions.get((form, source, page, qid)) or predictions.get((form, source, page, f"candidate_{qid}"))
        decision = (pred.get("decision") if pred else "") or ("accepted" if pred and pred.get("accepted") == "1" else "rejected")
        if expected not in {"accepted", "rejected"}:
            unsupported += 1
            errors.append(_merge_case(ann, pred, predicted_value=decision, ground_truth=expected_raw, status="unsupported_expected_choice"))
            continue
        if pred:
            matched += 1
        if decision == expected:
            correct += 1
        else:
            if decision == "accepted" and expected == "rejected":
                false_positive += 1
            if decision == "rejected" and expected == "accepted":
                false_negative += 1
            errors.append(_merge_case(ann, pred, predicted_value=decision, ground_truth=expected, status=pred.get("reason", "") if pred else "missing_prediction"))

    _write_csv(output_dir / "qcm_error_cases.csv", errors)
    summary = {
        "annotations": len(rows),
        "matched_predictions": matched,
        "choice_accuracy": _rate(correct, len(rows) - unsupported),
        "false_positive_count": false_positive,
        "false_negative_count": false_negative,
        "unsupported_expected_choice_count": unsupported,
        "error_cases_csv": str(output_dir / "qcm_error_cases.csv"),
    }
    _write_summary_csv(output_dir / "qcm_summary.csv", summary)
    return summary


def _read_result_csv(form: str, filename: str) -> list[dict[str, str]]:
    path = PROJECT_ROOT / "output" / f"verification_{form}_FINAL" / filename
    return _read_csv(path) if path.exists() else []


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        if not fieldnames:
            f.write("")
            return
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_summary_csv(path: Path, summary: dict[str, Any]) -> None:
    _write_csv(path, [{"metric": key, "value": value} for key, value in summary.items()])


def _write_metric_rows(path: Path, counters: dict[str, Counter[str]]) -> None:
    rows = []
    for name, counter in sorted(counters.items()):
        total = counter.get("total", 0)
        numerator = counter.get("correct", counter.get("normalized", counter.get("exact", 0)))
        rows.append({"field_name": name, "total": total, "correct_or_normalized": numerator, "accuracy": _rate(numerator, total)})
    _write_csv(path, rows)


def _write_counter_csv(path: Path, counter: Counter[str], columns: list[str]) -> None:
    rows = [{columns[0]: key, columns[1]: value} for key, value in sorted(counter.items())]
    _write_csv(path, rows)


def _write_confusion_csv(path: Path, confusion: Counter[tuple[str, str]]) -> None:
    rows = [{"ground_truth": gt, "predicted": pred, "count": count} for (gt, pred), count in sorted(confusion.items())]
    _write_csv(path, rows)


def _merge_case(annotation: dict[str, Any], prediction: dict[str, Any] | None, predicted_value: str, ground_truth: str, status: str) -> dict[str, Any]:
    row = dict(annotation)
    row.update(
        {
            "predicted_value": predicted_value,
            "ground_truth": ground_truth,
            "prediction_status": status,
        }
    )
    if prediction:
        for key in ["confidence", "debug_path", "crop_path", "reason", "decision", "margin", "top1_score", "top2_score"]:
            if key in prediction:
                row[f"prediction_{key}"] = prediction[key]
    return row


def _signature_threshold_curve(scored: list[tuple[float, str, str, bool]]) -> tuple[list[dict[str, Any]], float | None]:
    if not scored:
        return [], None
    thresholds = sorted({round(distance, 4) for distance, _pred, _expected, _genuine in scored})
    rows = []
    best: tuple[int, int, float] | None = None
    for threshold in thresholds:
        false_accept = false_reject = correct_accept = accepted = 0
        for distance, predicted, expected, genuine in scored:
            is_accepted = distance <= threshold
            if is_accepted:
                accepted += 1
            if genuine and predicted == expected and is_accepted:
                correct_accept += 1
            if genuine and predicted == expected and not is_accepted:
                false_reject += 1
            if (not genuine and is_accepted) or (genuine and predicted != expected and is_accepted):
                false_accept += 1
        row = {
            "threshold": threshold,
            "accepted": accepted,
            "correct_accept": correct_accept,
            "false_acceptance_count": false_accept,
            "false_rejection_count": false_reject,
        }
        rows.append(row)
        candidate = (false_accept, false_reject, threshold)
        if best is None or candidate < best:
            best = candidate
    return rows, best[2] if best else None


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


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value)).strip().lower()


def _normalize_number_text(value: str) -> str:
    cleaned = str(value).strip().replace(",", ".")
    try:
        return str(float(cleaned))
    except ValueError:
        return _normalize_text(cleaned)


def _normalize_decision(value: str) -> str:
    cleaned = str(value).strip().lower()
    if cleaned in {"1", "true", "yes", "accepted", "accept", "correct"}:
        return "accepted"
    if cleaned in {"0", "false", "no", "rejected", "reject", "incorrect"}:
        return "rejected"
    return cleaned


def _norm_source(value: str) -> str:
    stem = Path(str(value).strip()).stem
    return stem


def _confidence_bin(value: float) -> str:
    if value < 0.25:
        return "0.00-0.24"
    if value < 0.50:
        return "0.25-0.49"
    if value < 0.75:
        return "0.50-0.74"
    return "0.75-1.00"


def _truthy(value: str) -> bool:
    return str(value).strip().lower() not in {"0", "false", "no", "n", "forged", "fake"}


def _rate(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


if __name__ == "__main__":
    main()
