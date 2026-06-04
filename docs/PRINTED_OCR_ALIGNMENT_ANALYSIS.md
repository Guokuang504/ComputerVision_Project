# Printed OCR Alignment Analysis

Date: 2026-06-04

Source files:

- `output/verification_FORM1_FINAL/printed_ocr_debug.csv`
- `output/verification_FORM2_FINAL/printed_ocr_debug.csv`
- `output/verification_FORM3_FINAL/printed_ocr_debug.csv`

This analysis focuses on PAGE-01 printed OCR crop quality and confidence. It does not claim printed OCR accuracy because no ground-truth text file is currently available.

## Status Counts

| exam | total | ok | low_confidence | failed | invalid_crop |
| --- | ---: | ---: | ---: | ---: | ---: |
| FORM1 | 258 | 19 | 87 | 80 | 72 |
| FORM2 | 312 | 18 | 96 | 95 | 103 |
| FORM3 | 276 | 25 | 84 | 62 | 105 |

## Crop And OCR Risk Counts

| exam | empty crop | too_small recorded | low_contrast recorded | backend `none` | empty OCR text | short text length <= 2 | suspicious rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FORM1 | 72 | 0 | 0 | 72 | 155 | 49 | 243 |
| FORM2 | 103 | 0 | 0 | 103 | 198 | 29 | 295 |
| FORM3 | 105 | 0 | 0 | 105 | 167 | 29 | 252 |

Notes:

- Current logs do not expose separate `too_small` or `low_contrast` quality labels, so those counters are `0 recorded`, not a proof that the issue never occurs.
- `backend=none` is currently tied to `invalid_crop` rows that were not sent to OCR. On this machine, Tesseract was available for valid OCR attempts.
- `suspicious rows` counts rows with `failed`, `invalid_crop`, `low_confidence`, empty text, or very short text.

## Representative Debug Images

- FORM1 empty module crop: `/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/debug/page01/printed_ocr/EXAM_FORM1_19283_module.png`
- FORM1 border-contaminated professor crop: `/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/debug/page01/printed_ocr/EXAM_FORM1_19283_professor.png`
- FORM2 empty module crop: `/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/debug/page01/printed_ocr/EXAM_FORM2_19283_module.png`
- FORM3 empty module crop: `/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/debug/page01/printed_ocr/EXAM_FORM3_19283_module.png`
- FORM3 low-confidence professor crop: `/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/debug/page01/printed_ocr/EXAM_FORM3_19283_professor.png`
- FORM3 border-contaminated note crop: `/Users/noir/A2/ComputerVision/PROJECT 2026 -DATABASE-20260530/debug/page01/printed_ocr/EXAM_FORM3_19283_note_max.png`

## Main Interpretation

The OCR wrapper itself is robust: missing or invalid crops do not crash PDF processing, and each row records status, confidence, backend, and crop path. The larger risk is PAGE-01 field alignment. Empty crops and border-contaminated crops indicate that some field boxes are shifted or too tight for the rendered page layout.

## Minimal-Intrusion Improvement Strategy

1. Use `annotations/review_samples/printed_ocr_review_samples.csv` to select the worst fields.
2. Fill `annotations/printed_ocr_ground_truth.csv`.
3. Try field-specific crop padding only for repeated fields such as `module`, `code`, `date`, `note_max`, and `note_valid`.
4. Re-run OCR and compare with ground truth before keeping the change.

Commands:

```bash
python3 scripts/select_review_samples.py
python3 scripts/evaluate_with_ground_truth.py --task printed_ocr --annotations annotations/printed_ocr_ground_truth.csv
```

## Conclusion

The current pipeline is safe and auditable but not yet accuracy-proven for printed OCR. Any crop-margin change should be accepted only if exact/normalized accuracy improves on labeled samples. Without ground truth, the correct report statement is that printed OCR has a robust fallback and documented low-confidence cases, not a measured real accuracy.
