"""Graphical-form reading module for the IG.2405 computer-vision project."""

from .cryptogram import (
    CryptogramResult,
    CryptogramValidation,
    cryptogram_distance,
    extract_cryptogram,
    validate_cryptograms,
)
from .exam import ExamQuestionChoices, read_exam_choices
from .page01 import (
    ConditionResult,
    GridReadResult,
    Page01Graphics,
    crop_signature,
    read_exam_conditions,
    read_group_grid,
    read_page01_graphics,
    read_student_id_grid,
)
from .preprocess import binary_morphology, deskew_image, estimate_skew_angle, otsu_threshold

__all__ = [
    "ConditionResult",
    "CryptogramResult",
    "CryptogramValidation",
    "ExamQuestionChoices",
    "GridReadResult",
    "Page01Graphics",
    "binary_morphology",
    "crop_signature",
    "cryptogram_distance",
    "deskew_image",
    "estimate_skew_angle",
    "extract_cryptogram",
    "otsu_threshold",
    "read_exam_choices",
    "read_exam_conditions",
    "read_group_grid",
    "read_page01_graphics",
    "read_student_id_grid",
    "validate_cryptograms",
]
