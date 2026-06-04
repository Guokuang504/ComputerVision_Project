# Team Changelog

Date: 2026-06-04

This changelog summarizes integration and hardening changes for the team.

## Added Files

- `main.py`: root entry point.
- `config.py`: centralized thresholds and paths.
- `data_discovery.py`: automatic discovery for `FORM1`, `FORM2`, `FORM3`, and signatures.
- `debug_utils.py`: debug event/image logging.
- `excel_writer.py`: Program 1 and Program 2 workbook writing.
- `validate_outputs.py`: output validation and debug review generation.
- `scripts/final_check.py`: lightweight final delivery checks.
- `scripts/select_review_samples.py`: standard-library review queue generator for printed OCR, handwritten crops, signatures, and QCM candidates.
- `scripts/evaluate_with_ground_truth.py`: standard-library evaluator for optional human annotation files.
- `requirements.txt`: Vocareum-friendly Python dependencies.
- `.gitignore`: excludes raw data, output, debug, caches, and generated files.
- `README.md`: project overview and quick commands.
- `docs/RUN_GUIDE.md`: detailed run guide.
- `docs/METHODS_FOR_REPORT.md`: methods for final report.
- `docs/EVALUATION_SUMMARY.md`: FORM1/FORM2/FORM3 regression results.
- `docs/FINAL_RISK_CLOSURE_PLAN.md`: final risk table with evidence, required inputs, commands, and remaining limitations.
- `docs/USER_INPUT_CHECKLIST.md`: annotation checklist and CSV formats for teammates.
- `docs/FORM3_HANDWRITTEN_FAILURE_ANALYSIS.md`: FORM3 handwritten failure audit.
- `docs/PRINTED_OCR_ALIGNMENT_ANALYSIS.md`: PAGE-01 OCR crop/alignment audit.
- `docs/SIGNATURE_THRESHOLD_PLAN.md`: real FORM threshold calibration plan.
- `docs/QCM_VALIDATION_PLAN.md`: QCM candidate validation and false-positive review plan.
- `docs/PROJECT_ROOT_AUDIT.md`: Git-ready file classification.
- `annotations/templates/*.csv`: empty templates for OCR, handwritten, signature, and QCM labels.

## Updated Files

- `code_partie1_stucture_generale/main.py`
  - Integrated Program 1 and Program 2.
  - Added CLI options for `--exam-root`, `--results-dir`, `--signatures-dir`, `--signature-threshold`, and `--signature-ambiguous-margin`.
  - Added per-file exception handling.
  - Keeps rows for unreadable presence images.
  - Writes debug summaries and per-run CSVs.
  - Logs printed OCR crops and statuses.

- `code_partie1_stucture_generale/pdf_utils.py`
  - Added PyMuPDF import fallback.
  - Missing `fitz` now gives a clear message instead of import-time crash.

- `code_partie1_stucture_generale/page_fields.py`
  - Hardened crop extraction.
  - Numeric answer detection returns safe empty outputs instead of crashing.

- `code_partie2_elements_graphiques/components.py`
  - Added invalid image protection.
  - Handles `None`, empty arrays, `NaN`, and `inf`.

- `code_partie2_elements_graphiques/page01.py`
  - Hardened PAGE-01 graphical reading.
  - Safe defaults for missing grids, conditions, cryptogram, and signature crop.

- `code_partie2_elements_graphiques/exam.py`
  - Improved QCM false-positive filtering.
  - Added vertical A-D option stack logic for real FORM pages.
  - Kept low-level thresholding, connected components, geometry, and clustering.
  - Added `qcm_candidates.csv` with accepted/rejected reasons and candidate images.

- `recognition/signature.py`
  - Multi-feature signature distance fusion.
  - Status output: `matched`, `rejected`, `ambiguous`, `invalid_input`.

- `recognition/handwriting.py`
  - More stable preprocessing.
  - Debug crops for real exam handwritten fields.
  - Low-confidence and failed status handling.

- `recognition/ocr.py`
  - Tesseract wrapper with TSV confidence parsing.
  - Field whitelists.
  - Graceful `ocr_unavailable` fallback.

## Old Logic Kept

- Low-level graphical detection remains based on thresholding, connected components, morphology-style filtering, and geometry.
- Existing PAGE-01, cryptogram, and QCM module boundaries remain separate.
- Recognition still consumes cropped regions and does not own page segmentation.
- Existing demo scripts are retained for module sanity checks.

## Bugs Fixed

- Bad image, empty crop, `NaN`, and `inf` inputs no longer crash the batch.
- Unreadable presence images no longer reduce Program 1 Excel row count.
- QCM title fragments around `QUESTION` are no longer treated as checkbox answers in the reviewed FORM1 case.
- Numeric rows are now written into the `EXAM` sheet even when there is no QCM row at the same y-position.
- Printed OCR errors and missing OCR backend no longer stop PDF processing.
- Signature threshold and ambiguous margin can be overridden from the command line.

## Risk Closure Additions

- Review samples can be generated with:

```bash
python3 scripts/select_review_samples.py
```

- Ground-truth evaluation can be run with:

```bash
python3 scripts/evaluate_with_ground_truth.py --task all
```

- If annotation files are missing, evaluation prints the required template path and does not crash.
- Real OCR, handwritten, signature, and QCM accuracy should only be claimed after the corresponding `annotations/*.csv` file is filled.
- Filled annotation files and generated review queues are ignored by Git by default; only templates under `annotations/templates/` should normally be committed.

## Final Regression Results

- FORM1: `32/32` presence rows, `43/43` PDF workbooks.
- FORM2: `22/22` presence rows, `52/52` PDF workbooks.
- FORM3: `42/42` presence rows, `46/46` PDF workbooks.

Detailed metrics are in `docs/EVALUATION_SUMMARY.md`.

## Manual Checks Still Needed

- Inspect low-confidence/failed OCR crops in `debug/page01/printed_ocr/`.
- Inspect handwritten failures, especially FORM3, in `debug/handwritten_digits/`.
- Inspect signature rejected/ambiguous cases in `debug/signatures/`.
- Fill optional ground truth files listed in `docs/USER_INPUT_CHECKLIST.md`.
- Run `python3 scripts/evaluate_with_ground_truth.py --task all` after labels exist.
- If the team wants higher numeric-answer accuracy, create a labeled real-crop dataset and retrain/evaluate the handwritten model.
- If the team wants to submit data through Git, agree explicitly which sample data is small enough to version and update `.gitignore`.
