from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_EXAM_NAME = "FORM1"

SIGNATURES_DIR = PROJECT_ROOT / "SIGNATURES"
RESULTS_SUFFIX = "_RESULTS"
DEBUG_DIR = PROJECT_ROOT / "debug"

SIGNATURE_THRESHOLD = 0.82
SIGNATURE_AMBIGUOUS_MARGIN = 0.02

HANDWRITING_MIN_CONFIDENCE = 0.45
QCM_CHECKED_THRESHOLD = 0.40


def exam_data_dir(exam_name: str) -> Path:
    return PROJECT_ROOT / exam_name


def results_dir(exam_name: str) -> Path:
    return PROJECT_ROOT / f"{exam_name}{RESULTS_SUFFIX}"


def ensure_runtime_dirs(exam_name: str) -> tuple[Path, Path]:
    out = results_dir(exam_name)
    out.mkdir(parents=True, exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["page01", "qcm", "handwritten_digits", "signatures"]:
        (DEBUG_DIR / name).mkdir(parents=True, exist_ok=True)
    return out, DEBUG_DIR
