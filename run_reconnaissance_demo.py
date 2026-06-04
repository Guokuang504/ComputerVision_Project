from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from recognition import HandwrittenNumberRecognizer, RecognitionService, SignatureRecognizer
from config import SIGNATURE_THRESHOLD


ROOT = Path(__file__).resolve().parent
SIGNATURES = ROOT / "SIGNATURES"
MODEL_DIR = ROOT / "output" / "reconnaissance"


def make_text_image(text: str) -> np.ndarray:
    image = np.full((100, 500), 255, dtype=np.uint8)
    cv2.putText(image, text, (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0,), 3, cv2.LINE_AA)
    return image


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    signature_model = SignatureRecognizer(threshold=SIGNATURE_THRESHOLD).fit_from_folder(SIGNATURES)
    signature_model.save(MODEL_DIR / "signature_model.joblib")

    handwriting_model = HandwrittenNumberRecognizer().fit_default_digits()
    handwriting_model.save(MODEL_DIR / "handwriting_digits_svm.joblib")

    service = RecognitionService(signature_model, handwriting=handwriting_model)
    sample = next(SIGNATURES.rglob("*.png"))
    pred = service.recognize_signature(sample)
    print("sample_signature:", sample)
    print("predicted_student_id:", pred.student_id)
    print("confidence:", round(pred.confidence, 3))
    print("accepted:", pred.accepted)
    print("signature_status:", pred.status)
    print("handwriting_digit_validation_accuracy:", round(handwriting_model.validation_accuracy or 0.0, 3))
    print("tesseract_backend_available:", service.printed_ocr.has_backend)
    print("ocr_whitelist_fields:", sorted(service.printed_ocr.FIELD_WHITELISTS))
    for field_type, expected in [("code", "S1-01-G1"), ("student_id", "62034"), ("number", "3.745")]:
        ocr_pred = service.recognize_printed_field(make_text_image(expected), field_type)
        print(f"ocr_smoke_{field_type}:", ocr_pred.text, round(ocr_pred.confidence, 3), ocr_pred.backend)
    print("models_saved_to:", MODEL_DIR)


if __name__ == "__main__":
    main()
