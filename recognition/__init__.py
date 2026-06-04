"""Recognition module for the IG.2405 2026 computer vision project."""

from .handwriting import HandwrittenNumberRecognizer
from .ocr import PrintedTextRecognizer
from .pipeline import RecognitionResult, RecognitionService
from .signature import SignatureRecognizer

__all__ = [
    "HandwrittenNumberRecognizer",
    "PrintedTextRecognizer",
    "RecognitionResult",
    "RecognitionService",
    "SignatureRecognizer",
]
