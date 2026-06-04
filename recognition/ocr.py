from __future__ import annotations

import shutil
import subprocess
import tempfile
import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .image_utils import ImageInput, load_gray


@dataclass(frozen=True)
class OCRPrediction:
    text: str
    confidence: float
    backend: str
    status: str = "ok"
    debug_path: str = ""


class PrintedTextRecognizer:
    """Printed-text OCR wrapper with graceful fallback.

    The project statement allows higher-level functions for printed text. This
    class uses the local Tesseract binary when available. If no OCR backend is
    installed, it returns an empty low-confidence prediction instead of crashing.
    """

    FIELD_WHITELISTS = {
        "code": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
        "date": "0123456789/",
        "module": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.",
        "name": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-",
        "number": "0123456789.,-",
        "student_id": "0123456789",
        "unit": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    }

    FIELD_PSM = {
        "code": 7,
        "date": 7,
        "module": 7,
        "name": 7,
        "number": 8,
        "student_id": 8,
        "unit": 8,
    }

    def __init__(self, language: str = "eng", min_confidence: float = 0.30) -> None:
        self.language = language
        self.min_confidence = min_confidence
        self.tesseract_path = self._find_tesseract()

    @property
    def has_backend(self) -> bool:
        return self.tesseract_path is not None

    @staticmethod
    def _find_tesseract() -> Optional[str]:
        """Find Tesseract even when Windows has not refreshed PATH yet."""
        path = shutil.which("tesseract")
        if path:
            return path
        for candidate in (
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ):
            if candidate.exists():
                return str(candidate)
        return None

    def predict(self, image: ImageInput, whitelist: Optional[str] = None, psm: int = 7) -> OCRPrediction:
        try:
            gray = load_gray(image)
        except Exception:
            return OCRPrediction("", 0.0, "none", "invalid_input")
        prepared = self._prepare(gray)
        if self.tesseract_path:
            return self._predict_tesseract(prepared, whitelist, psm)
        return OCRPrediction("", 0.0, "none", "ocr_unavailable")

    def predict_field(self, image: ImageInput, field_type: str) -> OCRPrediction:
        """Run OCR with a predefined whitelist for common exam fields."""
        prediction = self.predict(
            image,
            whitelist=self.FIELD_WHITELISTS.get(field_type),
            psm=self.FIELD_PSM.get(field_type, 7),
        )
        return OCRPrediction(
            self._normalize_field_text(prediction.text, field_type),
            prediction.confidence,
            prediction.backend,
            prediction.status,
            prediction.debug_path,
        )

    def _prepare(self, gray: np.ndarray) -> np.ndarray:
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    def _predict_tesseract(self, gray: np.ndarray, whitelist: Optional[str], psm: int) -> OCRPrediction:
        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "ocr.png"
            ok, encoded = cv2.imencode(".png", gray)
            if not ok:
                return OCRPrediction("", 0.0, "tesseract", "failed")
            encoded.tofile(str(img_path))
            cmd = [
                self.tesseract_path or "tesseract",
                str(img_path),
                "stdout",
                "-l",
                self.language,
                "--oem",
                "1",
                "--psm",
                str(psm),
            ]
            if whitelist:
                cmd.extend(["-c", f"tessedit_char_whitelist={whitelist}"])
            cmd.append("tsv")
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                return OCRPrediction("", 0.0, "tesseract", "failed")
            text, confidence = self._parse_tesseract_tsv(proc.stdout, whitelist)
            if not text:
                status = "failed"
            elif confidence < self.min_confidence:
                status = "low_confidence"
            else:
                status = "ok"
            return OCRPrediction(text, confidence, "tesseract", status)

    @staticmethod
    def _parse_tesseract_tsv(tsv: str, whitelist: Optional[str]) -> tuple[str, float]:
        reader = csv.DictReader(io.StringIO(tsv), delimiter="\t")
        texts = []
        confidences = []
        for row in reader:
            text = (row.get("text") or "").strip()
            if not text:
                continue
            try:
                conf = float(row.get("conf") or -1)
            except ValueError:
                conf = -1.0
            if conf < 0:
                continue
            texts.append(text)
            confidences.append(conf / 100.0)
        if not texts:
            return "", 0.0
        separator = "" if whitelist and " " not in whitelist else " "
        return separator.join(texts).strip(), float(np.mean(confidences))

    @staticmethod
    def _normalize_field_text(text: str, field_type: str) -> str:
        cleaned = text.strip()
        if field_type in {"code", "student_id", "module", "number", "unit"}:
            cleaned = cleaned.replace(" ", "")
        if field_type == "module":
            normalized = cleaned.upper().replace("|", "I").replace("L", "I")
            match = re.search(r"[I1]G[.\-]?\d{4}", normalized)
            if match:
                value = match.group(0).replace("1G", "IG").replace("-", ".")
                if "." not in value:
                    value = value[:2] + "." + value[2:]
                return value
        if field_type == "date":
            match = re.search(r"\d{1,2}/\d{1,2}/\d{4}", cleaned)
            if match:
                return match.group(0)
        if field_type == "code":
            normalized = cleaned.upper().replace(" ", "")
            match = re.search(r"[S5328]\d-\d{2}-G\d", normalized)
            if match:
                value = match.group(0)
                if value[0] != "S":
                    value = "S" + value[1:]
                return value
            return normalized
        if field_type == "name":
            cleaned = re.sub(r"[^A-Za-zÀ-ÿ-]", "", cleaned).upper()
        if field_type == "number":
            cleaned = cleaned.replace(",", ".")
            if "." in cleaned:
                cleaned = cleaned.rstrip("0").rstrip(".")
        return cleaned
