# Data access

The repository contains code but does not distribute Revelio Labs, BoardEx,
Audit Analytics, WRDS, or other commercially licensed data. It also does not
distribute derived data when redistribution is restricted by the source
license.

Public users must obtain the source data independently from the original
providers under their own licenses and permissions. The required directory
layout and vintages are documented in
`Analysis/pipeline/README.md`. Place licensed files under `Analysis/Data/`;
that directory is ignored by Git.

This repository does not provide credentials, licensed datasets, or access to
remote storage.

Stata must likewise be installed and licensed independently by each
replicator. This repository does not provide Stata installers or licenses.

Public-source inputs, including Census/OMB and IPEDS files, can be downloaded
by the numbered scripts described in `Analysis/pipeline/README.md`.

## Exact reproduction versus an updated-vintage refresh

The formal exact reproduction path requires the historical input vintage used
for the paper. Because that snapshot includes licensed data, it is not
distributed through this repository.

The repository also includes optional acquisition scripts for researchers who
already have their own authorized access. These scripts can query Revelio
Labs, BoardEx, and Audit Analytics through WRDS and download specified public
Census/OMB and IPEDS inputs. Each user must arrange and authenticate all WRDS,
Revelio, BoardEx, Audit Analytics, and other licensed access independently
under their own permissions.

Running the acquisition scripts today creates a new data vintage. Provider
schemas, coverage, corrections, and availability change over time, so the
result is suitable for an approximate updated-vintage analysis, not an exact
reproduction of the published output.

The refresh workflow is not fully automatic. It also relies on project-specific
firm and geography mappings and, for proxy-statement measures, a separately
obtained local SEC filing archive. Other licensed or manually prepared inputs
used by individual analyses must likewise be supplied independently. See
`Analysis/pipeline/README.md` for the expected file contracts without any
credentials or storage details.
