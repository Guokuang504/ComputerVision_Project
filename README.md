# Computer Vision Final Project

Automatic reading of semi-structured exam forms for the IG.2405/IG2045 Computer Vision final project.

The project contains two main programs:

- Program 1: attendance validation from scanned presence images.
- Program 2: automatic PDF form reading and Excel generation.

The implementation integrates three team modules:

- `code_partie1_stucture_generale/`: main orchestration, PDF loading, page field crops, Excel writing flow.
- `code_partie2_elements_graphiques/`: low-level graphical analysis for grids, checkboxes/QCM, cryptograms, and PAGE-01 elements.
- `recognition/`: signature matching, printed OCR wrapper, handwritten number recognition, and evaluation.

## Repository Layout

```text
.
├── main.py
├── config.py
├── data_discovery.py
├── debug_utils.py
├── excel_writer.py
├── validate_outputs.py
├── requirements.txt
├── annotations/
├── docs/
├── scripts/
├── code_partie1_stucture_generale/
├── code_partie2_elements_graphiques/
└── recognition/
```

Large datasets and generated files are intentionally ignored by Git:

- `FORM1/`, `FORM2/`, `FORM3/`
- `SIGNATURES/` if your team chooses not to version raw data
- `debug/`
- `output/`
- `*_RESULTS/`
- generated Excel files

If the datasets are not committed, place `FORM1/`, `FORM2/`, `FORM3/`, and `SIGNATURES/` in the project root before running. You can also use `--exam-root` and `--signatures-dir`.

## Install

Python 3.9+ is recommended.

```bash
python3 -m pip install -r requirements.txt
```

Printed OCR uses the external `tesseract` command when available. The pipeline does not crash if Tesseract is missing; printed fields will be empty/low-confidence.

macOS install:

```bash
brew install tesseract
```

Vocareum/Linux install depends on the environment. If allowed:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
python3 -m pip install -r requirements.txt
```

## Run

Discover available datasets:

```bash
python3 main.py --discover
```

Run one exam folder:

```bash
python3 main.py FORM1
```

Run with explicit output folder:

```bash
python3 main.py FORM1 --results-dir output/verification_FORM1_FINAL
```

Override signature threshold:

```bash
python3 main.py FORM1 --signature-threshold 0.78 --signature-ambiguous-margin 0.03
```

Use explicit paths:

```bash
python3 main.py --exam-root ./FORM1 --exam-name FORM1 --signatures-dir ./SIGNATURES
```

## Validate Outputs

```bash
python3 validate_outputs.py output/verification_FORM1_FINAL --exam-root FORM1
```

This checks:

- Program 1 presence Excel columns and row count.
- Program 2 one workbook per input PDF.
- `PAGE-01` and `EXAM` sheet presence.
- Debug summaries for QCM, signatures, handwritten crops, and printed OCR.
- Review images under `debug/review/`.

## Final Check

```bash
python3 scripts/final_check.py --results-dir output/verification_FORM1_FINAL --exam-root FORM1
python3 -m compileall .
```

## Manual Review And Ground Truth Evaluation

Generate prioritized samples for human checking:

```bash
python3 scripts/select_review_samples.py
python3 scripts/select_review_samples.py --forms FORM1 FORM2 FORM3 --max-per-task 120
```

Review queues are written to `annotations/review_samples/`:

- `printed_ocr_review_samples.csv`
- `handwritten_review_samples.csv`
- `signature_review_samples.csv`
- `qcm_review_samples.csv`

Fill annotation files using the templates in `annotations/templates/`:

- `annotations/printed_ocr_ground_truth.csv`
- `annotations/handwritten_ground_truth.csv`
- `annotations/signature_ground_truth.csv`
- `annotations/qcm_review.csv`

Run measured evaluation when labels exist:

```bash
python3 scripts/evaluate_with_ground_truth.py --task all
```

If an annotation file is missing, the evaluator prints the matching template path and continues without crashing. Do not claim real OCR, handwritten, signature, or QCM accuracy unless the corresponding ground truth file is filled.

## Git Setup

```bash
git init
git add .
git commit -m "Integrate computer vision final project pipeline"
git branch -M main
git remote add origin <REMOTE_URL>
git push -u origin main
```

Before committing, verify `git status --short` does not include large data, `debug/`, `output/`, generated Excel files, filled annotation CSVs, review samples, `FORM1/`, `FORM2/`, `FORM3/`, or `SIGNATURES/`.

## Key Documentation

- `docs/RUN_GUIDE.md`: detailed run and Vocareum guide.
- `docs/METHODS_FOR_REPORT.md`: methods to use in the written report.
- `docs/EVALUATION_SUMMARY.md`: regression and debug metrics.
- `docs/FINAL_RISK_CLOSURE_PLAN.md`: risk closure table and validation commands.
- `docs/USER_INPUT_CHECKLIST.md`: annotation files needed from the team.
- `docs/FORM3_HANDWRITTEN_FAILURE_ANALYSIS.md`: FORM3 handwritten failure audit.
- `docs/PRINTED_OCR_ALIGNMENT_ANALYSIS.md`: printed OCR crop/alignment audit.
- `docs/SIGNATURE_THRESHOLD_PLAN.md`: signature threshold calibration strategy.
- `docs/QCM_VALIDATION_PLAN.md`: QCM candidate validation workflow.
- `docs/TEAM_CHANGELOG.md`: integration changes for teammates.
- `docs/VERIFICATION_REPORT.md`: FORM1 verification report from the previous hardening pass.
