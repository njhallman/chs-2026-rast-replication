# Python-only replication

The repository includes an optional Python-only execution path for users who
do not have Stata. It reuses every generator that was already Python-native
and translates only the Stata-backed regressions, tests, tables, and benchmark
figures.

The formal exact-replication environment remains the authoritative workflow.
The Python path is an independently validated compatibility implementation.
It does not import, start, or require Stata.

## Setup

Start with the normal Python environment:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install pip==25.0.1
python -m pip install --require-hashes -r requirements.lock
python tools/verify_environment.py --python-only
```

On Windows, activate with `.venv\Scripts\activate` instead. Then install the
one additional estimator dependency:

```bash
python -m pip install -r environment/python-only-requirements.txt
```

The strict environment verifier should be run before this last command because
it intentionally rejects packages outside the canonical Stata workflow's
allowlist.

The processed inputs are still required under `Analysis/Data/`. See
[`DATA_ACCESS.md`](DATA_ACCESS.md); no licensed data are included here.

## Run

```bash
python Analysis/run_all.py --python-only
```

This writes 12 tables and eight figures below `PythonOutput/` so the committed
Stata reference artifacts are not overwritten:

```text
PythonOutput/
  Tables/
  Figures/
```

Useful variants:

```bash
python Analysis/run_all.py --python-only --tables
python Analysis/run_all.py --python-only --figures
python Analysis/run_all.py --python-only --output-dir path/to/output
```

The Python-only table and benchmark modules can also be run directly:

```bash
python Analysis/python_only/run_tables.py
python Analysis/python_only/benchmark_figures.py
```

## Statistical compatibility

High-dimensional linear models use `pyfixest` with iterative singleton
removal, absorbed fixed effects, CRV1 employee clustering, and HC1 robust
covariance where the Stata specifications request it. Linear combinations and
Welch tests are computed in Python.

The Cox robustness model uses a direct Breslow partial likelihood with Stata's
multiple-record risk interval convention, `entry < failure_time <= exit`.
It also handles regressors absorbed by year effects, separated zero-failure
year levels, and Lin-Wei employee-clustered covariance. This detail matters:
the default repeated-record boundary behavior in common Python Cox libraries
does not replicate Stata's estimates for this sample.

## Validation against the official vintage

The Python path was run on Windows with Python 3.13.3 and the official
historical data snapshot, then compared with the committed paper artifacts:

- all 112 reported model cells matched at three decimal places;
- all 84 summary-statistic cells matched at three decimal places;
- all model observation counts and employee-cluster counts matched;
- all reported adjusted R-squared values matched at three decimal places;
- six of 12 tables were byte-identical, with the remaining differences due to
  LaTeX formatting rather than reported values;
- all eight figures replicated the same plotted results, with structural image
  similarity from 0.948 to 1.000.

The remaining differences are cosmetic rendering and formatting differences
between Stata and Python. None changes a sign, significance conclusion,
substantive implication, or interpretation reported in the paper.
