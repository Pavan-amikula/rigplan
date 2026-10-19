# Local verification record

Verified locally on 19 October 2026 with Python 3.13.4, NumPy 2.2.6, pandas 2.3.0, SciPy 1.15.3, scikit-learn 1.7.0, Streamlit 1.66.0 and PyArrow 23.0.1.

- Original 76,601,704-byte UCI ZIP downloaded successfully; archive checksum recorded in `data/processed/provenance.json`.
- Extracted every sensor channel; 2,205 rows, 34 mean/std response features, 1,449 stable cycles.
- Executed the default CLI benchmark and generated all audit artifacts. Numerical results are recorded in `reports/summary.json` rather than duplicated here.
- `python -m pytest -q`: 15 tests passed after the finishing changes. Checks include interaction rank, coverage, infeasible plans, missing factor pairs, selection independence from responses, split isolation, repeat uniqueness, schedule transitions and generated-artifact integrity. Two added checks confirm that the development study excludes the original holdout and produces complete group-level errors and coverage evidence.
- `python scripts/check_dashboard.py`: initial render and changes to repeat count, pair coverage, setting budget, cycle replay and sensor choice all passed without application exceptions.
- Opened the local server in the in-app browser and visually reviewed its rendered overview; adjusted narrow-panel layout to avoid clipped metric values.
- Executed `rigplan study`: nine scenarios across three inner condition-group folds, with 27 fold-level plan evaluations and 108 out-of-fold group errors per scenario. Retaining all settings with six repeats was the smallest development-screen candidate; this is exploratory, not a newly validated final plan.

Cloud jobs, Docker image execution, physical rig operation and prospective validation were not run. The statistical quality gate **fails**, independently of the passing software tests. Software correctness does not establish engineering acceptance.
