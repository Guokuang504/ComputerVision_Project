# User Input Checklist

Date: 2026-06-04

This checklist defines the manual labels needed to turn the current debug audit into measured recognition accuracy. The project can run without these files. If a file is missing, `scripts/evaluate_with_ground_truth.py` prints a template hint and exits without crashing.

## 1. Generate Review Samples

Run this before annotation:

```bash
python3 scripts/select_review_samples.py
python3 scripts/select_review_samples.py --forms FORM1 FORM2 FORM3 --max-per-task 120
```

Generated review queues:

- `annotations/review_samples/printed_ocr_review_samples.csv`
- `annotations/review_samples/handwritten_review_samples.csv`
- `annotations/review_samples/signature_review_samples.csv`
- `annotations/review_samples/qcm_review_samples.csv`

Each review CSV contains `ground_truth` and `comment` empty columns. Use the `debug_image_path` column to inspect the crop/candidate image.

## 2. Printed OCR Ground Truth

Required file:

- `annotations/printed_ocr_ground_truth.csv`

Template:

- `annotations/templates/printed_ocr_ground_truth_template.csv`

Columns:

```text
form,pdf_file,page,field_name,ground_truth_text,comment
```

How to fill:

- `form`: `FORM1`, `FORM2`, or `FORM3`.
- `pdf_file`: source form name, for example `EXAM_FORM3_19283`.
- `page`: page number if known; leave empty when the debug source does not include it.
- `field_name`: PAGE-01 field name, for example `module`, `professor`, `date`, `code`, `note_max`, `note_valid`.
- `ground_truth_text`: exact text visible on the original PDF/page.
- `comment`: optional reason such as `crop shifted left`, `text unreadable`, or `not visible`.

Minimum sample:

- At least 10 PDFs per FORM.
- Prefer all invalid/failed/low-confidence samples selected by `printed_ocr_review_samples.csv`.

Evaluation command:

```bash
python3 scripts/evaluate_with_ground_truth.py --task printed_ocr --annotations annotations/printed_ocr_ground_truth.csv
```

## 3. Handwritten Ground Truth

Required file:

- `annotations/handwritten_ground_truth.csv`

Template:

- `annotations/templates/handwritten_ground_truth_template.csv`

Columns:

```text
form,pdf_file,page,field_name,crop_id,ground_truth_value,comment
```

How to fill:

- `form`: `FORM1`, `FORM2`, or `FORM3`.
- `pdf_file`: source form name, for example `EXAM_FORM3_19283`.
- `page`: exam page if visible in the crop id, for example `6`.
- `field_name`: recognized field name when available, for example `mantisse` or `exposant`.
- `crop_id`: the debug crop name without relying on the full absolute path, for example `EXAM_FORM3_19283_p6_z1_mantisse`.
- `ground_truth_value`: visible handwritten value. Leave empty only when the crop truly has no readable content.
- `comment`: optional quality label such as `border contamination`, `empty crop`, `ambiguous handwriting`, or `wrong crop`.

Minimum sample:

- Start with 100 failed/low-confidence crops.
- For FORM3, label at least 50 failed crops; 120 selected samples is better.

Evaluation command:

```bash
python3 scripts/evaluate_with_ground_truth.py --task handwritten --annotations annotations/handwritten_ground_truth.csv
```

## 4. Signature Ground Truth

Required file:

- `annotations/signature_ground_truth.csv`

Template:

- `annotations/templates/signature_ground_truth_template.csv`

Columns:

```text
form,source_file,expected_student_id,is_genuine,comment
```

How to fill:

- `form`: `FORM1`, `FORM2`, or `FORM3`.
- `source_file`: exact filename from `signature_scores.csv`, for example `EXAM_FORM3_36912.jpeg`.
- `expected_student_id`: expected student ID for the form.
- `is_genuine`: `1`/`true` if the signature belongs to the expected student; `0`/`false` if it is known to be a forgery or mismatch.
- `comment`: optional note such as `unclear signature`, `expected from attendance list`, or `suspected forgery`.

Minimum sample:

- Label all rejected, ambiguous, and low-margin cases if possible.
- About 100 samples gives a useful first threshold calibration.

Evaluation command:

```bash
python3 scripts/evaluate_with_ground_truth.py --task signature --annotations annotations/signature_ground_truth.csv
```

## 5. QCM Review

Required file:

- `annotations/qcm_review.csv`

Template:

- `annotations/templates/qcm_review_template.csv`

Columns:

```text
form,pdf_file,page,question_id,expected_choice,comment
```

How to fill:

- `form`: `FORM1`, `FORM2`, or `FORM3`.
- `pdf_file`: source form/page name from `qcm_candidates.csv`, for example `EXAM_FORM3_19283_p5`.
- `page`: page number if known.
- `question_id`: candidate id or question id from the review sample `item_id`.
- `expected_choice`: for candidate-level review, use `accepted` or `rejected`. For question-level review, use the true choice label if the team has that mapping.
- `comment`: optional note such as `numeric answer box`, `true checkbox`, `title text`, or `missed option`.

Minimum sample:

- At least 50 accepted candidates and 50 suspicious rejected candidates per FORM.
- Include FORM2/FORM3 because numeric answer boxes and dense layouts create more false-positive risk.

Evaluation command:

```bash
python3 scripts/evaluate_with_ground_truth.py --task qcm --annotations annotations/qcm_review.csv
```

## 6. Run All Evaluation

After creating any annotation files:

```bash
python3 scripts/evaluate_with_ground_truth.py --task all
```

Outputs:

- `output/evaluation_with_ground_truth/evaluation_summary.json`
- `output/evaluation_with_ground_truth/printed_ocr_summary.csv`
- `output/evaluation_with_ground_truth/printed_ocr_error_cases.csv`
- `output/evaluation_with_ground_truth/handwritten_summary.csv`
- `output/evaluation_with_ground_truth/handwritten_error_cases.csv`
- `output/evaluation_with_ground_truth/handwritten_confusion_matrix.csv`
- `output/evaluation_with_ground_truth/signature_summary.csv`
- `output/evaluation_with_ground_truth/signature_threshold_curve.csv`
- `output/evaluation_with_ground_truth/signature_error_cases.csv`
- `output/evaluation_with_ground_truth/qcm_summary.csv`
- `output/evaluation_with_ground_truth/qcm_error_cases.csv`

## 7. Git Safety

The following are ignored by Git by default:

- `annotations/*.csv`
- `annotations/review_samples/`
- `debug/`
- `output/`
- `FORM1/`, `FORM2/`, `FORM3/`
- `SIGNATURES/`

Only the empty templates in `annotations/templates/` should normally be committed.
