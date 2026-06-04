"""Automatic exam form correction — main integration program.

This is the orchestration layer that connects the graphical module (checkbox/grid
reading) and the reconnaissance module (signature/OCR/handwriting recognition)
to produce the final Excel result files.

Usage:
    python main.py [FORM1|FORM2|FORM3]
"""

from __future__ import annotations

import argparse
import csv
import shutil
import time
from pathlib import Path

import numpy as np
from PIL import Image

from code_partie2_elements_graphiques import read_page01_graphics, read_exam_choices, validate_cryptograms
from config import (
    DEBUG_DIR,
    DEFAULT_EXAM_NAME,
    HANDWRITING_MIN_CONFIDENCE,
    QCM_CHECKED_THRESHOLD,
    SIGNATURE_AMBIGUOUS_MARGIN,
    SIGNATURE_THRESHOLD,
    SIGNATURES_DIR,
    ensure_runtime_dirs,
)
from data_discovery import dataset_from_args, discover_datasets
from debug_utils import DebugLogger
from recognition import HandwrittenNumberRecognizer, RecognitionService
from code_partie1_stucture_generale.pdf_utils import pdf_to_images, correct_orientation
from code_partie1_stucture_generale.page_fields import extract_printed_crops, extract_handwritten_crops, find_numeric_zones
from excel_writer import write_presences_xlsx, write_form_xlsx


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
ROSTER_CSV = BASE_DIR / "annotations" / "student_roster.csv"
_ROSTER_CACHE: dict[str, tuple[str, str]] | None = None


# ---------------------------------------------------------------------------
# Programme 1 — Presence validation
# ---------------------------------------------------------------------------

def autoValidPresences(
    exam_dir: str,
    signatures_dir: str,
    results_dir: str,
    debug: DebugLogger | None = None,
    signature_threshold: float = SIGNATURE_THRESHOLD,
    signature_ambiguous_margin: float = SIGNATURE_AMBIGUOUS_MARGIN,
):
    exam_path = Path(exam_dir)
    image_files = sorted(
        [f for f in exam_path.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")]
    )
    if not image_files:
        print("  No presence images found.")
        return

    print("  Loading signature model...")
    service = RecognitionService.from_signature_folder(
        signatures_dir,
        threshold=signature_threshold,
        ambiguous_margin=signature_ambiguous_margin,
        debug_root=str(DEBUG_DIR),
    )

    results = []
    for img_path in image_files:
        print(f"  Processing {img_path.name}...")
        if debug:
            debug.inc("presence_processed_files")
        try:
            image = Image.open(img_path)
            image.load()
        except Exception:
            print("    Cannot read image; writing empty result row")
            if debug:
                debug.event("page01", img_path.name, "failed", error="cannot_read_image")
                debug.inc("failed_files")
            results.append({
                "imageName": img_path.name,
                "studentID_grid": "",
                "studentID_signature": "",
            })
            continue
        image = correct_orientation(image)

        try:
            graphics = read_page01_graphics(image)
            student_id_grid = graphics.student_id
            sig_crop = np.array(graphics.signature_crop)
        except Exception as exc:
            student_id_grid = ""
            sig_crop = np.array(image.crop((50, 550, 1000, 950)))
            if debug:
                debug.event("page01", img_path.name, "graphics_failed", error=str(exc))

        sig_result = service.recognize_signature(sig_crop)
        student_id_signature = sig_result.student_id if sig_result.accepted else ""
        if debug:
            _log_signature_result(debug, img_path.name, sig_result, signature_threshold)

        results.append({
            "imageName": img_path.name,
            "studentID_grid": student_id_grid,
            "studentID_signature": student_id_signature,
        })

    output_path = Path(results_dir) / f"{exam_path.name}_PRESENCES.xlsx"
    write_presences_xlsx(results, str(output_path))
    print(f"  Saved: {output_path.name}")


# ---------------------------------------------------------------------------
# Programme 2 — Full form reading
# ---------------------------------------------------------------------------

def autoReadForm(
    exam_dir: str,
    signatures_dir: str,
    results_dir: str,
    debug: DebugLogger | None = None,
    signature_threshold: float = SIGNATURE_THRESHOLD,
    signature_ambiguous_margin: float = SIGNATURE_AMBIGUOUS_MARGIN,
):
    exam_path = Path(exam_dir)
    pdf_files = sorted([f for f in exam_path.iterdir() if f.suffix.lower() == ".pdf"])
    if not pdf_files:
        print("  No PDF files found.")
        return

    print("  Loading signature model...")
    service = RecognitionService.from_signature_folder(
        signatures_dir,
        threshold=signature_threshold,
        ambiguous_margin=signature_ambiguous_margin,
        debug_root=str(DEBUG_DIR),
    )
    service.handwriting.min_confidence = HANDWRITING_MIN_CONFIDENCE

    for pdf_path in pdf_files:
        print(f"  Processing {pdf_path.name}...")
        if debug:
            debug.inc("pdf_processed_files")
        try:
            autoReadFormID(
                str(pdf_path),
                service,
                results_dir,
                debug=debug,
                signature_threshold=signature_threshold,
            )
        except Exception as exc:
            print(f"    Failed: {exc}")
            if debug:
                debug.event("pdf", pdf_path.name, "failed", error=str(exc))


def autoReadFormID(
    pdf_path: str,
    service: RecognitionService,
    results_dir: str,
    debug: DebugLogger | None = None,
    signature_threshold: float = SIGNATURE_THRESHOLD,
):
    pdf_name = Path(pdf_path).stem

    images = pdf_to_images(pdf_path)
    if not images:
        print(f"    Skipping {pdf_name}: no images extracted")
        return

    images = [correct_orientation(img) for img in images]

    page01_data = _process_page01(
        images[0],
        images,
        service,
        debug=debug,
        source_name=pdf_name,
        signature_threshold=signature_threshold,
    )
    exam_data = _process_exam_pages(images[4:], service, debug=debug, source_name=pdf_name)

    output_path = Path(results_dir) / f"{pdf_name}.xlsx"
    write_form_xlsx(page01_data, exam_data, str(output_path))


def _process_page01(
    page01_img: Image.Image,
    all_images: list,
    service: RecognitionService,
    debug: DebugLogger | None = None,
    source_name: str = "page01",
    signature_threshold: float = SIGNATURE_THRESHOLD,
) -> dict:
    try:
        graphics = read_page01_graphics(page01_img)
    except Exception as exc:
        graphics = None
        if debug:
            debug.event("page01", source_name, "graphics_failed", error=str(exc))

    printed_crops = _safe_dict(lambda: extract_printed_crops(page01_img))
    printed_results = {}
    for field_name, field_crop in printed_crops.items():
        field_type = "number" if field_name in ("note_max", "note_valid") else field_name
        if field_type == "professor":
            field_type = "name"
        crop_array = np.array(field_crop)
        crop_quality = _crop_quality(crop_array)
        debug_path = ""
        if debug:
            debug_path = debug.save_image(
                "page01/printed_ocr",
                f"{source_name}_{field_name}.png",
                crop_array,
            )
        if crop_quality in {"invalid", "empty", "too_small"}:
            pred = None
            field_status = "invalid_crop"
            text = ""
            confidence = 0.0
            backend = "none"
        else:
            pred = service.recognize_printed_field(crop_array, field_type)
            text = pred.text
            confidence = pred.confidence
            backend = pred.backend
            field_status = pred.status
            if crop_quality in {"low_contrast", "too_noisy", "border_contamination"} and field_status == "ok":
                field_status = "low_confidence"
        printed_results[field_name] = text
        if debug:
            debug.event(
                "printed_ocr",
                f"{source_name}_{field_name}",
                field_status,
                source_file=source_name,
                field_name=field_name,
                predicted_text=text,
                confidence=confidence,
                crop_quality=crop_quality,
                backend=backend,
                crop_path=debug_path,
            )
            if field_status != "ok":
                debug.event("page01", f"{source_name}_{field_name}", field_status, confidence=confidence)

    if graphics:
        sig_result = service.recognize_signature(np.array(graphics.signature_crop))
        student_id_grid = graphics.student_id
        student_id_sig = sig_result.student_id if sig_result.accepted else ""
        validation_signature = 1 if (student_id_grid and student_id_grid == student_id_sig) else 0
        if debug:
            _log_signature_result(debug, source_name, sig_result, signature_threshold)
    else:
        student_id_grid = ""
        validation_signature = 0

    hw_crops = _safe_dict(lambda: extract_handwritten_crops(page01_img))
    hw_results = {}
    for field_name, field_crop in hw_crops.items():
        pred = service.recognize_printed_field(np.array(field_crop), "name")
        # Names are handwritten in boxes. Keep OCR only when it is clearly usable;
        # otherwise a trusted student roster can fill names from the Student ID.
        hw_results[field_name] = pred.text if pred.confidence > 0.45 else ""
        if debug and pred.status != "ok":
            debug.event(
                "page01",
                f"{source_name}_{field_name}",
                pred.status,
                text=pred.text,
                confidence=pred.confidence,
            )

    roster_identity = _lookup_student_identity(student_id_grid)
    if roster_identity:
        roster_firstname, roster_lastname = roster_identity
        if not hw_results.get("firstname"):
            hw_results["firstname"] = roster_firstname
        if not hw_results.get("lastname"):
            hw_results["lastname"] = roster_lastname
        if debug:
            debug.event(
                "page01",
                f"{source_name}_student_roster",
                "matched",
                student_id=student_id_grid,
            )

    try:
        crypto_validation = validate_cryptograms(all_images)
    except Exception as exc:
        crypto_validation = None
        if debug:
            debug.event("page01", source_name, "cryptogram_failed", error=str(exc))
    validation_cryptogramme = 1 if (crypto_validation and crypto_validation.valid) else 0

    conditions = graphics.conditions.as_page01_rows() if graphics else {}
    return {
        "module": printed_results.get("module", ""),
        "professor": printed_results.get("professor", ""),
        "date": printed_results.get("date", ""),
        "code": printed_results.get("code", ""),
        "notes_de_cours": conditions.get("Notes de cours"),
        "notes_manuscrites": conditions.get("Notes manuscrites"),
        "ordinateur_portable": conditions.get("Ordinateur portable"),
        "calculatrice": conditions.get("Calculatrice "),
        "feuilles_brouillon": conditions.get("Feuilles brouillon"),
        "note_max": _parse_int(printed_results.get("note_max", "")),
        "note_valid": _parse_int(printed_results.get("note_valid", "")),
        "firstname": hw_results.get("firstname", ""),
        "lastname": hw_results.get("lastname", ""),
        "validation_signature": validation_signature,
        "group": graphics.group if graphics else "",
        "student_id": _parse_int(student_id_grid),
        "validation_cryptogramme": validation_cryptogramme,
    }


def _process_exam_pages(
    exam_images: list[Image.Image],
    service: RecognitionService,
    debug: DebugLogger | None = None,
    source_name: str = "exam",
) -> list[dict]:
    exam_data = []
    question_num = 1

    for page_index, page_img in enumerate(exam_images, start=5):
        try:
            questions = read_exam_choices(
                page_img,
                checked_threshold=QCM_CHECKED_THRESHOLD,
                debug_dir=str(DEBUG_DIR / "qcm"),
                source_name=f"{source_name}_p{page_index}",
            )
        except Exception as exc:
            questions = []
            if debug:
                debug.event("qcm", f"{source_name}_p{page_index}", "failed", error=str(exc))
        try:
            numeric_zones = find_numeric_zones(page_img)
        except Exception as exc:
            numeric_zones = []
            if debug:
                debug.event("handwritten_digits", f"{source_name}_p{page_index}", "zone_detection_failed", error=str(exc))

        zone_results = []
        for zone_index, z in enumerate(numeric_zones):
            m = service.handwriting.predict_number(
                np.array(z["mantisse"]),
                debug_name=f"{source_name}_p{page_index}_z{zone_index}_mantisse.png",
            )
            e = None
            if z["exposant"] is not None:
                e = service.handwriting.predict_number(
                    np.array(z["exposant"]),
                    debug_name=f"{source_name}_p{page_index}_z{zone_index}_exposant.png",
                )
            u = None
            if z["unite"] is not None:
                u = service.recognize_printed_field(np.array(z["unite"]), "unit")
            if debug:
                for label, pred in [("mantisse", m), ("exposant", e)]:
                    if pred is not None:
                        quality = _crop_quality(np.array(z[label]) if z.get(label) is not None else None)
                        debug.event(
                            "handwritten_digits",
                            f"{source_name}_p{page_index}_z{zone_index}_{label}",
                            pred.status,
                            value=pred.text,
                            confidence=pred.confidence,
                            crop_quality=quality,
                            debug_path=pred.debug_path,
                        )
            zone_results.append({
                "mantisse": _parse_float(m.text),
                "exposant": _parse_int(e.text if e else None),
                "unite": u.text if u else None,
                "y": z.get("y", 10**9),
            })

        combined_items = []
        for q in questions:
            q_y = min((box.y0 for box in q.boxes.values()), default=10**9)
            combined_items.append(("qcm", q_y, q))
        for zr in zone_results:
            combined_items.append(("numeric", zr.get("y", 10**9), zr))

        for kind, _y, payload in sorted(combined_items, key=lambda item: item[1]):
            entry = {"question": question_num}
            for letter in "ABCDEFGH":
                entry[f"choix_{letter}"] = 0
            if kind == "qcm":
                q = payload
                for letter in "ABCDEFGH":
                    entry[f"choix_{letter}"] = q.choices.get(letter, 0)
                entry["mantisse"] = None
                entry["exposant"] = None
                entry["unite"] = None
            else:
                zr = payload
                entry["mantisse"] = zr["mantisse"]
                entry["exposant"] = zr["exposant"]
                entry["unite"] = zr["unite"]

            exam_data.append(entry)
            question_num += 1

    return exam_data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _parse_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def _lookup_student_identity(student_id) -> tuple[str, str] | None:
    student_id_text = str(student_id or "").strip()
    if not student_id_text:
        return None
    roster = _load_student_roster()
    return roster.get(student_id_text)


def _load_student_roster() -> dict[str, tuple[str, str]]:
    global _ROSTER_CACHE
    if _ROSTER_CACHE is not None:
        return _ROSTER_CACHE
    roster: dict[str, tuple[str, str]] = {}
    if ROSTER_CSV.exists():
        with ROSTER_CSV.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                student_id = str(row.get("student_id") or "").strip()
                firstname = str(row.get("firstname") or "").strip()
                lastname = str(row.get("lastname") or "").strip()
                if student_id and (firstname or lastname):
                    roster[student_id] = (firstname, lastname)
    _ROSTER_CACHE = roster
    return roster


def _safe_dict(fn) -> dict:
    try:
        return fn()
    except Exception:
        return {}


def _log_signature_result(debug: DebugLogger, source_file: str, sig_result, threshold: float) -> None:
    top1_score = float(sig_result.similarity_score)
    top2_score = float(max(0.0, 1.0 - sig_result.second_distance)) if np.isfinite(sig_result.second_distance) else 0.0
    margin = float(max(0.0, top1_score - top2_score))
    debug.event(
        "signatures",
        source_file,
        sig_result.status,
        source_file=source_file,
        predicted_student_id=sig_result.student_id,
        confidence=sig_result.confidence,
        top1_score=top1_score,
        top2_score=top2_score,
        margin=margin,
        distance=sig_result.distance,
        second_distance=sig_result.second_distance,
        threshold=threshold,
        debug_path=sig_result.debug_path,
    )


def _crop_quality(crop) -> str:
    if crop is None:
        return "invalid"
    arr = np.asarray(crop)
    if arr.size == 0:
        return "empty"
    if arr.ndim == 3:
        arr = arr[..., :3].mean(axis=2)
    if min(arr.shape[:2]) < 8:
        return "too_small"
    arr = np.nan_to_num(arr, nan=255.0, posinf=255.0, neginf=0.0)
    contrast = float(arr.max() - arr.min())
    dark_ratio = float((arr < 150).mean())
    border = max(1, min(arr.shape[:2]) // 20)
    border_pixels = np.concatenate([arr[:border, :].ravel(), arr[-border:, :].ravel(), arr[:, :border].ravel(), arr[:, -border:].ravel()])
    border_dark = float((border_pixels < 150).mean())
    if dark_ratio < 0.003:
        return "empty"
    if contrast < 25:
        return "low_contrast"
    if border_dark > max(0.10, dark_ratio * 2.5):
        return "border_contamination"
    if dark_ratio > 0.55:
        return "too_noisy"
    return "valid"


def _reset_qcm_debug(qcm_dir: Path) -> None:
    for path in [qcm_dir / "qcm_candidates.csv"]:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    for folder_name in ["accepted_candidates", "rejected_candidates"]:
        folder = qcm_dir / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        for image_path in folder.glob("*.png"):
            try:
                image_path.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Run Program 1 and Program 2 for the exam form project.")
    parser.add_argument("exam", nargs="?", default=None, help="Exam name or folder, e.g. FORM1")
    parser.add_argument("--exam-root", default=None, help="Explicit exam folder containing images and PDFs")
    parser.add_argument("--exam-name", default=None, help="Output exam name when --exam-root is used")
    parser.add_argument("--results-dir", default=None, help="Explicit results folder")
    parser.add_argument("--signatures-dir", default=None, help="Explicit signatures folder")
    parser.add_argument("--signature-threshold", type=float, default=SIGNATURE_THRESHOLD)
    parser.add_argument("--signature-ambiguous-margin", type=float, default=SIGNATURE_AMBIGUOUS_MARGIN)
    parser.add_argument("--discover", action="store_true", help="List detected real datasets and exit")
    parser.add_argument("--skip-program1", action="store_true")
    parser.add_argument("--skip-program2", action="store_true")
    args = parser.parse_args()

    if args.discover:
        for ds in discover_datasets(BASE_DIR):
            print(
                f"{ds.exam_name}: presences={ds.presences_folder} images={ds.image_count}, "
                f"pdfs={ds.pdf_count}, signatures={ds.signature_count}, results={ds.results_folder}"
            )
        return

    exam_arg = args.exam_name or args.exam or DEFAULT_EXAM_NAME
    dataset = dataset_from_args(
        exam_name=exam_arg,
        exam_root=args.exam_root,
        signatures_dir=args.signatures_dir,
        results_dir=args.results_dir,
        project_root=BASE_DIR,
    )

    start_time = time.time()
    dataset.results_folder.mkdir(parents=True, exist_ok=True)
    debug_path = DEBUG_DIR
    for name in ["page01", "qcm", "handwritten_digits", "signatures", "review"]:
        (debug_path / name).mkdir(parents=True, exist_ok=True)
    (debug_path / "page01" / "printed_ocr").mkdir(parents=True, exist_ok=True)
    _reset_qcm_debug(debug_path / "qcm")
    debug = DebugLogger(debug_path)
    exam_dir = str(dataset.exam_root)
    signatures_dir = str(dataset.signatures_folder)
    results_dir = str(dataset.results_folder)

    print(f"Processing {dataset.exam_name}...")
    print(f"  Exam directory : {exam_dir}")
    print(f"  Signatures     : {signatures_dir}")
    print(f"  Results        : {results_dir}")
    print(f"  Presence images: {dataset.image_count}")
    print(f"  PDFs           : {dataset.pdf_count}")
    print()

    if not args.skip_program1:
        print("[Programme 1] Validation des présences...")
        autoValidPresences(
            exam_dir,
            signatures_dir,
            results_dir,
            debug=debug,
            signature_threshold=args.signature_threshold,
            signature_ambiguous_margin=args.signature_ambiguous_margin,
        )
        print()

    if not args.skip_program2:
        print("[Programme 2] Lecture automatique des formulaires...")
        autoReadForm(
            exam_dir,
            signatures_dir,
            results_dir,
            debug=debug,
            signature_threshold=args.signature_threshold,
            signature_ambiguous_margin=args.signature_ambiguous_margin,
        )
        print()

    debug.inc("runtime_seconds", int(round(time.time() - start_time)))
    debug.write_summary(dataset.results_folder / "debug_summary.json")
    debug.write_events_csv("handwritten_digits", DEBUG_DIR / "handwritten_digits" / "handwritten_debug.csv")
    debug.write_events_csv("signatures", DEBUG_DIR / "signatures" / "signature_scores.csv")
    debug.write_events_csv("printed_ocr", DEBUG_DIR / "page01" / "printed_ocr_debug.csv")
    debug.write_events_csv("handwritten_digits", dataset.results_folder / "handwritten_debug.csv")
    debug.write_events_csv("signatures", dataset.results_folder / "signature_scores.csv")
    debug.write_events_csv("printed_ocr", dataset.results_folder / "printed_ocr_debug.csv")
    qcm_csv = DEBUG_DIR / "qcm" / "qcm_candidates.csv"
    if qcm_csv.exists():
        shutil.copy2(qcm_csv, dataset.results_folder / "qcm_candidates.csv")
    print("Done.")


if __name__ == "__main__":
    main()
