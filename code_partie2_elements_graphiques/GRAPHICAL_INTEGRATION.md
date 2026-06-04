# Graphical Module Integration

This module reads the graphical elements of the exam forms with low-level image
processing: thresholding, connected components, morphology helpers, row/column
clustering and simple rotation/deskew utilities.

## Files Added

- `graphical/components.py`: low-level image utilities, thresholding, connected components, checkbox scoring.
- `graphical/page01.py`: PAGE-01 graphical reader.
- `graphical/exam.py`: generic exam-page A-H checkbox reader.
- `graphical/cryptogram.py`: cryptogram crop and comparison.
- `graphical/preprocess.py`: Otsu thresholding, morphology and deskew helpers.
- `graphical/run_graphical_demo.py`: sample smoke test on `database/1..3`.
- `graphical/requirements_graphical.txt`: minimal dependencies.

## PAGE-01 API

```python
from graphical import read_page01_graphics

page = read_page01_graphics("EXAM_FORM1_63272.jpg")

student_id_grid = page.student_id
group_grid = page.group
conditions = page.conditions.as_page01_rows()
signature_crop = page.signature_crop
cryptogram_crop = page.cryptogram.crop if page.cryptogram else None
```

The `conditions` dictionary maps directly to the graphical rows in `PAGE-01`:

```python
{
    "Notes de cours": 1,
    "Notes manuscrites": 0,
    "Ordinateur portable": 1,
    "Calculatrice ": 0,
    "Feuilles brouillon": 1,
}
```

`page.signature_crop` can be passed to the recognition module for signature
identification.

With the current local `reconnaissance` package:

```python
import numpy as np
from graphical import read_page01_graphics
from reconnaissance import RecognitionService

page = read_page01_graphics("EXAM_FORM1_63272.jpg")
service = RecognitionService.from_signature_folder("STUDENT_CLASS_SIGNATURES")

recognition_result = service.recognize_page_01(
    signature_crop=np.asarray(page.signature_crop),
    printed_crops={},
    handwritten_crops={},
)

student_id_signature = recognition_result.student_id_signature
signature_ok = recognition_result.signature_accepted
```

`np.asarray(page.signature_crop)` is recommended because `reconnaissance`
types its image inputs as paths or numpy arrays.

## Cryptogram API

```python
from graphical import validate_cryptograms

validation = validate_cryptograms(page_images)
cryptogram_ok = 1 if validation.valid else 0
```

Cryptograms must be compared inside one multi-page PDF/form. They are not
expected to match across different exam forms.

## EXAM Sheet API

```python
from graphical import read_exam_choices

questions = read_exam_choices(page_image, choice_labels="ABCDEFGH")
for question in questions:
    print(question.question, question.choices)
```

Each `question.choices` dictionary has values `0` or `1` for `CHOIX A` to
`CHOIX H`. If the general module crops the answer-table area first, pass the
crop directly or use the `roi=` argument to improve robustness.

## Smoke Test

```bash
python graphical/run_graphical_demo.py
```

Current sample result on `database/1..3`:

- Student ID grid: `3/3`
- Group grid: `3/3`
- PAGE-01 graphical conditions: `3/3`
- Cryptogram crop: found on `3/3`
