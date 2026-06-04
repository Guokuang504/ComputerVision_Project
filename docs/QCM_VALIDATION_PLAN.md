# QCM Validation Plan

Date: 2026-06-04

The QCM detector must keep a low-level image processing approach. The current implementation uses thresholding, connected components, geometry filters, vertical stack checks, and row/column regularity. It does not use a high-level automatic checkbox detector.

## Current Method

The candidate pipeline records each possible box with:

- component geometry: `x`, `y`, `w`, `h`, `area`
- darkness/fill evidence: `dark_area`, `fill_ratio`, `inner_dark_score`, `border_score`
- layout evidence: `page_zone`, vertical stack membership, side consistency
- decision: `accepted`/`rejected`
- rejection reason
- debug crop path

CSV files:

- `output/verification_FORM1_FINAL/qcm_candidates.csv`
- `output/verification_FORM2_FINAL/qcm_candidates.csv`
- `output/verification_FORM3_FINAL/qcm_candidates.csv`

Debug folders:

- `debug/qcm/accepted_candidates/`
- `debug/qcm/rejected_candidates/`

## Current Candidate Counts

| exam | candidates | accepted | rejected | main rejection reasons |
| --- | ---: | ---: | ---: | --- |
| FORM1 | 14205 | 1288 | 12917 | `not_in_vertical_stack`, `aspect_not_square`, `size_not_checkbox` |
| FORM2 | 21900 | 964 | 20936 | `not_in_vertical_stack`, `aspect_not_square`, `size_not_checkbox` |
| FORM3 | 17557 | 1352 | 16205 | `not_in_vertical_stack`, `aspect_not_square`, `size_not_checkbox` |

## Numeric Answer Box Separation

Numeric answer boxes are excluded by combining several low-level signals:

- size filter: answer rectangles that are too large/small for checkbox dimensions get `size_not_checkbox`;
- aspect filter: non-square answer rectangles get `aspect_not_square`;
- vertical stack filter: isolated numeric cells that do not align as A-D option stacks get `not_in_vertical_stack`;
- side consistency: irregular candidates around text/table structures get `side_inconsistent`;
- page zone checks: candidates outside expected QCM regions are deprioritized or rejected.

This is intentionally conservative. Over-tuning the filters can reduce false positives but may create false negatives by rejecting true checkboxes in slightly shifted forms.

## How To Review Candidates

Generate review queues:

```bash
python3 scripts/select_review_samples.py
```

Open:

```text
annotations/review_samples/qcm_review_samples.csv
```

Inspect `debug_image_path` and fill `ground_truth`/`comment` for selected rows. For candidate-level review, mark `ground_truth` or `expected_choice` as:

- `accepted`: this candidate should be a valid QCM checkbox.
- `rejected`: this candidate should not be a QCM checkbox.

Then copy labels into:

```text
annotations/qcm_review.csv
```

Template:

```text
annotations/templates/qcm_review_template.csv
```

## Evaluation

Run:

```bash
python3 scripts/evaluate_with_ground_truth.py --task qcm --annotations annotations/qcm_review.csv
```

Expected outputs:

- `output/evaluation_with_ground_truth/qcm_summary.csv`
- `output/evaluation_with_ground_truth/qcm_error_cases.csv`

Metrics:

- choice/candidate accuracy
- false positive count
- false negative count
- candidate/question-level errors

## Closure Criteria

The QCM risk is closed when:

- accepted candidates reviewed by the team are mostly true checkboxes;
- suspicious rejected candidates are not true missed checkboxes, or the missed pattern is understood;
- numeric answer boxes are not accepted as QCM choices in the reviewed sample;
- any rule change is measured with `qcm_review.csv`.

## Conclusion

The current QCM logic is course-compatible because it uses low-level image processing and geometry. The remaining risk is validation, not crash safety. Manual review should focus on accepted candidates with abnormal area/aspect/fill and rejected candidates that look like true checkboxes.
