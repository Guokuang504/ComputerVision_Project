from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

from .handwriting import HandwrittenNumberRecognizer, TextPrediction
from .image_utils import ImageInput
from .ocr import OCRPrediction, PrintedTextRecognizer
from .signature import SignaturePrediction, SignatureRecognizer


@dataclass(frozen=True)
class RecognitionResult:
    student_id_signature: str = ""
    signature_confidence: float = 0.0
    signature_accepted: bool = False
    printed_fields: dict[str, OCRPrediction] = field(default_factory=dict)
    handwritten_fields: dict[str, TextPrediction] = field(default_factory=dict)


class RecognitionService:
    """Facade used by the integration code written by the other modules."""

    def __init__(
        self,
        signature_model: SignatureRecognizer,
        printed_ocr: Optional[PrintedTextRecognizer] = None,
        handwriting: Optional[HandwrittenNumberRecognizer] = None,
    ) -> None:
        self.signature_model = signature_model
        self.printed_ocr = printed_ocr or PrintedTextRecognizer()
        self.handwriting = handwriting or HandwrittenNumberRecognizer().fit_default_digits()

    @classmethod
    def from_signature_folder(
        cls,
        signatures_root: str,
        threshold: float = 0.82,
        ambiguous_margin: float = 0.02,
        debug_root: Optional[str] = None,
    ) -> "RecognitionService":
        signature_debug = str(Path(debug_root) / "signatures") if debug_root else None
        handwriting_debug = str(Path(debug_root) / "handwritten_digits") if debug_root else None
        sig = SignatureRecognizer(
            threshold=threshold,
            ambiguous_margin=ambiguous_margin,
            debug_dir=signature_debug,
        ).fit_from_folder(signatures_root)
        return cls(sig, handwriting=HandwrittenNumberRecognizer(debug_dir=handwriting_debug).fit_default_digits())

    def recognize_page_01(
        self,
        signature_crop: ImageInput,
        printed_crops: Optional[Mapping[str, ImageInput]] = None,
        handwritten_crops: Optional[Mapping[str, ImageInput]] = None,
    ) -> RecognitionResult:
        sig = self.recognize_signature(signature_crop)
        printed = {}
        for name, crop in (printed_crops or {}).items():
            printed[name] = self.printed_ocr.predict(crop)
        handwritten = {}
        for name, crop in (handwritten_crops or {}).items():
            handwritten[name] = self.handwriting.predict_number(crop, debug_name=f"{name}.png")
        return RecognitionResult(
            student_id_signature=sig.student_id if sig.accepted else "",
            signature_confidence=sig.confidence,
            signature_accepted=sig.accepted,
            printed_fields=printed,
            handwritten_fields=handwritten,
        )

    def recognize_signature(self, signature_crop: ImageInput) -> SignaturePrediction:
        return self.signature_model.predict(signature_crop)

    def recognize_handwritten_number(self, crop: ImageInput) -> TextPrediction:
        return self.handwriting.predict_number(crop)

    def recognize_printed_text(self, crop: ImageInput, whitelist: Optional[str] = None, psm: int = 7) -> OCRPrediction:
        return self.printed_ocr.predict(crop, whitelist=whitelist, psm=psm)

    def recognize_printed_field(self, crop: ImageInput, field_type: str) -> OCRPrediction:
        return self.printed_ocr.predict_field(crop, field_type)
