"""Smoke test for the graphical module on the provided sample images.

Usage:
    python graphical/run_graphical_demo.py
    python graphical/run_graphical_demo.py --image ../database/1/EXAM_FORM1_63272.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from graphical import read_page01_graphics, validate_cryptograms


EXPECTED_PAGE01 = {
    "EXAM_FORM1_63272.jpg": {
        "student_id": "63272",
        "group": "G02B",
        "conditions": {
            "Notes de cours": 1,
            "Notes manuscrites": 0,
            "Ordinateur portable": 1,
            "Calculatrice ": 0,
            "Feuilles brouillon": 1,
        },
    },
    "EXAM_FORM2_63272.jpg": {
        "student_id": "63272",
        "group": "G02B",
        "conditions": {
            "Notes de cours": 1,
            "Notes manuscrites": 1,
            "Ordinateur portable": 0,
            "Calculatrice ": 1,
            "Feuilles brouillon": 1,
        },
    },
    "EXAM_FORM3_63272.jpg": {
        "student_id": "63272",
        "group": "G02B",
        "conditions": {
            "Notes de cours": 0,
            "Notes manuscrites": 1,
            "Ordinateur portable": 0,
            "Calculatrice ": 1,
            "Feuilles brouillon": 2,
        },
    },
}


def default_database_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "database"
        if candidate.exists():
            return candidate
    return Path(__file__).resolve().parents[2] / "database"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=default_database_dir())
    parser.add_argument("--image", type=Path, default=None)
    parser.add_argument("--debug-dir", type=Path, default=PROJECT_DIR / "graphical_debug")
    args = parser.parse_args()

    if args.image is not None:
        image_paths = [args.image]
    else:
        image_paths = sorted(args.database.glob("*/*.jpg"))
    if not image_paths:
        raise SystemExit("No .jpg images found. Use --image or --database.")

    args.debug_dir.mkdir(parents=True, exist_ok=True)
    print(f"Images: {len(image_paths)}")
    all_ok = True
    cryptogram_inputs = []
    for path in image_paths:
        result = read_page01_graphics(path)
        cryptogram_inputs.append(path)
        rows = result.as_page01_rows(cryptogram_valid=1 if result.cryptogram else None)
        expected = EXPECTED_PAGE01.get(path.name)
        ok = True
        if expected is not None:
            ok &= result.student_id == expected["student_id"]
            ok &= result.group == expected["group"]
            ok &= result.conditions.as_page01_rows() == expected["conditions"]
        all_ok &= ok

        print(f"\n{path.name}")
        print(f"  student_id_grid: {result.student_id}  confidence={result.student_grid.confidence:.3f}")
        print(f"  group_grid:      {result.group}  confidence={result.group_grid.confidence:.3f}")
        print(f"  conditions:      {result.conditions.as_page01_rows()}")
        print(f"  max_numbers:     {result.conditions.max_numbers}")
        print(f"  cryptogram:      {'found' if result.cryptogram else 'missing'}")
        if expected is not None:
            print(f"  expected match:  {'OK' if ok else 'MISMATCH'}")

        save_debug_image(path, result, args.debug_dir / f"{path.stem}_debug.jpg")
        result.signature_crop.save(args.debug_dir / f"{path.stem}_signature_crop.jpg")
        if result.cryptogram is not None:
            result.cryptogram.crop.save(args.debug_dir / f"{path.stem}_cryptogram.jpg")

    if len(cryptogram_inputs) > 1:
        validation = validate_cryptograms(cryptogram_inputs)
        distances = ", ".join(f"{d:.3f}" for d in validation.distances) or "n/a"
        print(
            "\nCryptogram cross-check on these different sample forms: "
            f"{validation.valid}  distances={distances}"
        )
        print("  Note: validation is expected inside one multi-page PDF, not across different forms.")
    print(f"\nSample evaluation: {'OK' if all_ok else 'MISMATCH'}")


def save_debug_image(path: Path, result, output: Path) -> None:
    # Re-open full page for annotation.
    full = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(full)
    for box in result.student_grid.boxes.values():
        draw.rectangle((box.x0, box.y0, box.x1, box.y1), outline="blue", width=4)
    for box in result.group_grid.boxes.values():
        draw.rectangle((box.x0, box.y0, box.x1, box.y1), outline="green", width=4)
    if result.cryptogram is not None:
        box = result.cryptogram.box
        draw.rectangle((box.x0, box.y0, box.x1, box.y1), outline="orange", width=6)
    full.save(output, quality=90)


if __name__ == "__main__":
    main()
