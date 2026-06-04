# Run Guide

## 1. Install Dependencies

From the project root:

```bash
python3 -m pip install -r requirements.txt
```

Required Python packages:

- `numpy`
- `opencv-python`
- `Pillow`
- `scipy`
- `scikit-image`
- `scikit-learn`
- `joblib`
- `openpyxl`
- `PyMuPDF`

Printed OCR uses the external `tesseract` command if available. If Tesseract is missing, the OCR wrapper returns empty text with `ocr_unavailable`/low-confidence status instead of crashing.

macOS:

```bash
brew install tesseract
```

Vocareum/Linux, if system installation is allowed:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
python3 -m pip install -r requirements.txt
```

## 2. Place Data

Default layout:

```text
project-root/
├── FORM1/
├── FORM2/
├── FORM3/
└── SIGNATURES/
```

The data folders are intentionally ignored by Git. If the team does not commit raw data, each member must place the folders locally.

Alternative explicit paths:

```bash
python3 main.py --exam-root /path/to/FORM1 --exam-name FORM1 --signatures-dir /path/to/SIGNATURES
```

## 3. Discover Datasets

```bash
python3 main.py --discover
```

Expected local discovery in the final pass:

- `FORM1`: 32 images, 43 PDFs
- `FORM2`: 22 images, 52 PDFs
- `FORM3`: 42 images, 46 PDFs
- `SIGNATURES`: 1220 signature PNGs

## 4. Run The Pipeline

FORM1:

```bash
python3 main.py FORM1 --results-dir output/verification_FORM1_FINAL
```

FORM2:

```bash
python3 main.py FORM2 --results-dir output/verification_FORM2_FINAL
```

FORM3:

```bash
python3 main.py FORM3 --results-dir output/verification_FORM3_FINAL
```

Signature threshold override:

```bash
python3 main.py FORM1 --signature-threshold 0.78 --signature-ambiguous-margin 0.03
```

## 5. Validate Outputs

```bash
python3 validate_outputs.py output/verification_FORM1_FINAL --exam-root FORM1
python3 validate_outputs.py output/verification_FORM2_FINAL --exam-root FORM2
python3 validate_outputs.py output/verification_FORM3_FINAL --exam-root FORM3
```

Validation checks:

- Program 1 presence workbook exists.
- Program 1 columns are `imageName`, `studentID_grid`, `studentID_signature`.
- Program 1 row count equals input presence image count.
- Program 2 creates one workbook per PDF.
- Each Program 2 workbook contains `PAGE-01` and `EXAM`.

## 6. Debug Files

Main debug folders:

- `debug/page01/printed_ocr/`
- `debug/qcm/accepted_candidates/`
- `debug/qcm/rejected_candidates/`
- `debug/handwritten_digits/`
- `debug/signatures/`
- `debug/review/`

Per-run CSV files are copied into each results folder:

- `handwritten_debug.csv`
- `signature_scores.csv`
- `printed_ocr_debug.csv`
- `qcm_candidates.csv`
- `debug_summary.json`
- `validation_summary.json`

## 7. Select Review Samples

Use this after running FORM1/FORM2/FORM3 final outputs. It creates smaller CSVs for manual checking instead of asking the team to inspect every debug row.

```bash
python3 scripts/select_review_samples.py
python3 scripts/select_review_samples.py --forms FORM1 FORM2 FORM3 --max-per-task 120
```

Generated files:

- `annotations/review_samples/printed_ocr_review_samples.csv`
- `annotations/review_samples/handwritten_review_samples.csv`
- `annotations/review_samples/signature_review_samples.csv`
- `annotations/review_samples/qcm_review_samples.csv`

Each row includes:

```text
form,source_file,page,item_id,predicted_value,confidence,status,debug_image_path,reason_for_review,ground_truth,comment
```

Use `debug_image_path` to open the crop/candidate image, then fill `ground_truth` and `comment`.

## 8. Fill Ground Truth Templates

Templates:

- `annotations/templates/printed_ocr_ground_truth_template.csv`
- `annotations/templates/handwritten_ground_truth_template.csv`
- `annotations/templates/signature_ground_truth_template.csv`
- `annotations/templates/qcm_review_template.csv`

Filled files expected by the evaluator:

- `annotations/printed_ocr_ground_truth.csv`
- `annotations/handwritten_ground_truth.csv`
- `annotations/signature_ground_truth.csv`
- `annotations/qcm_review.csv`

Detailed instructions are in `docs/USER_INPUT_CHECKLIST.md`.

## 9. Evaluate With Ground Truth

Run all available labeled evaluations:

```bash
python3 scripts/evaluate_with_ground_truth.py --task all
```

Run one task:

```bash
python3 scripts/evaluate_with_ground_truth.py --task printed_ocr --annotations annotations/printed_ocr_ground_truth.csv
python3 scripts/evaluate_with_ground_truth.py --task handwritten --annotations annotations/handwritten_ground_truth.csv
python3 scripts/evaluate_with_ground_truth.py --task signature --annotations annotations/signature_ground_truth.csv
python3 scripts/evaluate_with_ground_truth.py --task qcm --annotations annotations/qcm_review.csv
```

Output directory:

```text
output/evaluation_with_ground_truth/
```

If an annotation file is missing, the script prints a message such as:

```text
Missing annotation file: annotations/handwritten_ground_truth.csv. Use annotations/templates/handwritten_ground_truth_template.csv as template.
```

This is expected and does not block the project pipeline.

## 10. Dependency Fallbacks

PyMuPDF:

- Required for PDF rendering.
- Install with `python3 -m pip install PyMuPDF` or `python3 -m pip install -r requirements.txt`.
- If `fitz` is missing, `pdf_utils.py` gives a clear message; Program 2 PDF reading cannot be validated until PyMuPDF is installed.

Tesseract:

- Used only by printed OCR.
- If Tesseract is missing, OCR does not crash, but printed OCR fields become empty/low-confidence fallback values.
- Install if allowed, or mention the fallback in the report.

## 11. Clean Generated Files

Generated files are ignored by Git. To clean local outputs:

```bash
rm -rf debug output *_RESULTS
```

Do not remove `FORM1/`, `FORM2/`, `FORM3/`, or `SIGNATURES/` unless you have another copy.

## 12. Final Checks

```bash
python3 -m compileall .
python3 main.py --help
python3 validate_outputs.py --help
python3 scripts/final_check.py --results-dir output/verification_FORM1_FINAL --exam-root FORM1
python3 scripts/select_review_samples.py
python3 scripts/evaluate_with_ground_truth.py --task all
```

Verify:

- `annotations/templates/` contains the four template CSVs.
- `annotations/review_samples/` contains the four review CSVs after sample selection.
- Review CSVs include empty `ground_truth` and `comment` columns.
- Missing annotation files do not crash evaluation.

## 13. Git Commands

```bash
git init
git add .
git commit -m "Integrate computer vision final project pipeline"
git branch -M main
git remote add origin <REMOTE_URL>
git push -u origin main
```

Before committing:

```bash
git status --short
```

Make sure raw data, debug images, output Excel files, filled annotations, review samples, and caches are not staged. In particular, `debug/`, `output/`, `FORM1/`, `FORM2/`, `FORM3/`, and `SIGNATURES/` should not appear in `git status --short`.
