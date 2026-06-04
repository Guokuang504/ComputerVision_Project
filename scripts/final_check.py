from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight final delivery checks.")
    parser.add_argument("--results-dir", default=None, help="Optional generated results folder to validate")
    parser.add_argument("--exam-root", default=None, help="Optional exam data folder used with --results-dir")
    args = parser.parse_args()

    checks = {
        "project_root": str(PROJECT_ROOT),
        "imports_ok": False,
        "required_paths": {},
        "datasets": [],
        "validation": None,
    }

    import config  # noqa: F401
    import data_discovery
    import debug_utils  # noqa: F401
    import excel_writer  # noqa: F401
    import recognition  # noqa: F401
    from code_partie2_elements_graphiques import read_exam_choices  # noqa: F401
    from validate_outputs import validate_results

    checks["imports_ok"] = True
    required = [
        "main.py",
        "config.py",
        "validate_outputs.py",
        "excel_writer.py",
        "debug_utils.py",
        "code_partie1_stucture_generale",
        "code_partie2_elements_graphiques",
        "recognition",
        "docs",
    ]
    checks["required_paths"] = {name: (PROJECT_ROOT / name).exists() for name in required}
    checks["datasets"] = [
        {
            "exam_name": ds.exam_name,
            "image_count": ds.image_count,
            "pdf_count": ds.pdf_count,
            "signature_count": ds.signature_count,
        }
        for ds in data_discovery.discover_datasets(PROJECT_ROOT)
    ]

    if args.results_dir:
        results_dir = Path(args.results_dir)
        if not results_dir.is_absolute():
            results_dir = PROJECT_ROOT / results_dir
        exam_root = Path(args.exam_root) if args.exam_root else None
        if exam_root is not None and not exam_root.is_absolute():
            exam_root = PROJECT_ROOT / exam_root
        checks["validation"] = validate_results(results_dir, exam_root)

    print(json.dumps(checks, indent=2, ensure_ascii=False))
    if not checks["imports_ok"] or not all(checks["required_paths"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
