# Methods For Report

## Overall Pipeline

Text diagram:

```text
Input FORM images / PDFs
        |
        v
PDF rendering and page orientation correction
        |
        v
PAGE-01 processing -----------------------+
        |                                  |
        |                                  v
        |                         student ID grid
        |                         group grid
        |                         exam conditions
        |                         cryptogram
        |                         signature crop
        |                         printed OCR crops
        |
        v
Exam-page processing ---------------------+
        |                                  |
        |                                  v
        |                         QCM checkbox stacks
        |                         numeric answer boxes
        |                         handwritten crops
        |
        v
Recognition module
        |
        +--> signature matching
        +--> printed OCR
        +--> handwritten number baseline
        |
        v
Excel outputs
        |
        +--> Program 1: FORMX_PRESENCES.xlsx
        +--> Program 2: one workbook per PDF with PAGE-01 and EXAM sheets
```

## Preprocessing

The structure module performs:

- PDF page rendering with PyMuPDF at 300 DPI.
- Defensive page orientation correction based on dark-pixel density in top and bottom bands.
- Safe image conversion with fallback for unreadable or invalid images.
- Per-file exception handling so one bad image/PDF does not stop the batch.

The graphical and recognition modules sanitize image arrays:

- Convert to grayscale.
- Replace `NaN` and `inf` values.
- Reject empty arrays and invalid crops.
- Clamp crop boxes to image bounds.

## Segmentation Methods

PAGE-01 field cropping uses fixed relative or pixel ROIs because the exam form is semi-structured.

Exam numeric answer boxes are detected with:

- Grayscale conversion.
- Binary thresholding.
- Contour extraction.
- Quadrilateral approximation.
- Size and aspect-ratio filtering.
- Grouping mantisse, exponent, and unit areas by relative position.

## Graphical Recognition

Student ID, group, conditions, and QCM are handled by low-level image processing, not high-level semantic detectors.

Used operations:

- Thresholding for dark components.
- Connected components.
- Geometry filters: width, height, area, aspect ratio.
- Fill-ratio and inner-dark scoring.
- Position clustering.
- Regular row/column or vertical-stack consistency checks.

QCM detection:

- First extracts form-box candidates from connected components.
- Rejects numeric answer rectangles using size/aspect/stack logic.
- Uses vertical A-D stack regularity for the real FORM pages.
- Keeps horizontal row/column clustering as fallback.
- Logs every candidate to `qcm_candidates.csv`.

This complies with the low-level CV requirement because it uses explicit thresholding, morphology-style filtering, connected components, and geometric rules instead of an automatic checkbox detector.

## Cryptogram

Cryptogram validation is handled in the graphical module. It extracts the relevant graphical pattern from pages and compares consistency between pages. Failures are caught and logged instead of stopping the PDF batch.

## Signature Matching

Input: cropped signature image.

Preprocessing:

- Grayscale conversion.
- Otsu thresholding.
- Foreground crop.
- Aspect-ratio preserving resize to `192 x 96`.

Descriptor:

- HOG with cell sizes `8`, `10`, `12`, `16`.
- Zoning density on a `6 x 12` grid.
- Weighted distance fusion.

Classification:

- Compare the query signature to all reference signatures in `SIGNATURES/`.
- Predict the student ID of the nearest reference sample.
- Reject if the best distance is above `SIGNATURE_THRESHOLD`.
- Mark ambiguous if the top-1/top-2 margin is below `SIGNATURE_AMBIGUOUS_MARGIN`.

Default parameters:

- `SIGNATURE_THRESHOLD = 0.82`
- `SIGNATURE_AMBIGUOUS_MARGIN = 0.02`

The CLI can override both values.

## Printed OCR

Printed fields use a Tesseract wrapper when available.

Field-specific whitelists:

- `code`: uppercase letters, digits, hyphen.
- `date`: digits and slash.
- `module`: alphanumeric and dot.
- `number`: digits, comma, dot, minus.
- `student_id`: digits.
- `unit`: letters.

Robustness:

- If Tesseract is missing, the OCR wrapper returns empty text with `ocr_unavailable`.
- Empty, too-small, low-contrast, or noisy crops are logged in `printed_ocr_debug.csv`.
- OCR errors do not stop Excel generation.

## Handwritten Recognition

Handwritten numeric recognition is a baseline:

- Grayscale.
- Median denoising.
- Binarization.
- Border removal.
- Morphological opening.
- Foreground crop.
- Connected-component character segmentation.
- Digit classification with an SVM trained on `sklearn.datasets.load_digits`.

The sklearn accuracy is only a classifier sanity check. Real exam-crop quality is evaluated separately through `handwritten_debug.csv`, with statuses:

- `valid`
- `empty`
- `too_small`
- `too_noisy`
- `border_contamination`
- `low_contrast`

## Parameters

Central parameters are in `config.py`:

- `SIGNATURE_THRESHOLD = 0.82`
- `SIGNATURE_AMBIGUOUS_MARGIN = 0.02`
- `HANDWRITING_MIN_CONFIDENCE = 0.45`
- `QCM_CHECKED_THRESHOLD = 0.40`
- `DEBUG_DIR = PROJECT_ROOT / "debug"`

## Limitations

- OCR quality depends on PAGE-01 crop alignment and Tesseract availability.
- Handwritten recognition is not trained on real exam crops.
- Some handwritten crops still contain box borders, which increases failures.
- Signature threshold is validated on the signature database, not on independently labeled FORM submissions.
- FORM ordering for mixed QCM/numeric questions is based on detected y-position and can still be imperfect if extra numeric boxes are detected.
