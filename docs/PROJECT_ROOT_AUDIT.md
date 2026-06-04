# Project Root Audit

Date: 2026-06-04

## Keep In Git

Source files:

- `main.py`
- `config.py`
- `data_discovery.py`
- `debug_utils.py`
- `excel_writer.py`
- `validate_outputs.py`
- `code_partie1_stucture_generale/`
- `code_partie2_elements_graphiques/`
- `recognition/`
- `scripts/`

Configuration:

- `.gitignore`
- `requirements.txt`
- `requirements_project.txt`
- `requirements_reconnaissance.txt`
- `code_partie2_elements_graphiques/requirements_graphical.txt`

Documentation:

- `README.md`
- `docs/`
- `PROJET COMPUTER VISION IG2045-2026 ENG.pdf` can be kept if the team wants the assignment statement in the repository. It is small, but not required for runtime.

Validation scripts:

- `validate_outputs.py`
- `scripts/final_check.py`
- `recognition/evaluate.py`
- `run_reconnaissance_demo.py`
- `code_partie2_elements_graphiques/run_graphical_demo.py`

## Keep Locally / Do Not Commit By Default

Raw data:

- `FORM1/`
- `FORM2/`
- `FORM3/`
- `SIGNATURES/`
- `data/`, `dataset/`, `samples/` if used later

Generated output:

- `debug/`
- `output/`
- `*_RESULTS/`
- generated `.xlsx` files
- generated `.joblib` models

Temporary/cache files:

- `__pycache__/`
- `*.pyc`
- `.DS_Store`
- `.pytest_cache/`
- virtual environments

## Current Dataset Sizes

- `FORM1/`: about `125 MB`
- `FORM2/`: about `139 MB`
- `FORM3/`: about `170 MB`
- `SIGNATURES/`: about `13 MB`
- `debug/`: about `110 MB` after verification
- `output/`: about `199 MB` after verification

These folders are ignored by `.gitignore`. If the team decides to version a small sample dataset, put it in a dedicated folder and adjust `.gitignore` intentionally.
