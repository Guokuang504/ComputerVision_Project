# Verification Report

Date: 2026-06-03

This report covers the verification and hardening pass on the integrated Computer Vision project. The goal was not to add a new feature set, but to prove that the current pipeline runs on real project data, produces the required Excel files, and records failures/debug evidence without stopping the batch.

Update 2026-06-04: the final delivery pass extended regression from FORM1 to all locally available datasets. FORM1, FORM2, and FORM3 all pass output-format validation. See `docs/EVALUATION_SUMMARY.md` for the final cross-FORM table.

## Data Discovery

Detected real datasets:

| exam | presence folder | pdf folder | images | PDFs | signatures | default results |
| --- | --- | --- | ---: | ---: | ---: | --- |
| FORM1 | `FORM1/` | `FORM1/` | 32 | 43 | 1220 | `FORM1_RESULTS/` |
| FORM2 | `FORM2/` | `FORM2/` | 22 | 52 | 1220 | `FORM2_RESULTS/` |
| FORM3 | `FORM3/` | `FORM3/` | 42 | 46 | 1220 | `FORM3_RESULTS/` |

The command-line path discovery supports:

```bash
python3 main.py FORM1
python3 main.py --exam-root ./FORM1 --exam-name FORM1
python3 main.py FORM1 --results-dir output/verification_FORM1_RESULTS_r3
```

## Commands Run

```bash
python3 main.py --discover
python3 main.py FORM1 --results-dir output/verification_FORM1_RESULTS_r3 --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM1_RESULTS_r3 --exam-root FORM1
python3 -m recognition.evaluate --signatures SIGNATURES --threshold 0.82
python3 -m compileall .
```

## FORM1 Pipeline Result

Output folder:

`output/verification_FORM1_RESULTS_r3/`

Program 1:

- Presence images: `32`
- Rows in `FORM1_PRESENCES.xlsx`: `32`
- Required columns present: `imageName`, `studentID_grid`, `studentID_signature`
- Unreadable presence images: `3`
  - `EXAM_FORM1_61992.jpg`
  - `EXAM_FORM1_62288.png`
  - `EXAM_FORM1_62336.JPG`
- Handling: those files now keep an output row with empty recognition fields instead of being dropped.

Program 2:

- PDFs: `43`
- Generated `.xlsx` files: `43`
- Missing `.xlsx`: `0`
- Invalid workbooks: `0`
- Each generated workbook has at least `PAGE-01` and `EXAM` sheets.

Summary files:

- `output/verification_FORM1_RESULTS_r3/debug_summary.json`
- `output/verification_FORM1_RESULTS_r3/validation_summary.json`

## Debug Review

Generated review folders:

- `debug/review/page01_alignment/`
- `debug/review/signatures/`
- `debug/review/qcm/`
- `debug/review/handwritten/`

Review sample counts:

- Valid presence images reviewed: `10`
- PDFs reviewed: `5`
- PDF pages reviewed: `15`
- PAGE-01 alignment images: `15`
- Signature crops: `15`
- QCM overlays: `10`
- Handwritten crops: `30`

Visual checks performed:

- PAGE-01 overlay: student ID grid, group grid, and signature ROI are in the expected regions.
- QCM overlay: the previous false positive on `QUESTION` title text was removed; accepted boxes are now the left-side A-D option boxes.
- Signature crop: non-empty and tight enough for signature matching.
- Handwritten crop: non-empty, but many crops still contain border contamination.

## QCM False Positive Check

Output files:

- `debug/qcm/qcm_candidates.csv`
- `debug/qcm/accepted_candidates/`
- `debug/qcm/rejected_candidates/`

Final FORM1 + review debug summary:

- Candidate rows: `15454`
- Accepted candidates: `1392`
- Rejected candidates: `14062`
- Rejection reasons:
  - `not_in_vertical_stack`: `7876`
  - `aspect_not_square`: `5781`
  - `size_not_checkbox`: `389`
  - `side_inconsistent`: `16`

Fix applied:

- Kept the low-level image processing approach: thresholding, connected components, geometric filtering, border score, and stack regularity.
- Added a vertical A-D checkbox stack rule for real FORM pages.
- Kept the old horizontal-grid logic as fallback.
- Numeric answer rectangles are rejected by size/aspect rules and stay separate from QCM choices.

## Handwritten Digits

Output file:

`debug/handwritten_digits/handwritten_debug.csv`

Real crop debug summary:

- Rows: `261`
- `ok`: `193`
- `low_confidence`: `24`
- `failed`: `44`

Important interpretation:

- These are real exam-crop status counts, not accuracy values.
- There is no real ground truth label file for these handwritten crops in this validation pass.
- Several crops are marked as border-contaminated or failed; this is the main remaining risk for numeric answers.
- The sklearn digits validation accuracy is only a baseline check for the classifier, not proof of real exam handwriting accuracy.

## Signature Threshold

Output file:

`debug/signatures/signature_scores.csv`

Real FORM1 signature summary:

- Signature events: `72`
- `matched`: `35`
- `rejected`: `37`
- Threshold used: `0.82`
- Ambiguous margin used: `0.02`

Because the real FORM1 presence/PDF signatures do not provide a direct signature ground truth in this validation script, these counts are for manual audit, not accuracy.

Signature database leave-one-out evaluation:

- Samples: `1220`
- Top-1 accuracy: `0.8598360655737705`
- Accepted-correct rate: `0.7172131147540983`
- Accepted-wrong rate: `0.03770491803278689`
- Rejection rate: `0.21475409836065573`
- Ambiguous rate: `0.030327868852459017`

## Vocareum Compatibility

Checked:

- No absolute input paths are required by `main.py`; use `FORM1` or `--exam-root`.
- Results and debug folders are created automatically.
- No GUI/display dependency is required.
- Dependencies are listed in `requirements_project.txt`.
- `PyMuPDF` is used for PDF rendering. If missing, `pdf_to_images` prints a clear installation message and returns no pages instead of crashing at import time.
- `Tesseract` is optional for OCR. If missing, OCR returns empty text and confidence `0.0`.

Required packages:

```text
numpy
opencv-python
Pillow
scipy
scikit-image
scikit-learn
joblib
openpyxl
PyMuPDF
```

## Final Cross-FORM Status

| exam | Program 1 rows | Program 2 workbooks | missing workbooks | invalid workbooks |
| --- | ---: | ---: | ---: | ---: |
| FORM1 | 32 / 32 | 43 / 43 | 0 | 0 |
| FORM2 | 22 / 22 | 52 / 52 | 0 | 0 |
| FORM3 | 42 / 42 | 46 / 46 | 0 | 0 |

Final output folders:

- `output/verification_FORM1_FINAL/`
- `output/verification_FORM2_FINAL/`
- `output/verification_FORM3_FINAL/`

## Remaining Risks

- Printed OCR remains sensitive to crop alignment and Tesseract settings.
- Handwritten numeric extraction still needs better border removal and real labeled crop evaluation.
- Signature threshold `0.82` is calibrated on the signature database, but real-form acceptance/rejection still needs manual audit because no direct signature labels are available in this validation pass.
- The EXAM sheet now includes numeric rows, but exact question ordering can still be imperfect when numeric zone detection returns extra boxes.
