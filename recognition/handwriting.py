from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import joblib
import numpy as np
from PIL import Image
from sklearn.datasets import load_digits
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC

from .image_utils import ImageInput, binarize_ink, crop_foreground, load_gray, split_connected_components


@dataclass(frozen=True)
class TextPrediction:
    text: str
    confidence: float
    status: str = "ok"
    debug_path: str = ""


class HandwrittenNumberRecognizer:
    """Basic recognizer for handwritten numbers.

    It is intentionally simple: characters are segmented with connected
    components, digits are classified by an SVM trained on sklearn's digits
    dataset, and punctuation is recognized by shape heuristics.
    """

    def __init__(self, min_confidence: float = 0.45, debug_dir: Optional[str] = None) -> None:
        self.classifier: SVC | None = None
        self.validation_accuracy: float | None = None
        self.min_confidence = min_confidence
        self.debug_dir = Path(debug_dir) if debug_dir else None

    def fit_default_digits(self, random_state: int = 42) -> "HandwrittenNumberRecognizer":
        digits = load_digits()
        images = digits.images.astype(np.float32)
        y = digits.target
        train_idx, val_idx = train_test_split(
            np.arange(len(images)), test_size=0.25, random_state=random_state, stratify=y
        )

        x_train = []
        y_train = []
        for idx in train_idx:
            for augmented in self._augment_digit_image(images[idx]):
                x_train.append(self._normalize_digit_array(augmented))
                y_train.append(y[idx])
        x_train = np.asarray(x_train, dtype=np.float32)
        y_train = np.asarray(y_train)
        x_val = np.asarray([self._normalize_digit_array(images[idx]) for idx in val_idx], dtype=np.float32)
        y_val = y[val_idx]

        clf = SVC(kernel="rbf", C=8.0, gamma="scale", probability=True, random_state=random_state)
        clf.fit(x_train, y_train)
        pred = clf.predict(x_val)
        self.validation_accuracy = float(accuracy_score(y_val, pred))
        self.classifier = clf
        return self

    def save(self, path: str) -> None:
        joblib.dump({"classifier": self.classifier, "validation_accuracy": self.validation_accuracy}, path)

    @classmethod
    def load(cls, path: str) -> "HandwrittenNumberRecognizer":
        data = joblib.load(path)
        model = cls()
        model.classifier = data["classifier"]
        model.validation_accuracy = data["validation_accuracy"]
        return model

    def predict_digit(self, image: ImageInput, debug_name: Optional[str] = None) -> TextPrediction:
        if self.classifier is None:
            self.fit_default_digits()
        debug_path = self._save_debug_image(image, debug_name or "digit_input.png")
        try:
            gray = load_gray(image)
            feat = self._prepare_digit_features(gray).reshape(1, -1)
        except Exception:
            return TextPrediction("", 0.0, "invalid_input", debug_path)
        probabilities = self.classifier.predict_proba(feat)[0]  # type: ignore[union-attr]
        idx = int(np.argmax(probabilities))
        confidence = float(probabilities[idx])
        status = "ok" if confidence >= self.min_confidence else "low_confidence"
        return TextPrediction(str(idx), confidence, status, debug_path)

    def predict_number(self, image: ImageInput, debug_name: Optional[str] = None) -> TextPrediction:
        if self.classifier is None:
            self.fit_default_digits()
        debug_path = self._save_debug_image(image, debug_name or "number_input.png")
        try:
            gray = load_gray(image)
        except Exception:
            return TextPrediction("", 0.0, "invalid_input", debug_path)
        if gray.size == 0 or min(gray.shape[:2]) < 4:
            return TextPrediction("", 0.0, "invalid_input", debug_path)
        binary = self._preprocess_number_binary(gray)
        binary = crop_foreground(binary, pad=2)
        chars = split_connected_components(binary, min_area=max(8, binary.size // 1200))
        if not chars:
            return TextPrediction("", 0.0, "failed", debug_path)

        pieces: list[str] = []
        confidences: list[float] = []
        for char_img in chars:
            h, w = char_img.shape
            area = float(char_img.mean())
            if h < 0.35 * binary.shape[0] and w < 0.25 * binary.shape[1] and area > 0:
                pieces.append(".")
                confidences.append(0.55)
                continue
            if h <= 4 and w >= 2 * h:
                pieces.append("-")
                confidences.append(0.55)
                continue
            pred = self.predict_digit((char_img * 255).astype(np.uint8))
            pieces.append(pred.text)
            confidences.append(pred.confidence)

        confidence = float(np.mean(confidences)) if confidences else 0.0
        status = "ok" if confidence >= self.min_confidence else "low_confidence"
        return TextPrediction("".join(pieces), confidence, status, debug_path)

    def _preprocess_number_binary(self, gray: np.ndarray) -> np.ndarray:
        gray = load_gray(gray)
        gray = cv2.medianBlur(gray, 3)
        binary = binarize_ink(gray, invert=True)
        if binary.size == 0:
            return binary
        h, w = binary.shape
        border = max(1, min(h, w) // 35)
        if h > 2 * border and w > 2 * border:
            binary[:border, :] = 0
            binary[-border:, :] = 0
            binary[:, :border] = 0
            binary[:, -border:] = 0
        kernel = np.ones((2, 2), dtype=np.uint8)
        binary = cv2.morphologyEx(binary.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        return binary

    def _prepare_digit_features(self, gray: np.ndarray) -> np.ndarray:
        gray = load_gray(gray).astype(np.float32)
        if gray.shape == (8, 8) and gray.max() <= 16.0:
            return self._normalize_digit_array(gray)

        border = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
        background = float(np.median(border))
        ink_intensity = 255.0 - gray if background > 127.0 else gray
        ink_intensity = np.clip(ink_intensity, 0.0, 255.0)
        _, mask = cv2.threshold(ink_intensity.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.count_nonzero(mask) == 0:
            return np.zeros(64, dtype=np.float32)

        cropped = self._crop_by_mask(ink_intensity, mask > 0, pad=2)
        digit = self._resize_gray_keep_ratio(cropped, (8, 8))
        if digit.max() > 0:
            digit = digit / digit.max() * 16.0
        return digit.astype(np.float32).reshape(-1)

    @staticmethod
    def _normalize_digit_array(image: np.ndarray) -> np.ndarray:
        digit = image.astype(np.float32)
        if digit.max() > 16.0:
            digit = digit / 255.0 * 16.0
        return np.clip(digit, 0.0, 16.0).reshape(-1)

    @staticmethod
    def _augment_digit_image(image: np.ndarray) -> list[np.ndarray]:
        transforms = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]
        augmented = []
        for dx, dy in transforms:
            matrix = np.float32([[1, 0, dx], [0, 1, dy]])
            shifted = cv2.warpAffine(image.astype(np.float32), matrix, (8, 8), borderValue=0)
            augmented.append(shifted)
        return augmented

    @staticmethod
    def _crop_by_mask(image: np.ndarray, mask: np.ndarray, pad: int) -> np.ndarray:
        ys, xs = np.where(mask)
        y0, y1 = max(0, ys.min() - pad), min(image.shape[0], ys.max() + pad + 1)
        x0, x1 = max(0, xs.min() - pad), min(image.shape[1], xs.max() + pad + 1)
        return image[y0:y1, x0:x1]

    @staticmethod
    def _resize_gray_keep_ratio(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
        target_w, target_h = size
        h, w = image.shape[:2]
        if h == 0 or w == 0:
            return np.zeros((target_h, target_w), dtype=np.float32)
        scale = min(target_w / w, target_h / h)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        resized = cv2.resize(image.astype(np.float32), (new_w, new_h), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((target_h, target_w), dtype=np.float32)
        y0 = (target_h - new_h) // 2
        x0 = (target_w - new_w) // 2
        canvas[y0 : y0 + new_h, x0 : x0 + new_w] = resized
        return canvas

    def _save_debug_image(self, image: ImageInput, filename: str) -> str:
        if self.debug_dir is None:
            return ""
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        path = self.debug_dir / self._safe_filename(filename)
        try:
            arr = load_gray(image)
            Image.fromarray(arr, mode="L").save(path)
            return str(path)
        except Exception:
            return ""

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(filename))
        return cleaned if cleaned.lower().endswith(".png") else f"{cleaned}.png"
