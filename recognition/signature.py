from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from PIL import Image
from skimage.feature import hog

from .image_utils import ImageInput, binarize_ink, crop_foreground, load_gray, resize_keep_ratio


@dataclass(frozen=True)
class SignaturePrediction:
    student_id: str
    confidence: float
    distance: float
    second_distance: float
    accepted: bool
    status: str = "matched"
    similarity_score: float = 0.0
    debug_path: str = ""


class SignatureRecognizer:
    """Signature identification using explainable bitmap descriptors.

    The model stores all reference samples and one centroid per student.
    Distances combine HOG descriptors at several scales and zoning densities.
    """

    DEFAULT_FEATURE_WEIGHTS = {
        "hog_8": 0.12,
        "hog_10": 0.20,
        "hog_12": 0.43,
        "hog_16": 0.10,
        "zones_6x12": 0.15,
    }

    def __init__(
        self,
        image_size: tuple[int, int] = (192, 96),
        threshold: float = 0.82,
        ambiguous_margin: float = 0.02,
        debug_dir: Optional[str] = None,
    ):
        self.image_size = image_size
        self.threshold = threshold
        self.ambiguous_margin = ambiguous_margin
        self.debug_dir = Path(debug_dir) if debug_dir else None
        self.feature_weights = dict(self.DEFAULT_FEATURE_WEIGHTS)
        self.student_ids: list[str] = []
        self.centroids: np.ndarray | None = None
        self.sample_features: np.ndarray | None = None
        self.sample_feature_sets: dict[str, np.ndarray] = {}
        self.sample_student_ids: list[str] = []
        self.sample_counts: dict[str, int] = {}

    def fit_from_folder(self, signatures_root: str) -> "SignatureRecognizer":
        root = Path(signatures_root)
        features: dict[str, list[dict[str, np.ndarray]]] = {}
        for path in sorted(root.rglob("*.png")):
            student_id = path.parent.name
            features.setdefault(student_id, []).append(self.extract_feature_sets(path))
        if not features:
            raise ValueError(f"No signature PNG files found under {root}")
        self.student_ids = sorted(features)
        flat_features = [self._combine_feature_sets(feat) for sid in self.student_ids for feat in features[sid]]
        self.centroids = np.vstack(
            [np.mean([self._combine_feature_sets(feat) for feat in features[sid]], axis=0) for sid in self.student_ids]
        )
        self.sample_features = np.vstack(flat_features)
        self.sample_feature_sets = {
            name: np.vstack([feat[name] for sid in self.student_ids for feat in features[sid]])
            for name in self.feature_weights
        }
        self.sample_student_ids = [sid for sid in self.student_ids for _ in features[sid]]
        self.sample_counts = {sid: len(features[sid]) for sid in self.student_ids}
        return self

    def save(self, path: str) -> None:
        joblib.dump(
            {
                "image_size": self.image_size,
                "threshold": self.threshold,
                "ambiguous_margin": self.ambiguous_margin,
                "feature_weights": self.feature_weights,
                "student_ids": self.student_ids,
                "centroids": self.centroids,
                "sample_features": self.sample_features,
                "sample_feature_sets": self.sample_feature_sets,
                "sample_student_ids": self.sample_student_ids,
                "sample_counts": self.sample_counts,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "SignatureRecognizer":
        data = joblib.load(path)
        model = cls(
            tuple(data["image_size"]),
            float(data["threshold"]),
            float(data.get("ambiguous_margin", 0.08)),
        )
        model.feature_weights = dict(data.get("feature_weights", cls.DEFAULT_FEATURE_WEIGHTS))
        model.student_ids = list(data["student_ids"])
        model.centroids = data["centroids"]
        model.sample_features = data.get("sample_features")
        model.sample_feature_sets = dict(data.get("sample_feature_sets", {}))
        model.sample_student_ids = list(data.get("sample_student_ids", []))
        model.sample_counts = dict(data["sample_counts"])
        return model

    def predict(self, image: ImageInput) -> SignaturePrediction:
        if not self.sample_student_ids:
            raise ValueError("SignatureRecognizer must be fitted before prediction")
        debug_path = self._save_debug_image(image, "input_signature.png")
        try:
            query_features = self.extract_feature_sets(image)
        except Exception:
            return SignaturePrediction("", 0.0, float("inf"), float("inf"), False, "invalid_input", 0.0, debug_path)
        distances = self._sample_distances(query_features)
        best_by_id: dict[str, float] = {}
        for sid, sample_distance in zip(self.sample_student_ids, distances):
            best_by_id[sid] = min(best_by_id.get(sid, float("inf")), float(sample_distance))
        ranked = sorted(best_by_id.items(), key=lambda item: item[1])
        best_sid, distance = ranked[0]
        second = float(ranked[1][1]) if len(ranked) > 1 else float("inf")
        confidence = float(max(0.0, min(1.0, 1.0 - distance / max(second, 1e-6))))
        similarity_score = float(max(0.0, 1.0 - distance))
        if distance > self.threshold:
            status = "rejected"
            accepted = False
        elif confidence < self.ambiguous_margin:
            status = "ambiguous"
            accepted = False
        else:
            status = "matched"
            accepted = True
        debug_path = self._save_debug_image(image, f"{status}_{best_sid}_{distance:.3f}.png")
        return SignaturePrediction(best_sid, confidence, distance, second, accepted, status, similarity_score, debug_path)

    def extract_features(self, image: ImageInput) -> np.ndarray:
        """Return one concatenated descriptor for compatibility and diagnostics."""
        return self._combine_feature_sets(self.extract_feature_sets(image))

    def extract_feature_sets(self, image: ImageInput) -> dict[str, np.ndarray]:
        gray = load_gray(image)
        if gray.size == 0 or min(gray.shape[:2]) < 8:
            raise ValueError("Invalid signature crop")
        binary = binarize_ink(gray, invert=True)
        binary = crop_foreground(binary, pad=12)
        binary = resize_keep_ratio(binary, self.image_size)
        return {
            "hog_8": self._hog_features(binary, 8),
            "hog_10": self._hog_features(binary, 10),
            "hog_12": self._hog_features(binary, 12),
            "hog_16": self._hog_features(binary, 16),
            "zones_6x12": self._zoning_features(binary, rows=6, cols=12),
        }

    def _sample_distances(self, query_features: dict[str, np.ndarray]) -> np.ndarray:
        if self.sample_feature_sets:
            distances = np.zeros(len(self.sample_student_ids), dtype=np.float32)
            for name, weight in self.feature_weights.items():
                samples = self.sample_feature_sets[name]
                distances += weight * np.linalg.norm(samples - query_features[name][None, :], axis=1)
            return distances
        if self.sample_features is None:
            raise ValueError("SignatureRecognizer has no fitted feature matrix")
        feat = self._combine_feature_sets(query_features)
        return np.linalg.norm(self.sample_features - feat[None, :], axis=1)

    def _combine_feature_sets(self, feature_sets: dict[str, np.ndarray]) -> np.ndarray:
        parts = [self.feature_weights[name] * feature_sets[name] for name in self.feature_weights]
        combined = np.concatenate(parts)
        norm = np.linalg.norm(combined)
        return (combined / (norm + 1e-8)).astype(np.float32)

    @staticmethod
    def _hog_features(binary: np.ndarray, cell_size: int) -> np.ndarray:
        descriptor = hog(
            binary.astype(np.float32),
            orientations=9,
            pixels_per_cell=(cell_size, cell_size),
            cells_per_block=(2, 2),
            block_norm="L2-Hys",
            feature_vector=True,
        )
        norm = np.linalg.norm(descriptor)
        return (descriptor / (norm + 1e-8)).astype(np.float32)

    def _save_debug_image(self, image: ImageInput, filename: str) -> str:
        if self.debug_dir is None:
            return ""
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        path = self.debug_dir / filename
        try:
            arr = load_gray(image)
            Image.fromarray(arr, mode="L").save(path)
            return str(path)
        except Exception:
            return ""

    @staticmethod
    def _zoning_features(binary: np.ndarray, rows: int, cols: int) -> np.ndarray:
        zones = []
        y_groups = np.array_split(np.arange(binary.shape[0]), rows)
        x_groups = np.array_split(np.arange(binary.shape[1]), cols)
        for ys in y_groups:
            for xs in x_groups:
                zones.append(float(binary[np.ix_(ys, xs)].mean()))
        descriptor = np.asarray(zones, dtype=np.float32)
        norm = np.linalg.norm(descriptor)
        return (descriptor / (norm + 1e-8)).astype(np.float32)
