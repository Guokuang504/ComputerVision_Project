# Final Project Integration Summary

## Structure Audit

Current integrated modules:

- `code_partie1_stucture_generale/`: orchestration, PDF rendering, page field crops, Program 1 and Program 2 flow.
- `code_partie2_elements_graphiques/`: low-level graphical reading for PAGE-01 grids, condition checkboxes, cryptograms, and exam QCM boxes.
- `recognition/`: signature matching, printed OCR, handwritten number recognition, and evaluation scripts.
- `config.py`: centralized paths and thresholds.
- `excel_writer.py`: required `.xlsx` outputs for Program 1 and Program 2.
- `main.py`: root entry point. Run with `python3 main.py FORM1`.

Potential conflicts fixed:

- `graphical` and `reconnaissance` imports were replaced by direct project package imports.
- Missing `excel_writer.py` was added.
- Results/debug paths are centralized instead of hard-coded to a missing `database/` folder.
- Python 3.9 runtime type-alias issue in the graphical module was fixed.

## Robustness Changes

- PAGE-01 graphical reading now handles `None`, empty arrays, `NaN`, `inf`, missing grids, all-NaN scores, failed cryptogram extraction, and failed signature-box detection.
- Batch processing catches per-file exceptions and continues.
- Invalid crops return empty values, low confidence, or `status="invalid_input"` instead of stopping the batch.
- Excel generation writes empty cells for failed fields instead of failing.

## QCM and Numeric Fields

- QCM detection remains low-level: thresholding, connected components, geometry filters, clustering, and fill-ratio scoring.
- Checkbox candidates are now filtered by:
  - area and side length,
  - width/height ratio,
  - expected page bounds,
  - rectangular border score,
  - relative size consistency,
  - vertical A-D stack regularity for real FORM pages,
  - row/column regularity as fallback.
- Numeric answer rectangles are handled separately by `find_numeric_zones`.
- `debug/qcm/qcm_candidates.csv` records `x`, `y`, `w`, `h`, `area`, `aspect_ratio`, `fill_ratio`, `page_zone`, and accepted/rejected reason.

## Recognition Updates

- Handwritten numbers now apply grayscale normalization, binarization, median denoising, border removal, morphology opening, connected components, padding/resize, and confidence status.
- Debug crops for handwritten numbers are saved under `debug/handwritten_digits/`.
- Signature matching returns `predicted_student_id`, `confidence`, `distance`, `similarity_score`, `status`, and `debug_path`.
- Signature validation now writes:
  - `output/reconnaissance/signature_eval.csv`
  - `output/reconnaissance/signature_scores.csv`
  - `output/reconnaissance/signature_thresholds.csv`
  - grouped debug samples under `debug/signatures/validation/`

Current signature validation at `threshold=0.82`, `ambiguous_margin=0.02`:

- Top-1 accuracy: `0.8598`
- Accepted-correct rate: `0.7172`
- Accepted-wrong rate: `0.0377`
- Rejection rate: `0.2148`
- Ambiguous rate: `0.0303`

## Real Data Verification

Final full regression commands:

```bash
python3 main.py FORM1 --results-dir output/verification_FORM1_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM1_FINAL --exam-root FORM1

python3 main.py FORM2 --results-dir output/verification_FORM2_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM2_FINAL --exam-root FORM2

python3 main.py FORM3 --results-dir output/verification_FORM3_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM3_FINAL --exam-root FORM3
```

Validation result:

- FORM1: Program 1 `32 / 32` rows, Program 2 `43 / 43` workbooks.
- FORM2: Program 1 `22 / 22` rows, Program 2 `52 / 52` workbooks.
- FORM3: Program 1 `42 / 42` rows, Program 2 `46 / 46` workbooks.
- Each Program 2 workbook contains `PAGE-01` and `EXAM` sheets.
- Unreadable presence images now produce empty rows instead of being dropped.
- Final report: `docs/VERIFICATION_REPORT.md`.
- Final evaluation summary: `docs/EVALUATION_SUMMARY.md`.

Debug folders:

- `debug/page01/`
- `debug/qcm/`
- `debug/handwritten_digits/`
- `debug/signatures/`
- `debug/review/`

Each main run writes:

- `FORMX_RESULTS/debug_summary.json`
- Program 1 presence file: `FORMX_RESULTS/FORMX_PRESENCES.xlsx`
- Program 2 files: `FORMX_RESULTS/EXAM_FORMX_*.xlsx`

Smoke command:

```bash
python3 main.py FORM1
```

For a smaller local smoke test, create a temporary exam folder with one image and one PDF, then run:

```bash
python3 main.py tmp_smoke_exam
```

## Remaining Risks

- Printed OCR quality depends strongly on field crop alignment. The pipeline is now stable, but some PAGE-01 printed fields may still be inaccurate.
- Handwritten digits are still trained on `sklearn.datasets.load_digits`, not real exam crops.
- FORM1/FORM2/FORM3 all passed output-format regression. QCM title false positives were fixed with vertical stack logic, but manual review is still recommended for low-confidence cases.
- Vocareum must provide `fitz`/PyMuPDF or an equivalent PDF renderer. If PyMuPDF is missing, the program now prints an installation message instead of failing at import time.
