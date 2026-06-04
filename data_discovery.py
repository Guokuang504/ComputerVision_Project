from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


@dataclass(frozen=True)
class ExamDataset:
    exam_name: str
    exam_root: Path
    presences_folder: Path
    pdf_folder: Path
    signatures_folder: Path
    results_folder: Path
    image_count: int
    pdf_count: int
    signature_count: int


def discover_datasets(project_root: str | Path = ".") -> list[ExamDataset]:
    root = Path(project_root).resolve()
    signatures = _find_signatures(root)
    datasets = []
    candidate_dirs = []
    for child in root.iterdir():
        if child.is_dir() and (child.name.startswith("FORM") or child.name.startswith("EXAM_FORM")):
            candidate_dirs.append(child)
    for folder in sorted(candidate_dirs):
        images = _count_files(folder, IMAGE_SUFFIXES)
        pdfs = _count_files(folder, {".pdf"})
        if images == 0 and pdfs == 0:
            continue
        exam_name = folder.name
        datasets.append(
            ExamDataset(
                exam_name=exam_name,
                exam_root=folder,
                presences_folder=folder,
                pdf_folder=folder,
                signatures_folder=signatures,
                results_folder=root / f"{exam_name}_RESULTS",
                image_count=images,
                pdf_count=pdfs,
                signature_count=sum(1 for p in signatures.rglob("*.png")) if signatures.exists() else 0,
            )
        )
    return datasets


def dataset_from_args(
    exam_name: str | None,
    exam_root: str | Path | None,
    signatures_dir: str | Path | None,
    results_dir: str | Path | None,
    project_root: str | Path = ".",
) -> ExamDataset:
    root = Path(project_root).resolve()
    if exam_root is not None:
        folder = Path(exam_root).resolve()
        name = exam_name or folder.name
    else:
        name = exam_name or "FORM1"
        folder = root / name
    signatures = Path(signatures_dir).resolve() if signatures_dir else _find_signatures(root)
    results = Path(results_dir).resolve() if results_dir else root / f"{name}_RESULTS"
    return ExamDataset(
        exam_name=name,
        exam_root=folder,
        presences_folder=folder,
        pdf_folder=folder,
        signatures_folder=signatures,
        results_folder=results,
        image_count=_count_files(folder, IMAGE_SUFFIXES),
        pdf_count=_count_files(folder, {".pdf"}),
        signature_count=sum(1 for p in signatures.rglob("*.png")) if signatures.exists() else 0,
    )


def _find_signatures(root: Path) -> Path:
    for name in ["STUDENT_CLASS_SIGNATURES", "SIGNATURES"]:
        candidate = root / name
        if candidate.exists():
            return candidate
    return root / "SIGNATURES"


def _count_files(folder: Path, suffixes: set[str]) -> int:
    if not folder.exists() or not folder.is_dir():
        return 0
    return sum(1 for p in folder.iterdir() if p.is_file() and p.suffix.lower() in suffixes)
