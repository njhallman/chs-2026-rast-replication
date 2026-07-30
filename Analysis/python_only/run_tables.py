#!/usr/bin/env python
"""Generate every Stata-backed analytical table using Python only."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import numpy as np
import pandas as pd

from models import (
    ModelResult,
    add_period_dummies,
    fit_cox_ph,
    fit_linear_fe,
    model_to_long,
    summary_statistics,
)


PERIODS = [
    "female_pre_2004",
    "female_2004_2005",
    "female_2006_2007",
    "female_2008_2009",
    "female_2010_2011",
    "female_2012_2013",
    "female_2014_2015",
    "female_2016_2017",
    "female_2018_2019",
    "female_2020_2021",
    "female_2022_2023",
]
CONTROLS = ["masterorhigher", "top_university", "api", "black", "other"]
SUMMARY_VARIABLES = [
    "retained",
    "promo",
    "post_formap",
    "top_university",
    "masterorhigher",
    "api",
    "black",
    "other",
    "ac_fem_pct_sf",
    "dei_proportion_firm",
    "salary_pct_change",
    "log_gap",
]


def _fit_models(
    data: pd.DataFrame,
) -> tuple[list[ModelResult], list[dict]]:
    models: list[ModelResult] = []
    linear_combinations: list[dict] = []

    main = data.copy()
    old_periods = [
        name
        for name in main.columns
        if name.startswith("female_") and name != "female"
    ]
    main = main.drop(columns=old_periods, errors="ignore")
    add_period_dummies(main)
    models.append(
        fit_linear_fe(
            main,
            name="main_b4",
            dependent="retained",
            regressors=PERIODS + CONTROLS,
            fixed_effects=["auditorkey", "year", "yearfirst"],
            cluster="userid",
        )
    )

    mechanisms = data.copy()
    specifications = [
        (
            "mechanism_ac",
            mechanisms["ac_fem_pct_sf"].notna(),
            ["female_ac", "female", "ac_fem_pct_sf"] + CONTROLS,
        ),
        (
            "mechanism_dei",
            mechanisms["dei_proportion_firm"].notna(),
            ["female_dei", "female", "dei_proportion_firm"] + CONTROLS,
        ),
        (
            "mechanism_formap",
            pd.Series(True, index=mechanisms.index),
            ["female_post_formap", "female", "post_formap"] + CONTROLS,
        ),
        (
            "mechanism_horse_race",
            mechanisms["ac_fem_pct_sf"].notna()
            & mechanisms["dei_proportion_firm"].notna(),
            [
                "female_ac",
                "female_dei",
                "female_post_formap",
                "female",
                "ac_fem_pct_sf",
                "dei_proportion_firm",
                "post_formap",
            ]
            + CONTROLS,
        ),
    ]
    for name, sample, regressors in specifications:
        models.append(
            fit_linear_fe(
                mechanisms.loc[sample],
                name=name,
                dependent="retained",
                regressors=regressors,
                fixed_effects=["auditorkey", "year", "yearfirst"],
                cluster="userid",
            )
        )

    last_years = (
        data.sort_values(["userid", "year"]).groupby("userid").tail(1)
    )
    leavers = last_years[
        (last_years["retained"] == 0) & (last_years["year"] <= 2023)
    ].copy()
    leavers = leavers.rename(
        columns={"year": "exit_year", "auditorkey": "aud_firm"}
    )
    destination_regressors = [
        "female_post",
        "female",
        "post_formap",
        "masterorhigher",
        "api",
        "black",
        "other",
    ]
    for name, dependent in [
        ("destination_salary", "salary_pct_change"),
        ("destination_log_gap", "log_gap"),
    ]:
        models.append(
            fit_linear_fe(
                leavers,
                name=name,
                dependent=dependent,
                regressors=destination_regressors,
                fixed_effects=["aud_firm", "exit_year", "yearfirst"],
                robust=True,
            )
        )

    ranked = data[data["badrankdummy"] == 0].copy()
    rank_regressors = [
        "female_post_staff",
        "female_post_senior",
        "female_post_mgrplus",
        "female_staff",
        "female_senior",
        "female_mgrplus",
        "post_senior",
        "post_mgrplus",
        "senior",
        "mgrplus",
        "post_formap",
        "time_in_rank",
    ] + CONTROLS
    retention = fit_linear_fe(
        ranked,
        name="rank_retention",
        dependent="retained",
        regressors=rank_regressors,
        fixed_effects=["auditorkey", "year", "yearfirst"],
        cluster="userid",
    )
    models.append(retention)

    promotion_sample = ranked[
        (ranked["positionrank"] < 6) & (ranked["retained"] == 1)
    ].copy()
    promotion = fit_linear_fe(
        promotion_sample,
        name="rank_promotion",
        dependent="promo",
        regressors=rank_regressors,
        fixed_effects=["auditorkey", "year", "yearfirst"],
        cluster="userid",
    )
    models.append(promotion)
    for result in [retention, promotion]:
        for rank in ["staff", "senior", "mgrplus"]:
            estimate, standard_error, p_value = result.linear_combination(
                {
                    f"female_post_{rank}": 1.0,
                    f"female_{rank}": 1.0,
                }
            )
            linear_combinations.append(
                {
                    "model": result.name,
                    "term": f"post_net_female_{rank}",
                    "coefficient": estimate,
                    "standard_error": standard_error,
                    "p_value": p_value,
                }
            )

    # Stata drops observations with missing values in an absorbed FE.  Avoid
    # turning missing metro codes into a literal "<NA>" fixed-effect group.
    location = data[data["metro_area_code"].notna()].copy()
    location["year_metro"] = (
        location["year"].astype("Int64").astype(str)
        + "#"
        + location["metro_area_code"].astype("Int64").astype(str)
    )
    models.append(
        fit_cox_ph(
            data,
            name="robustness_cox",
            duration="time",
            status="termination",
            regressors=[
                "female_post",
                "female",
                "post_formap",
                "top_university",
                "masterorhigher",
                "api",
                "black",
                "other",
            ],
            categorical_effects=["auditorkey", "year"],
            subject="userid",
        )
    )
    models.append(
        fit_linear_fe(
            location,
            name="robustness_location",
            dependent="retained",
            regressors=["female_post", "female", "post_formap"]
            + [
                "top_university",
                "masterorhigher",
                "api",
                "black",
                "other",
            ],
            fixed_effects=["auditorkey", "yearfirst", "year_metro"],
            cluster="userid",
        )
    )

    return models, linear_combinations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results-dir",
        type=Path,
        help="Optional directory for raw estimates and Cox diagnostics.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional table output directory.",
    )
    args = parser.parse_args()

    analysis_dir = Path(__file__).resolve().parents[1]
    if str(analysis_dir) not in sys.path:
        sys.path.insert(0, str(analysis_dir))
    from shared.data_loader import load_b4_stata
    from shared.paths import REPO_DIR, tables_dir
    if args.output_dir:
        table_output = args.output_dir.resolve()
    elif os.environ.get("CHS_OUTPUT_DIR"):
        table_output = Path(tables_dir)
    else:
        table_output = Path(REPO_DIR) / "PythonOutput" / "Tables"
    table_output.mkdir(parents=True, exist_ok=True)

    started = time.time()
    data = load_b4_stata()
    print(
        f"Loaded {len(data):,} employee-years and "
        f"{data['userid'].nunique():,} employees."
    )

    summary_data = data.copy()
    summary_data.loc[
        summary_data["badrankdummy"] == 1, "promo"
    ] = np.nan
    summary = summary_statistics(summary_data, SUMMARY_VARIABLES)

    models, combinations = _fit_models(data)
    diagnostics = {
        model.name: model.diagnostics
        for model in models
        if model.diagnostics is not None
    }
    estimate_frames = [model_to_long(model) for model in models]
    estimates = pd.DataFrame(
        [
            record
            for frame in estimate_frames
            for record in frame.to_dict("records")
        ]
    )
    combinations_frame = pd.DataFrame(combinations)

    manifest = {
        "python_version": sys.version,
        "input_rows": int(len(data)),
        "input_employees": int(data["userid"].nunique()),
        "models_run": [model.name for model in models],
        "elapsed_seconds": time.time() - started,
    }

    with tempfile.TemporaryDirectory(prefix="chs-python-tables-") as temp:
        result_dir = Path(temp)
        summary.to_csv(
            result_dir / "summary_statistics_python.csv", index=False
        )
        estimates.to_csv(
            result_dir / "model_estimates_python.csv", index=False
        )
        combinations_frame.to_csv(
            result_dir / "linear_combinations_python.csv", index=False
        )
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("write_tables.py")),
                "--results-dir",
                str(result_dir),
                "--output-dir",
                str(table_output),
            ],
            check=True,
        )

        if args.results_dir:
            output = args.results_dir.resolve()
            output.mkdir(parents=True, exist_ok=True)
            summary.to_csv(
                output / "summary_statistics_python.csv", index=False
            )
            estimates.to_csv(
                output / "model_estimates_python.csv", index=False
            )
            combinations_frame.to_csv(
                output / "linear_combinations_python.csv", index=False
            )
            (output / "model_diagnostics.json").write_text(
                json.dumps(diagnostics, indent=2), encoding="utf-8"
            )
            (output / "run_manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
