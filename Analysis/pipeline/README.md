# Data Pipeline

Numbered scripts that acquire, process, and prepare data for the paper.

## Two different uses

### Formal exact replication

Exact replication requires the historical input vintage used for the paper.
The licensed snapshot is not distributed. Researchers who independently
possess the matching files can place them in the layout below and begin with
scripts 06 and 07.

### Optional updated-vintage refresh

Scripts 01-05 and 08 are retained as research provenance and as a starting
point for licensed users who want to assemble a newer data vintage. Users must
obtain WRDS, Revelio Labs, BoardEx, Audit Analytics, and every other licensed
input independently under their own permissions. Current provider data,
coverage, and schemas may differ from the paper vintage, so this route produces
an approximate updated-vintage analysis and will not replicate the published
tables and figures exactly.

## Script Sequence

| # | Script | Source | Auth | Description |
|---|--------|--------|------|-------------|
| 01 | `01_download_revelio.py` | WRDS Revelio | Duo 2FA | Position files by role + education data + B4 career histories |
| 02 | `02_download_boardex.py` | WRDS BoardEx | Duo 2FA | Board composition and committee data |
| 03 | `03_download_audit_analytics.py` | WRDS Audit Analytics | Duo 2FA | Auditor-client engagement records (audit opinions) |
| 04 | `04_download_census.py` | Census/OMB | Public | ZIP-to-CBSA crosswalk from Census ZCTA + OMB delineation |
| 05 | `05_download_ipeds.py` | NCES IPEDS | Public | Accounting degree completions by year/institution |
| 06 | `06_build_interim.py` | Local | None | Raw Revelio → interim datasets |
| 07 | `07_prepare_data.py` | Local | None | Interim → processed analysis-ready panels |
| 08 | `08_fetch_proxy_keywords.py` | local-edgar | None | Extract DEI keywords from SEC proxy statements |

## Data Sources for 06_build_interim.py

Script 06 prefers the **bulk partition files** (`revelioFsPosUsr_1-4_of_4.feather`) from the original January 2025 Revelio download. These are the data that produced the published tables (145,573 users, 713,614 person-years). If bulk files are not present, it falls back to per-role files from `01_download_revelio.py`.

That fallback is a refresh path, not an equivalent reconstruction of the
historical bulk files. The Revelio role schema has changed since the paper
vintage.

## Dependencies

Scripts 01-05 download raw data and can run in any order (01-03 share WRDS auth).

Scripts 06-08 must run in order:
- `06` requires raw Revelio files (bulk partitions or per-role files from `01`)
- `07` requires interim files from `06`
- `08` requires Audit Analytics from `03` and a separately obtained local SEC
  filing archive configured with `LOCAL_EDGAR_ARCHIVE`

Additional project-specific dependencies include a manually curated
CBSA-to-Revelio metro mapping and firm-name mappings used during preparation.
Some analyses also require licensed or manually prepared inputs not downloaded
by scripts 01-05. These inputs must be obtained independently.

## Usage

```bash
# Rebuild from existing raw data (no WRDS connection needed)
python Analysis/pipeline/06_build_interim.py
python Analysis/pipeline/07_prepare_data.py
python Analysis/run_all.py

# Approximate updated-vintage refresh (requires your own provider permissions)
python Analysis/pipeline/01_download_revelio.py --force
python Analysis/pipeline/02_download_boardex.py --force
python Analysis/pipeline/03_download_audit_analytics.py --force
python Analysis/pipeline/04_download_census.py
python Analysis/pipeline/05_download_ipeds.py
python Analysis/pipeline/06_build_interim.py
python Analysis/pipeline/07_prepare_data.py
python Analysis/pipeline/08_fetch_proxy_keywords.py
python Analysis/run_all.py
```

Fresh-data results should be interpreted as an updated-vintage analysis and
are expected to differ from the published output.

## Data Directory Layout

```
Analysis/Data/
├── raw/
│   ├── revelio/
│   │   ├── revelioFsPosUsr_{1-4}_of_4.feather   Bulk position data (Jan 2025, preferred by 06)
│   │   ├── revelioPosUsr_role_*.feather          Per-role position files (from 01, fallback)
│   │   ├── revelioEdu_role_combined.feather       Education data
│   │   └── revelio_b4_users_all_positions.feather B4 auditor complete career histories
│   ├── boardex/          3 board composition feather files
│   ├── audit_analytics/  Auditor-client engagement CSV
│   ├── census/           ZIP-CBSA crosswalk + OMB reference
│   └── ipeds/            Accounting degree completions CSVs
├── interim/
│   ├── revB4Aud.feather          Big 4 auditor positions (from 06)
│   └── revOtherFs.feather        Other FS positions (from 06)
└── processed/
    ├── revB4AudStata.feather     Regression-ready B4 panel (from 07)
    ├── revB4AudExp.feather       Exploration B4 panel (from 07)
    ├── revOtherFsStata.feather   Regression-ready Other FS panel (from 07)
    ├── revOtherFsExp.feather     Exploration Other FS panel (from 07)
    └── sample_counts.json        Filtering audit trail (from 07)
```
