# Environment Setup

## Environments

There are three environments where this project runs:

1. **macOS (local)** — Stata is commonly installed at `/Applications/Stata/` and data are stored locally.
2. **Linux** — Install Stata and its required packages independently, then use the standard Python setup below.
3. **Cloud environments** — May need additional configuration; see [Troubleshooting](#troubleshooting).

## Standard Setup

Create an isolated Python environment and install the pinned dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install and license Stata SE independently, then install the required Stata
packages: `estout`, `ftools`, `reghdfe`, `require`, `outreg2`, `coefplot`, and
`ppmlhdfe`.

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
