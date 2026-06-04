# Recognition Module Integration

This document describes the interface between the recognition part and the two other modules.

## Files Added

- `recognition/signature.py`: signature identification from a cropped signature image.
- `recognition/handwriting.py`: basic handwritten number recognition.
- `recognition/ocr.py`: printed text OCR wrapper.
- `recognition/pipeline.py`: simple facade for integration.
- `recognition/evaluate.py`: signature cross-validation.
- `run_reconnaissance_demo.py`: trains baseline models and runs a quick prediction.
- `requirements_reconnaissance.txt`: Python dependencies for this part.

## Expected Inputs From Other Modules

The recognition module does not locate fields in the page. It expects already cropped images:

- `signature_crop`: inner signature area only, without the surrounding rectangle when possible.
- `printed_crops`: dictionary of printed-text fields, for example `module`, `professor`, `date`, `code`, `max_grade`, `validation_grade`.
- `handwritten_crops`: dictionary of handwritten numeric fields, for example `q3_mantisse`, `q3_exposant`, `q6_mantisse`.

The structure/general module should handle PDF loading, rotation correction, page normalization, Excel creation, and final writing. The graphical module should handle grid reading, checkbox reading, cryptogram reading, and field cropping.

## API Example

```python
from recognition import RecognitionService

service = RecognitionService.from_signature_folder("SIGNATURES", threshold=0.82)

result = service.recognize_page_01(
    signature_crop=signature_image,
    printed_crops={
        "module": module_crop,
        "professor": professor_crop,
        "code": code_crop,
    },
    handwritten_crops={}
)

student_id_signature = result.student_id_signature
signature_ok = result.signature_accepted
```

For exam-page numeric answers:

```python
pred = service.recognize_handwritten_number(mantisse_crop)
value = pred.text
confidence = pred.confidence
```

For printed OCR:

```python
pred = service.recognize_printed_text(code_crop)
text = pred.text
confidence = pred.confidence
```

For printed OCR with a predefined whitelist:

```python
pred = service.recognize_printed_field(code_crop, "code")
```

Available field types are `code`, `date`, `module`, `name`, `number`, `student_id`, and `unit`. These presets choose both a character whitelist and a Tesseract page segmentation mode adapted to single-field crops.

## Output Contract

For `PAGE-01`:

- `student_id_signature`: predicted student ID from the signature database. Empty if rejected.
- `signature_accepted`: `True` if the best signature distance is below the threshold.
- `signature_confidence`: margin between the best and second-best signature match.
- `printed_fields[name].text`: OCR result for printed fields.
- `handwritten_fields[name].text`: OCR result for handwritten numeric fields.

The integration code should compare:

- `studentID_grid` from the graphical module.
- `student_id_signature` from this recognition module.

Recommended Excel rule:

- `Validation signature = 1` if both IDs are non-empty and identical.
- `Validation signature = 0` otherwise.

For the `EXAM` sheet:

- Checkbox choices (`CHOIX A` to `CHOIX H`) come from the graphical module.
- `MANTISSE` and `EXPOSANT` can use `recognize_handwritten_number`.
- `UNITE` currently needs printed/OCR backend or a small custom classifier if handwritten units must be recognized.

## Current Performance

Command:

```bash
python3 -m recognition.evaluate --signatures SIGNATURES --threshold 0.82
```

Measured on the provided signature database with leave-one-out validation:

- Samples: `1220`
- Top-1 signature ID accuracy: about `86.0%`
- Accepted-correct rate at threshold `0.82`: about `71.7%`
- Accepted-wrong rate at threshold `0.82`: about `3.8%`
- Rejection rate at threshold `0.82`: about `21.5%`
- Ambiguous rate at threshold `0.82`: about `3.0%`

The signature distance is now a weighted fusion of HOG descriptors at cell sizes `8`, `10`, `12`, `16`, and `6 x 12` zoning densities. The threshold was recalibrated from validation scores. Increasing it accepts more signatures but may increase wrong acceptances.

The handwritten digit recognizer is still a baseline trained on `sklearn.datasets.load_digits`, but its internal validation accuracy is now about `99.6%` after preserving grayscale features and adding small translation augmentation. This number is not a real exam-handwriting score.

Printed OCR is now active on this machine:

- Tesseract version: `5.5.2`
- Installed language data: `eng`, `osd`, `snum`
- Demo smoke fields recognized by `run_reconnaissance_demo.py`: `S1-01-G1`, `62034`, `3.745`

## Real FORM Verification Outputs

The integrated pipeline was run on all locally available real FORM datasets:

```bash
python3 main.py FORM1 --results-dir output/verification_FORM1_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM1_FINAL --exam-root FORM1

python3 main.py FORM2 --results-dir output/verification_FORM2_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM2_FINAL --exam-root FORM2

python3 main.py FORM3 --results-dir output/verification_FORM3_FINAL --signature-threshold 0.82 --signature-ambiguous-margin 0.02
python3 validate_outputs.py output/verification_FORM3_FINAL --exam-root FORM3
```

Results:

- FORM1: Program 1 `32 / 32` rows, Program 2 `43 / 43` PDF workbooks.
- FORM2: Program 1 `22 / 22` rows, Program 2 `52 / 52` PDF workbooks.
- FORM3: Program 1 `42 / 42` rows, Program 2 `46 / 46` PDF workbooks.
- All checked workbooks contain `PAGE-01` and `EXAM` sheets.
- Real handwritten crop debug is saved in each results folder as `handwritten_debug.csv`.
- Real signature score debug is saved in each results folder as `signature_scores.csv`.
- Printed OCR debug is saved in each results folder as `printed_ocr_debug.csv`.
- QCM candidate audit is saved in each results folder as `qcm_candidates.csv`.

Full verification details are in `docs/EVALUATION_SUMMARY.md` and `docs/VERIFICATION_REPORT.md`.

## Important Limitations

Printed OCR requires an OCR engine. The wrapper uses the local `tesseract` command, parses TSV confidence values, and falls back to an empty result with confidence `0.0` if Tesseract is missing on another machine. Install it on macOS with `brew install tesseract`.

Handwritten digit recognition is a baseline trained from `sklearn.datasets.load_digits`, not from the exam handwriting. It is useful for a working end-to-end chain, but accuracy should be measured again if we collect crops from the provided forms and train/validate on them.

## Recommended Cropping Rules

- Correct page rotation before cropping.
- Crop signature inside the signature box, excluding borders and labels.
- Crop each handwritten number field tightly, but leave a small margin around the ink.
- For decimals and exponents, give the whole field to `recognize_handwritten_number`; it segments connected components internally.
- Avoid passing full answer rows to the recognition module. Segmentation should happen before recognition.
