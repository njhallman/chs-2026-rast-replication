# Environment Setup

## Environments

There are three environments where this project runs:

1. **macOS (local)** — Stata is commonly installed at `/Applications/Stata/` and data are stored locally.
2. **Linux** — Install Stata and its required packages independently, then use the standard Python setup below.
3. **Cloud environments** — May need additional configuration; see [Troubleshooting](#troubleshooting).

## Canonical Exact-Reproduction Setup

The canonical environment is recorded in `environment.lock.json`. It pins
Python 3.13.3, the tested macOS/Apple Silicon environment, StataNow/SE 18.5,
and every required Stata add-on. Python artifacts are additionally locked by
cryptographic hashes in `requirements.lock`.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install pip==25.0.1
python -m pip install --require-hashes -r requirements.lock
python tools/verify_environment.py
```

Stata is licensed software and is not distributed with this repository.
Install and license the exact Stata build recorded in `environment.lock.json`.
The required add-on versions are listed in
`environment/stata-requirements.txt`; their installed entry points are
checksummed by the verifier. `Analysis/shared/stata_setup.py` also enforces
the exact versions whenever a Stata-backed analysis starts.

The human-readable `requirements.txt` contains exact Python version pins.
`requirements.lock` is the installation source for a formal reproduction
because it additionally authenticates every permitted package artifact.

For Python-only development on another system, install the same hash lock and
skip the OS/Stata portion of the check:

```bash
python tools/verify_environment.py --python-only
```

Regenerate `requirements.lock` only when intentionally updating dependencies:

```bash
uv pip compile requirements.txt \
  --python-version 3.13.3 \
  --python-platform aarch64-apple-darwin \
  --generate-hashes --no-annotate \
  --output-file requirements.lock
```

After regenerating it, update the corresponding SHA-256 value in
`environment.lock.json` and rerun the clean-room reproduction.

Data are not downloaded during setup. Before running the analysis, public
users must obtain the required inputs independently from their original
providers and place them under `Analysis/Data/`.

Choose the workflow before continuing:

- For an **exact reproduction**, install the same historical-vintage inputs
  used for the paper. Those licensed inputs are not distributed here.
- For an **approximate updated-vintage refresh**, users with their own licenses
  may run the acquisition scripts described in `Analysis/pipeline/README.md`.
  Fresh downloads will not match the published results exactly and may require
  adapting to provider schema changes, supplying manual mappings, and
  configuring a separate local SEC filing archive.

Run analysis scripts with:
```bash
python3 Analysis/run_all.py
# or individual scripts:
python3 Analysis/tables/summary_stats.py
```

## Lazy Data Loading

The analysis looks for data under `Analysis/Data/`. Public users must supply
the required data there. The shared data loader first checks
`Analysis/Data/<subpath>` and returns that local path.

The four main processed datasets are accessed via `shared.data_loader` (which uses `ensure_data_file` internally). Scripts that need other files (e.g., proxy statement CSVs, Audit Analytics data) call `ensure_data_file` directly.

## Troubleshooting

These issues can occur in Linux or cloud environments.

### `sfi` module errors

An incomplete Stata installation can leave the `ado/` directory empty. Without
the ado files, pystata fails with `ModuleNotFoundError: No module named 'sfi'`.

**Fix — manually extract the ado files:**

```bash
# 1. Remove the installed markers so extraction can proceed
rm -f /usr/local/stata/installed.185 /usr/local/stata/installed.180

# 2. Copy compressed ado files from the extracted tar structure
cp /usr/local/stata/unix/linux64/ado.taz /usr/local/stata/ado.tar.Z
cp /usr/local/stata/unix/linux64/base.taz /usr/local/stata/base.tar.Z
cp /usr/local/stata/unix/linux64/bins.taz /usr/local/stata/bins.tar.Z
cp /usr/local/stata/unix/linux64/docs.taz /usr/local/stata/docs.tar.Z
cp /usr/local/stata/unix/linux64/setrwxp /usr/local/stata/setrwxp
chmod 750 /usr/local/stata/setrwxp

# 3. Extract manually
cd /usr/local/stata
gunzip ado.tar.Z base.tar.Z bins.tar.Z docs.tar.Z
tar -xof base.tar && tar -xof bins.tar && tar -xof ado.tar && tar -xof docs.tar
./setrwxp now
rm -f ado.tar base.tar bins.tar docs.tar
date > installed.185 && date > installed.180

# 4. Set Stata to use a Python version it can find (default python3 may not be detected)
# Run this in Stata or via: /usr/local/stata/stata-se -b -e 'python set exec /usr/bin/python3.10, permanently'

# 5. Install required Stata packages
python3 -c "
import stata_setup; stata_setup.config('/usr/local/stata', 'se')
from pystata import stata
for pkg in ['estout', 'ftools', 'reghdfe', 'outreg2', 'coefplot', 'ppmlhdfe']:
    stata.run(f'ssc install {pkg}, replace')
"
```

### SIGILL (exit code 132) on QEMU/virtual CPUs

On some cloud VMs, the virtual CPU lacks instruction set extensions (AVX, SSE4, etc.). This causes SIGILL crashes in modern numpy/pandas/pyarrow and in Stata's shared library when loaded via pystata. Stata may work standalone (`/usr/local/stata/stata-se -b -e 'command'`) but the in-process pystata API will crash.

**Fix — use micromamba with older package versions that don't require AVX:**

```bash
# 1. Install micromamba
curl -L https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C /tmp bin/micromamba
export MAMBA_ROOT_PREFIX=/home/dev/micromamba

# 2. Create conda environment with Python 3.10 and older packages
/tmp/bin/micromamba create -n gda -c conda-forge -y \
    python=3.10 numpy=1.24.4 pandas=2.0.3 pyarrow=12.0.1

# 3. Install pip packages in the conda env
/tmp/bin/micromamba run -n gda pip install stata_setup

# 4. Install Stata packages via pystata in the conda env
/tmp/bin/micromamba run -n gda python -c "
import stata_setup; stata_setup.config('/usr/local/stata', 'se')
from pystata import stata
for pkg in ['estout', 'ftools', 'reghdfe', 'require', 'outreg2', 'coefplot', 'ppmlhdfe']:
    stata.run(f'ssc install {pkg}, replace')
"
```

Then run analysis scripts with:
```bash
export MAMBA_ROOT_PREFIX=/home/dev/micromamba
/tmp/bin/micromamba run -n gda python Analysis/run_all.py
```
