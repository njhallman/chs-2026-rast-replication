"""
Run all tables and figures in sequence.

Usage:
    python Analysis/run_all.py            # run everything
    python Analysis/run_all.py --tables   # tables only
    python Analysis/run_all.py --figures  # figures only
    python Analysis/run_all.py --python-only

Each script can also be run individually, e.g.:
    python Analysis/tables/extended_period_tables.py
"""
import sys, os, subprocess, argparse, time, shutil

_dir = os.path.dirname(os.path.abspath(__file__))


def run(script_path, label, env=None):
    rel = os.path.relpath(script_path)
    print(f"\n{'='*60}")
    print(f"  Running: {rel}")
    print(f"{'='*60}")
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=os.path.dirname(_dir),
        env=env,
    )
    elapsed = time.time() - t0
    status = "OK" if result.returncode == 0 else f"FAILED (code {result.returncode})"
    print(f"  {label}: {status}  ({elapsed:.0f}s)")
    return result.returncode == 0


TABLE_SCRIPTS = [
    # Descriptive tables
    (os.path.join(_dir, 'tables', 'roles_table.py'),                'rolesTable.tex'),
    (os.path.join(_dir, 'tables', 'top_companies.py'),              'topCompanies.tex'),
    (os.path.join(_dir, 'tables', 'nonb4_firms.py'),                'nonB4FirmsTable.tex'),
    (os.path.join(_dir, 'tables', 'sample_design.py'),              'sampleDesign.tex'),
    (os.path.join(_dir, 'tables', 'variable_definitions.py'),       'VariableDefinitions.tex'),
    (os.path.join(_dir, 'tables', 'summary_stats.py'),              'summaryStats.tex'),
    # Main results
    (os.path.join(_dir, 'tables', 'extended_period_tables.py'),     'mainB4Table.tex'),
    (os.path.join(_dir, 'tables', 'mechanisms_table.py'),           'mechanismsTable.tex'),
    (os.path.join(_dir, 'tables', 'outside_options.py'),            'destinationQualityPost.tex'),
    (os.path.join(_dir, 'tables', 'rank_interaction.py'),           'rankInteraction.tex'),
    (os.path.join(_dir, 'tables', 'robustness_models.py'),         'robustnessModels.tex'),
]

FIGURE_SCRIPTS = [
    # Main figures
    (os.path.join(_dir, 'figures', 'stack_plot.py'),                        'stackPlot.png'),
    (os.path.join(_dir, 'figures', 'mechanism_variation_metro.py'),         'mechanism_variation_metro.png'),
    (os.path.join(_dir, 'figures', 'retention_gap_map.py'),                 'retentionGapMap.png'),
    (os.path.join(_dir, 'figures', 'supply_vs_entry.py'),                   'supplyVsEntry.png'),
    # Benchmark figures
    (os.path.join(_dir, 'benchmarks', 'fig_top5_ib_extended.py'),          'benchmarkBB5IB.png, benchmarkOFS.png'),
    (os.path.join(_dir, 'benchmarks', 'fig_at_combined.py'),               'benchmarkATCombined.png'),
    (os.path.join(_dir, 'benchmarks', 'fig_b4_nonaudit.py'),               'benchmarkB4Tax.png'),
]

PYTHON_ONLY_TABLE_SCRIPTS = [
    # These generators were already Python-native.
    (os.path.join(_dir, 'tables', 'roles_table.py'),                'rolesTable.tex'),
    (os.path.join(_dir, 'tables', 'top_companies.py'),              'topCompanies.tex'),
    (os.path.join(_dir, 'tables', 'nonb4_firms.py'),                'nonB4FirmsTable.tex'),
    (os.path.join(_dir, 'tables', 'sample_design.py'),              'sampleDesign.tex'),
    (os.path.join(_dir, 'tables', 'variable_definitions.py'),       'VariableDefinitions.tex'),
    # One Python translation fits and writes all six Stata-backed tables.
    (os.path.join(_dir, 'python_only', 'run_tables.py'),
     'six Python analytical tables'),
]

PYTHON_ONLY_FIGURE_SCRIPTS = [
    # These generators were already Python-native.
    (os.path.join(_dir, 'figures', 'stack_plot.py'),                'stackPlot.png'),
    (os.path.join(_dir, 'figures', 'mechanism_variation_metro.py'), 'mechanism_variation_metro.png'),
    (os.path.join(_dir, 'figures', 'retention_gap_map.py'),         'retentionGapMap.png'),
    (os.path.join(_dir, 'figures', 'supply_vs_entry.py'),           'supplyVsEntry.png'),
    # One Python translation fits and draws all four Stata-backed benchmarks.
    (os.path.join(_dir, 'python_only', 'benchmark_figures.py'),
     'four Python benchmark figures'),
]


def main():
    parser = argparse.ArgumentParser(description='Run all analysis scripts.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--tables',  action='store_true', help='Run table scripts only')
    group.add_argument('--figures', action='store_true', help='Run figure scripts only')
    parser.add_argument(
        '--python-only',
        action='store_true',
        help='Reproduce every output without importing or starting Stata',
    )
    parser.add_argument(
        '--output-dir',
        help=(
            'Write Tables/ and Figures/ below this directory. '
            'Defaults to PythonOutput for --python-only and LaTeX otherwise.'
        ),
    )
    args = parser.parse_args()

    table_scripts = (
        PYTHON_ONLY_TABLE_SCRIPTS if args.python_only else TABLE_SCRIPTS
    )
    figure_scripts = (
        PYTHON_ONLY_FIGURE_SCRIPTS if args.python_only else FIGURE_SCRIPTS
    )
    scripts = []
    if args.tables:
        scripts = table_scripts
    elif args.figures:
        scripts = figure_scripts
    else:
        scripts = table_scripts + figure_scripts

    output_dir = args.output_dir
    if output_dir is None and args.python_only:
        output_dir = os.path.join(os.path.dirname(_dir), 'PythonOutput')
    child_env = None
    if output_dir:
        output_dir = os.path.abspath(output_dir)
        os.makedirs(os.path.join(output_dir, 'Tables'), exist_ok=True)
        os.makedirs(os.path.join(output_dir, 'Figures'), exist_ok=True)
        child_env = os.environ.copy()
        child_env['CHS_OUTPUT_DIR'] = output_dir

    failures = []
    t_start = time.time()

    for script_path, label in scripts:
        ok = run(script_path, label, env=child_env)
        if not ok:
            failures.append(label)

    if output_dir and not args.figures:
        static_table = os.path.join(
            os.path.dirname(_dir), 'LaTeX', 'Tables', 'firmNamesTable.tex'
        )
        shutil.copy2(
            static_table,
            os.path.join(output_dir, 'Tables', 'firmNamesTable.tex'),
        )

    total = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"  Finished in {total/60:.1f} min")
    if failures:
        print(f"  FAILED: {', '.join(failures)}")
        sys.exit(1)
    else:
        print("  All scripts completed successfully.")
        if output_dir:
            print(f"  Outputs: {output_dir}")


if __name__ == '__main__':
    main()
