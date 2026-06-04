# Signature Threshold Plan

Date: 2026-06-04

Current runtime parameters:

- `threshold=0.82`
- `ambiguous_margin=0.02`

The signature recognizer returns:

- `predicted_student_id`
- `confidence`
- `top1_score`
- `top2_score`
- `margin`
- `status`: `matched`, `rejected`, `ambiguous`, or `invalid_input`
- `debug_path`

## Current Real FORM Audit

These are real form status logs, not ground-truth accuracy values.

| exam | rows | matched | rejected | ambiguous | invalid_input |
| --- | ---: | ---: | ---: | ---: | ---: |
| FORM1 | 72 | 35 | 37 | 0 | 0 |
| FORM2 | 70 | 32 | 38 | 0 | 0 |
| FORM3 | 84 | 44 | 39 | 1 | 0 |

Score logs:

- `output/verification_FORM1_FINAL/signature_scores.csv`
- `output/verification_FORM2_FINAL/signature_scores.csv`
- `output/verification_FORM3_FINAL/signature_scores.csv`

Representative score cases:

- FORM3 matched: `EXAM_FORM3_19283.jpeg`, predicted `19283`, distance `0.546`, threshold `0.82`.
- FORM3 rejected: `EXAM_FORM3_36912.jpeg`, predicted `61856`, distance `1.070`, threshold `0.82`.
- FORM3 low-margin rejected: `EXAM_FORM3_50305.jpg`, margin about `0.014`.

## Database Validation

The only quantitative signature accuracy currently available comes from leave-one-out validation on `SIGNATURES/`, not from the real FORM attendance pages.

Command:

```bash
python3 -m recognition.evaluate --signatures SIGNATURES --threshold 0.82
```

Current database result:

- Samples: `1220`
- Top-1 accuracy: `0.8598360655737705`
- Accepted-correct rate: `0.7172131147540983`
- Accepted-wrong rate: `0.03770491803278689`
- Rejection rate: `0.21475409836065573`
- Ambiguous rate: `0.030327868852459017`

## Threshold Strategy

1. Minimize false acceptance first. A wrong accepted signature is more damaging than a rejected signature that can be manually reviewed.
2. Report `ambiguous` separately. Close top-1/top-2 scores should not be forced into a confident match.
3. Use real ground truth before changing the default threshold. The current real FORM logs show many rejected cases, but without labels we do not know whether they are false rejections or true mismatches/low-quality signatures.
4. Once labels exist, sweep thresholds and choose the lowest false-acceptance setting that reduces false rejection.

Commands to compare a lower threshold:

```bash
python3 main.py FORM1 --signature-threshold 0.78 --signature-ambiguous-margin 0.03
python3 scripts/evaluate_with_ground_truth.py --task signature --annotations annotations/signature_ground_truth.csv
```

## Required Ground Truth

Fill:

```text
annotations/signature_ground_truth.csv
```

Template:

```text
annotations/templates/signature_ground_truth_template.csv
```

Columns:

```text
form,source_file,expected_student_id,is_genuine,comment
```

Minimum label set:

- All `rejected` cases.
- All `ambiguous` cases.
- Low-margin cases where `margin < 0.03`.
- A control group of matched cases.

## Expected Evaluation Outputs

```bash
python3 scripts/evaluate_with_ground_truth.py --task signature --annotations annotations/signature_ground_truth.csv
```

Expected files:

- `output/evaluation_with_ground_truth/signature_summary.csv`
- `output/evaluation_with_ground_truth/signature_threshold_curve.csv`
- `output/evaluation_with_ground_truth/signature_error_cases.csv`

## Conclusion

The current threshold is conservative and database-validated. It should not be changed blindly. Real FORM false rejection and false acceptance can only be claimed after `annotations/signature_ground_truth.csv` is filled and the threshold curve is evaluated.
