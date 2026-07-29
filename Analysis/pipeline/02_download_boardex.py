"""
02_download_boardex.py — Download BoardEx board-level data from WRDS.

Data source: WRDS BoardEx (boardex schema)
Authentication: WRDS username/password + Duo two-factor authentication
Tables used:
    - boardex.na_wrds_org_summary       (director records: gender, role, company IDs, CIK)
    - boardex.na_wrds_company_profile   (company identifiers and HQ state)
    - boardex.na_board_dir_committees   (committee memberships for audit committee analysis)

These tables are used by the mechanisms analysis to measure audit committee
gender composition as a proxy for client-side pressure on audit firms.

Outputs (all in Analysis/Data/raw/boardex/):
    - na_wrds_org_summary.feather
    - na_wrds_company_profile.feather
    - na_board_dir_committees.feather

Usage:
    python Analysis/pipeline/02_download_boardex.py
    python Analysis/pipeline/02_download_boardex.py --force

This requires the user's own WRDS and BoardEx permissions. A current download
is for an approximate updated-vintage analysis and need not match the paper.
"""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import wrds
from shared.paths import data_dir

OUTPUT_DIR = os.path.join(data_dir, 'raw', 'boardex')
os.makedirs(OUTPUT_DIR, exist_ok=True)

TABLES = {
    'na_wrds_org_summary':       'boardex.na_wrds_org_summary',
    'na_wrds_company_profile':   'boardex.na_wrds_company_profile',
    'na_board_dir_committees':   'boardex.na_board_dir_committees',
}


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Download a current BoardEx vintage using the user's own WRDS "
            "and BoardEx permissions; results may differ from the paper"
        )
    )
    parser.add_argument('--force', action='store_true', help='Re-download existing files')
    args = parser.parse_args()

    print("=" * 60)
    print("  02_download_boardex.py — BoardEx data from WRDS")
    print("=" * 60)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nWARNING: This requires WRDS Duo 2FA. Watch for the push notification.")
    print("Connecting to WRDS...\n")

    conn = wrds.Connection()

    for name, sql_table in TABLES.items():
        output_file = os.path.join(OUTPUT_DIR, f'{name}.feather')
        if os.path.exists(output_file) and not args.force:
            print(f"  SKIP (exists): {name}")
        else:
            print(f"  Downloading {sql_table}...", end='', flush=True)
            df = conn.raw_sql(f"SELECT * FROM {sql_table}")
            print(f" {len(df):,} rows, {df.shape[1]} cols")
            df.to_feather(output_file, compression='zstd')

    conn.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
