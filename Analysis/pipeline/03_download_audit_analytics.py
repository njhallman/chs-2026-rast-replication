"""
03_download_audit_analytics.py — Download Audit Analytics data from WRDS.

Data source: WRDS Audit Analytics (audit schema)
Authentication: WRDS username/password + Duo two-factor authentication
Table: audit.audit_comp_feed34_revised_audit_opinions
    Auditor-client engagement records with auditor name, CIK, fiscal year,
    and audit opinion details.

Key columns used by analysis scripts:
    - company_fkey   (CIK — links to BoardEx/EDGAR for client identification)
    - auditor_name   (Big 4 firm name for filtering)
    - fiscal_year_of_op
    - fiscal_year_end_op

Used by:
    - Analysis/tables/mechanisms_table.py (link audit committee data to B4 firms)
    - Analysis/figures/mechanism_variation_metro.py (same)
    - Analysis/pipeline/08_fetch_proxy_keywords.py (match B4 clients to proxy statements)

Output:
    Analysis/Data/raw/audit_analytics/audit_audit_comp_feed34_revised_audit_opinions.csv

Usage:
    python Analysis/pipeline/03_download_audit_analytics.py
    python Analysis/pipeline/03_download_audit_analytics.py --force

This requires the user's own WRDS and Audit Analytics permissions. A current
download is for an approximate updated-vintage analysis and need not match the
paper.
"""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import wrds
import pandas as pd

from shared.paths import data_dir

OUTPUT_DIR = os.path.join(data_dir, 'raw', 'audit_analytics')
os.makedirs(OUTPUT_DIR, exist_ok=True)

WRDS_TABLE = 'audit.audit_comp_feed34_revised_audit_opinions'
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'audit_audit_comp_feed34_revised_audit_opinions.csv')

EXPECTED_COLUMNS = ['company_fkey', 'auditor_name', 'fiscal_year_of_op', 'fiscal_year_end_op']


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Download a current Audit Analytics vintage using the user's own "
            "WRDS/Audit Analytics permissions; results may differ from the paper"
        )
    )
    parser.add_argument('--force', action='store_true', help='Re-download existing file')
    args = parser.parse_args()

    print("=" * 60)
    print("  03_download_audit_analytics.py — Audit Analytics from WRDS")
    print("=" * 60)

    if os.path.exists(OUTPUT_FILE) and not args.force:
        print(f"\n  SKIP (exists): {OUTPUT_FILE}")
        size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
        print(f"  Size: {size_mb:.1f} MB")
        # Validate
        df = pd.read_csv(OUTPUT_FILE, nrows=5)
        missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
        if missing:
            print(f"  WARNING: Missing expected columns: {missing}")
        else:
            print("  Validation passed.")
        return

    print(f"\n  Table: {WRDS_TABLE}")
    print("\nWARNING: This requires WRDS Duo 2FA. Watch for the push notification.")
    print("Connecting to WRDS...\n")

    conn = wrds.Connection()

    print(f"  Downloading {WRDS_TABLE}...", end='', flush=True)
    df = conn.raw_sql(f"SELECT * FROM {WRDS_TABLE}")
    print(f" {len(df):,} rows, {df.shape[1]} cols")

    # Validate columns
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        print(f"  WARNING: Missing expected columns: {missing}")
        print(f"  Available: {list(df.columns)}")

    print(f"  Unique CIKs: {df['company_fkey'].nunique():,}")

    # Save as CSV to match the format downstream scripts expect
    df.to_csv(OUTPUT_FILE, index=False)
    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"  Saved: {OUTPUT_FILE} ({size_mb:.1f} MB)")

    conn.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
