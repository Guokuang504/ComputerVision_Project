# Evaluation Summary

Date: 2026-06-04

## Datasets Tested

All locally available real datasets were tested.

| exam | presence images | PDFs | signatures available |
| --- | ---: | ---: | ---: |
| FORM1 | 32 | 43 | 1220 |
| FORM2 | 22 | 52 | 1220 |
| FORM3 | 42 | 46 | 1220 |

Commands:

```bash
python3 main.py FORM1 --results-dir output/verification_FORM1_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM1_FINAL --exam-root FORM1

python3 main.py FORM2 --results-dir output/verification_FORM2_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM2_FINAL --exam-root FORM2

python3 main.py FORM3 --results-dir output/verification_FORM3_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM3_FINAL --exam-root FORM3
```

## Program 1 Validation

| exam | presence images | Excel rows | unreadable presence files | columns ok | status |
| --- | ---: | ---: | ---: | --- | --- |
| FORM1 | 32 | 32 | 3 | yes | ok |
| FORM2 | 22 | 22 | 4 | yes | ok |
| FORM3 | 42 | 42 | 4 | yes | ok |

Unreadable images are not dropped. They produce an output row with the original `imageName` and empty recognition fields.

## Program 2 Validation

| exam | PDFs | generated workbooks | missing workbooks | invalid workbooks | PAGE-01 sheet | EXAM sheet |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| FORM1 | 43 | 43 | 0 | 0 | yes | yes |
| FORM2 | 52 | 52 | 0 | 0 | yes | yes |
| FORM3 | 46 | 46 | 0 | 0 | yes | yes |

## Runtime

| exam | runtime seconds | debug summary |
| --- | ---: | --- |
| FORM1 | 86 | `output/verification_FORM1_FINAL/debug_summary.json` |
| FORM2 | 101 | `output/verification_FORM2_FINAL/debug_summary.json` |
| FORM3 | 104 | `output/verification_FORM3_FINAL/debug_summary.json` |

## QCM Candidate Statistics

| exam | candidates | accepted | rejected | main rejection reasons |
| --- | ---: | ---: | ---: | --- |
| FORM1 | 14205 | 1288 | 12917 | `not_in_vertical_stack`, `aspect_not_square`, `size_not_checkbox` |
| FORM2 | 21900 | 964 | 20936 | `not_in_vertical_stack`, `aspect_not_square`, `size_not_checkbox` |
| FORM3 | 17557 | 1352 | 16205 | `not_in_vertical_stack`, `aspect_not_square`, `size_not_checkbox` |

CSV paths:

- `output/verification_FORM1_FINAL/qcm_candidates.csv`
- `output/verification_FORM2_FINAL/qcm_candidates.csv`
- `output/verification_FORM3_FINAL/qcm_candidates.csv`

Each row includes geometry, fill score, page zone, `accepted`, `decision`, and rejection reason.

## Handwritten Crop Audit

These are real exam crop status counts, not accuracy values.

| exam | rows | ok | low_confidence | failed |
| --- | ---: | ---: | ---: | ---: |
| FORM1 | 261 | 193 | 24 | 44 |
| FORM2 | 462 | 325 | 109 | 28 |
| FORM3 | 561 | 312 | 43 | 206 |

CSV paths:

- `output/verification_FORM1_FINAL/handwritten_debug.csv`
- `output/verification_FORM2_FINAL/handwritten_debug.csv`
- `output/verification_FORM3_FINAL/handwritten_debug.csv`

Main risk: FORM3 has many failed handwritten crops, mostly due to border contamination or bad crop quality. This should be manually reviewed before claiming numeric-answer accuracy.

## Printed OCR Audit

| exam | rows | ok | low_confidence | failed | invalid_crop |
| --- | ---: | ---: | ---: | ---: | ---: |
| FORM1 | 258 | 19 | 87 | 80 | 72 |
| FORM2 | 312 | 18 | 96 | 95 | 103 |
| FORM3 | 276 | 25 | 84 | 62 | 105 |

CSV paths:

- `output/verification_FORM1_FINAL/printed_ocr_debug.csv`
- `output/verification_FORM2_FINAL/printed_ocr_debug.csv`
- `output/verification_FORM3_FINAL/printed_ocr_debug.csv`

Interpretation:

- The OCR pipeline is stable and does not crash.
- Accuracy is still limited by PAGE-01 crop alignment and crop quality.
- Low-confidence and invalid-crop cases should be manually inspected in `debug/page01/printed_ocr/`.

## Signature Matching Statistics

Real FORM score logs, no ground-truth accuracy claim:

| exam | rows | matched | rejected | ambiguous | invalid_input |
| --- | ---: | ---: | ---: | ---: | ---: |
| FORM1 | 72 | 35 | 37 | 0 | 0 |
| FORM2 | 70 | 32 | 38 | 0 | 0 |
| FORM3 | 84 | 44 | 39 | 1 | 0 |

CSV paths:

- `output/verification_FORM1_FINAL/signature_scores.csv`
- `output/verification_FORM2_FINAL/signature_scores.csv`
- `output/verification_FORM3_FINAL/signature_scores.csv`

Signature database leave-one-out validation:

```bash
python3 -m recognition.evaluate --signatures SIGNATURES --threshold 0.82
```

Results from the calibrated signature database:

- Samples: `1220`
- Top-1 accuracy: `0.8598360655737705`
- Accepted-correct rate: `0.7172131147540983`
- Accepted-wrong rate: `0.03770491803278689`
- Rejection rate: `0.21475409836065573`
- Ambiguous rate: `0.030327868852459017`

## Remaining Risks

- Printed OCR needs better PAGE-01 crop alignment or field-specific crop tuning.
- Handwritten numbers need labeled real exam crops for true accuracy evaluation.
- FORM3 handwritten crop failures are high and should be manually reviewed.
- Signature accepted/rejected statistics on real forms are audit statistics only; no true labels are available in this validation pass.
- Large raw datasets are ignored by Git, so each teammate must place them locally or use explicit paths.
- Final risk closure, annotation templates, review sample selection, and ground-truth evaluation workflow are documented in `docs/FINAL_RISK_CLOSURE_PLAN.md` and `docs/USER_INPUT_CHECKLIST.md`.
