# FORM3 Handwritten Failure Analysis

Date: 2026-06-04

Source file:

- `output/verification_FORM3_FINAL/handwritten_debug.csv`

This is a failure audit, not an accuracy report. No real handwritten ground truth is currently available, so the project can report crop quality, status counts, and debug examples, but cannot claim true FORM3 handwritten accuracy.

## Summary

| metric | count |
| --- | ---: |
| total handwritten records | 561 |
| ok | 312 |
| low_confidence | 43 |
| failed | 206 |
| invalid/empty crop quality | 2 |
| too_small crop quality | 0 recorded |
| too_noisy crop quality | 0 recorded |
| border_contamination crop quality | 401 |
| low_contrast crop quality | 0 recorded |
| valid crop quality | 158 |

The dominant recorded quality issue is `border_contamination`. This means many crops include table borders or answer-box edges that become foreground after thresholding. The recognizer is stable because it returns `failed` or `low_confidence` instead of forcing a high-confidence digit, but the downstream accuracy still needs labels.

## Representative Debug Images

Open these paths to inspect the actual crops:

- Failed, border contamination: `/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/debug/handwritten_digits/EXAM_FORM3_19283_p6_z1_mantisse.png`
- Low confidence, border contamination: `/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/debug/handwritten_digits/EXAM_FORM3_19283_p8_z0_exposant.png`
- Valid crop, accepted output: `/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/debug/handwritten_digits/EXAM_FORM3_19283_p6_z0_mantisse.png`
- Empty crop example: `/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/debug/handwritten_digits/EXAM_FORM3_62496_p5_z0_mantisse.png`

## Likely Causes

| cause | evidence | current interpretation |
| --- | --- | --- |
| Crop alignment | Many failures are tied to answer zones and page/cell positions, not a single classifier class. | Some crops likely include too much grid or miss the handwritten content. |
| Border contamination | `401/561` records have `crop_quality=border_contamination`. | Border removal and padding are the highest-impact preprocessing checks. |
| Preprocessing limitation | Border pixels can survive binarization and dominate connected components. | Current preprocessing is defensive, but not always enough for FORM3 geometry. |
| Model limitation | The digit model was trained on baseline digit data, not labeled FORM3 crops. | Even clean crops cannot be assumed correct without real labels. |
| Missing content | `2` records are marked empty; some failed crops may also be visually blank or unreadable. | Empty or unreadable fields should remain blank/failed, not guessed. |

## What Is Already Controlled

- Invalid crops do not crash the batch.
- Debug crop images are saved in `debug/handwritten_digits/`.
- Each result has `value`, `confidence`, `status`, `crop_quality`, and `debug_path`.
- Low-confidence and failed crops are not reported as high-confidence successes.

## Required Closure

1. Generate the review queue:

```bash
python3 scripts/select_review_samples.py --forms FORM3 --max-per-task 120
```

2. Fill labels in:

```text
annotations/handwritten_ground_truth.csv
```

Use the template:

```text
annotations/templates/handwritten_ground_truth_template.csv
```

3. Evaluate:

```bash
python3 scripts/evaluate_with_ground_truth.py --task handwritten --annotations annotations/handwritten_ground_truth.csv
```

## Conclusion

FORM3 handwritten output is engineered to fail safely, but its accuracy is not proven. The current evidence points mainly to crop alignment and border contamination. Any further code tuning should be validated with `annotations/handwritten_ground_truth.csv`; otherwise the report should describe this as a failure audit only.
