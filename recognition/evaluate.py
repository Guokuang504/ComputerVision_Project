from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

import numpy as np

from .signature import SignatureRecognizer


def evaluate_signature_leave_one_out(
    signatures_root: str | Path,
    threshold: float = 0.82,
    scores_out: str | Path | None = None,
    thresholds_out: str | Path | None = None,
    debug_dir: str | Path | None = None,
) -> dict[str, float]:
    root = Path(signatures_root)
    paths = sorted(root.rglob("*.png"))
    labels = np.asarray([path.parent.name for path in paths])
    recognizer = SignatureRecognizer(threshold=threshold)
    cache = {path: recognizer.extract_feature_sets(path) for path in paths}
    ids = sorted(set(labels))
    distance_matrix = np.zeros((len(paths), len(paths)), dtype=np.float32)
    for name, weight in recognizer.feature_weights.items():
        features = np.vstack([cache[path][name] for path in paths])
        norms = np.sum(features * features, axis=1)
        squared = norms[:, None] + norms[None, :] - 2.0 * features.dot(features.T)
        distance_matrix += weight * np.sqrt(np.maximum(squared, 0.0)).astype(np.float32)
    np.fill_diagonal(distance_matrix, np.inf)

    score_rows = []

    for idx, test_path in enumerate(paths):
        best_by_id: dict[str, float] = {}
        for sid in ids:
            sid_indices = np.where(labels == sid)[0]
            sid_indices = sid_indices[sid_indices != idx]
            if len(sid_indices) > 0:
                best_by_id[sid] = float(distance_matrix[idx, sid_indices].min())
        ranked = sorted(best_by_id.items(), key=lambda item: item[1])
        predicted_student_id, distance = ranked[0]
        second_distance = ranked[1][1] if len(ranked) > 1 else float("inf")
        confidence = float(max(0.0, min(1.0, 1.0 - distance / max(second_distance, 1e-6))))
        status = _signature_status(distance, confidence, threshold)
        expected_student_id = test_path.parent.name
        correct = predicted_student_id == expected_student_id
        score_rows.append(
            {
                "image": str(test_path),
                "expected_student_id": expected_student_id,
                "predicted_student_id": predicted_student_id,
                "distance": distance,
                "second_distance": second_distance,
                "confidence": confidence,
                "status": status,
                "correct": int(correct),
            }
        )
        _maybe_copy_debug_sample(test_path, status, correct, debug_dir)

    total = len(paths)
    metrics = _metrics_from_scores(score_rows, threshold)
    metrics["samples"] = float(total)
    if scores_out:
        _write_csv(score_rows, scores_out)
    if thresholds_out:
        _write_csv(_threshold_sweep(score_rows), thresholds_out)
    return {
        "samples": float(total),
        "top1_accuracy": metrics["top1_accuracy"],
        "accepted_correct_rate": metrics["accepted_correct_rate"],
        "accepted_wrong_rate": metrics["accepted_wrong_rate"],
        "rejection_rate": metrics["rejection_rate"],
        "ambiguous_rate": metrics["ambiguous_rate"],
    }


def _signature_status(distance: float, confidence: float, threshold: float, ambiguous_margin: float = 0.02) -> str:
    if distance > threshold:
        return "rejected"
    if confidence < ambiguous_margin:
        return "ambiguous"
    return "matched"


def _metrics_from_scores(rows: list[dict], threshold: float) -> dict[str, float]:
    total = len(rows)
    if total == 0:
        return {
            "top1_accuracy": 0.0,
            "accepted_correct_rate": 0.0,
            "accepted_wrong_rate": 0.0,
            "rejection_rate": 0.0,
            "ambiguous_rate": 0.0,
        }
    statuses = [_signature_status(float(r["distance"]), float(r["confidence"]), threshold) for r in rows]
    correct = [bool(int(r["correct"])) for r in rows]
    matched = [s == "matched" for s in statuses]
    return {
        "top1_accuracy": sum(correct) / total,
        "accepted_correct_rate": sum(m and c for m, c in zip(matched, correct)) / total,
        "accepted_wrong_rate": sum(m and not c for m, c in zip(matched, correct)) / total,
        "rejection_rate": sum(s == "rejected" for s in statuses) / total,
        "ambiguous_rate": sum(s == "ambiguous" for s in statuses) / total,
    }


def _threshold_sweep(rows: list[dict]) -> list[dict]:
    out = []
    for threshold in np.arange(0.74, 0.901, 0.01):
        metrics = _metrics_from_scores(rows, float(threshold))
        out.append({"threshold": round(float(threshold), 3), **metrics})
    return out


def _write_csv(rows: list[dict], output_path: str | Path) -> None:
    if not rows:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _maybe_copy_debug_sample(path: Path, status: str, correct: bool, debug_dir: str | Path | None) -> None:
    if debug_dir is None:
        return
    group = "matched" if status == "matched" and correct else status
    if status == "matched" and not correct:
        group = "wrong_match"
    folder = Path(debug_dir) / group
    folder.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(path, folder / path.name)
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signatures", default="SIGNATURES")
    parser.add_argument("--threshold", type=float, default=0.82)
    parser.add_argument("--out", default="output/reconnaissance/signature_eval.csv")
    parser.add_argument("--scores-out", default="output/reconnaissance/signature_scores.csv")
    parser.add_argument("--thresholds-out", default="output/reconnaissance/signature_thresholds.csv")
    parser.add_argument("--debug-dir", default="debug/signatures/validation")
    args = parser.parse_args()

    metrics = evaluate_signature_leave_one_out(
        args.signatures,
        args.threshold,
        scores_out=args.scores_out,
        thresholds_out=args.thresholds_out,
        debug_dir=args.debug_dir,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics))
        writer.writeheader()
        writer.writerow(metrics)
    for key, value in metrics.items():
        print(f"{key}: {value}")
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
