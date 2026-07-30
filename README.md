This repository contains the code used to create the paper at
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4678211.

The repository publishes reproduction code only. It does not distribute the
underlying data, including Revelio and other commercial or licensed inputs.
Public users must obtain all required inputs independently from the original
providers under their own licenses and permissions; see
[`DATA_ACCESS.md`](DATA_ACCESS.md).

## Setup

- Canonical Python 3.13.3, recorded in `.python-version`
- Hash-locked Python artifacts in `requirements.lock`
- StataNow/SE 18.5 with exact add-on versions in
  `environment/stata-requirements.txt`
- Independently obtained data placed under `Analysis/Data/`

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install pip==25.0.1
python -m pip install --require-hashes -r requirements.lock
python tools/verify_environment.py

```

The strict verifier checks the exact successful clean-room environment,
including OS build, architecture, Stata binaries, and Stata add-on checksums.
See `SETUP.md` for development and noncanonical-platform instructions.

## Running the Analysis

There are two distinct workflows:

1. **Formal exact reproduction.** The published results were generated from a
   fixed historical data vintage that cannot be redistributed. Researchers who
   independently possess the matching licensed inputs may install them under
   `Analysis/Data/` and run the commands below.
2. **Optional data refresh.** The numbered acquisition scripts under
   `Analysis/pipeline/` can help users with their own WRDS and source-provider
   permissions build an approximate, updated-vintage dataset. Provider
   coverage and schemas change, so refreshed data will not reproduce the
   published tables and figures exactly.

```bash
# Exact path after installing the matching historical inputs locally
python Analysis/pipeline/06_build_interim.py
python Analysis/pipeline/07_prepare_data.py

# Generate all tables and figures
python Analysis/run_all.py
```

See `Analysis/pipeline/README.md` for the full pipeline documentation.
See `DATA_ACCESS.md` before using any acquisition script.
The machine-readable mapping from each published output to its generator is
in `reproduction_manifest.json`.

## Optional Python-only path

Users without Stata can reproduce all 12 tables and eight figures with the
independently validated Python compatibility path:

```bash
python -m pip install -r environment/python-only-requirements.txt
python Analysis/run_all.py --python-only
```

Outputs are written below `PythonOutput/` and do not overwrite the committed
Stata reference artifacts. See [`PYTHON_ONLY.md`](PYTHON_ONLY.md) for setup,
rerun instructions, statistical implementation details, and validation
results.
