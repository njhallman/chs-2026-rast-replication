#!/usr/bin/env python
"""Write Python-only LaTeX counterparts for the six Stata-backed tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def star(p_value: float) -> str:
    if p_value < 0.01:
        return r"\sym{***}"
    if p_value < 0.05:
        return r"\sym{**}"
    if p_value < 0.10:
        return r"\sym{*}"
    return ""


def number(value: float) -> str:
    return f"{value:.3f}"


def table_preamble(columns: int) -> list[str]:
    return [
        r"{",
        r"\def\sym#1{\ifmmode^{#1}\else\(^{#1}\)\fi}",
        rf"\begin{{tabular}}{{l*{{{columns}}}{{D{{.}}{{.}}{{-1}}}}}}",
        r"\toprule",
    ]


def table_end() -> list[str]:
    return [r"\bottomrule", r"\end{tabular}", r"}"]


def rows_for_terms(
    estimates: pd.DataFrame,
    models: list[str],
    terms: list[tuple[str, str]],
) -> list[str]:
    indexed = estimates.set_index(["model", "term"])
    lines = []
    for term, label in terms:
        coefficients = []
        standard_errors = []
        for model in models:
            key = (model, term)
            if key not in indexed.index:
                coefficients.append("")
                standard_errors.append("")
                continue
            row = indexed.loc[key]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            coefficients.append(
                f"{number(float(row.coefficient))}"
                f"{star(float(row.p_value))}"
            )
            standard_errors.append(
                f"({number(float(row.standard_error))})"
            )
        lines.append(label + " & " + " & ".join(coefficients) + r"\\")
        lines.append(" & " + " & ".join(standard_errors) + r"\\")
    return lines


def metadata_rows(
    estimates: pd.DataFrame,
    models: list[str],
    *,
    controls: bool = True,
    fixed_effects: str = "C,Y,E",
) -> list[str]:
    meta = estimates.groupby("model", sort=False).first()
    nobs = [f"{int(meta.loc[name, 'nobs']):,}" for name in models]
    employees = [
        (
            f"{int(meta.loc[name, 'clusters']):,}"
            if pd.notna(meta.loc[name, "clusters"])
            else ""
        )
        for name in models
    ]
    adjusted = [
        (
            f"{float(meta.loc[name, 'adjusted_r2']):.3f}"
            if pd.notna(meta.loc[name, "adjusted_r2"])
            else ""
        )
        for name in models
    ]
    lines = [
        r"\midrule",
        "Observations & " + " & ".join(nobs) + r"\\",
        "Unique employees & " + " & ".join(employees) + r"\\",
        "Adjusted R-squared & " + " & ".join(adjusted) + r"\\",
    ]
    if controls:
        lines.append("Controls & " + " & ".join(["Yes"] * len(models)) + r"\\")
    lines.append(
        "Fixed effects & "
        + " & ".join([fixed_effects] * len(models))
        + r"\\"
    )
    return lines


def write_regression_table(
    path: Path,
    estimates: pd.DataFrame,
    models: list[str],
    terms: list[tuple[str, str]],
    titles: list[str] | None = None,
    fixed_effects: str = "C,Y,E",
) -> None:
    lines = table_preamble(len(models))
    lines.append(
        " & "
        + " & ".join(
            rf"\multicolumn{{1}}{{c}}{{({index})}}"
            for index in range(1, len(models) + 1)
        )
        + r"\\"
    )
    if titles:
        lines.append(
            " & "
            + " & ".join(
                rf"\multicolumn{{1}}{{c}}{{{title}}}" for title in titles
            )
            + r"\\"
        )
    lines.append(r"\midrule")
    lines.extend(rows_for_terms(estimates, models, terms))
    lines.extend(
        metadata_rows(
            estimates, models, fixed_effects=fixed_effects
        )
    )
    lines.extend(table_end())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(path: Path, summary: pd.DataFrame) -> None:
    labels = {
        "retained": r"\RETAINED",
        "promo": r"\PROMOTED",
        "post_formap": r"\POSTFORMAP",
        "top_university": r"\TOPUNIVERSITY",
        "masterorhigher": r"\MASTERS",
        "api": r"\APIRACE",
        "black": r"\BLACKRACE",
        "other": r"\OTHERRACE",
        "ac_fem_pct_sf": r"AC Female \%",
        "dei_proportion_firm": "Gender Keywords",
        "salary_pct_change": r"Salary \% Change",
        "log_gap": "Log Gap Days",
    }
    first = summary.iloc[0]
    lines = [
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        (
            f" & Total (N = {int(first.total_n):,})"
            f" & Female (N = {int(first.female_n):,})"
            f" & Male (N = {int(first.male_n):,})"
            r" & Difference\\"
        ),
        r" & mean/sd & mean/sd & mean/sd & p\\",
        r"\midrule",
    ]
    for row in summary.itertuples(index=False):
        label = labels[row.variable]
        lines.append(
            f"{label} & {row.total_mean:.3f} & {row.female_mean:.3f}"
            f" & {row.male_mean:.3f} & {row.welch_p:.3f}\\\\"
        )
        lines.append(
            f" & ({row.total_sd:.3f}) & ({row.female_sd:.3f})"
            f" & ({row.male_sd:.3f}) & \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_rank(
    path: Path,
    estimates: pd.DataFrame,
    combinations: pd.DataFrame,
) -> None:
    models = ["rank_retention", "rank_promotion"]
    terms = [
        (
            "female_post_staff",
            r"\FEMALE\ $\times$ Post Form AP $\times$ Staff",
        ),
        (
            "female_post_senior",
            r"\FEMALE\ $\times$ Post Form AP $\times$ Senior",
        ),
        (
            "female_post_mgrplus",
            r"\FEMALE\ $\times$ Post Form AP $\times$ Manager+",
        ),
        ("female_staff", r"\FEMALE\ $\times$ Staff"),
        ("female_senior", r"\FEMALE\ $\times$ Senior"),
        ("female_mgrplus", r"\FEMALE\ $\times$ Manager+"),
    ]
    lines = table_preamble(2)
    lines.extend(
        [
            r" & \multicolumn{1}{c}{(1)} & \multicolumn{1}{c}{(2)}\\",
            (
                r" & \multicolumn{1}{c}{DV = Retained}"
                r" & \multicolumn{1}{c}{DV = Promoted}\\"
            ),
            r"\midrule",
        ]
    )
    lines.extend(rows_for_terms(estimates, models, terms))
    lines.extend(
        [
            r"\midrule",
            (
                r"\multicolumn{3}{l}{\textit{Post-period net female gap"
                r" (sum of 3-way + 2-way):}}\\[4pt]"
            ),
        ]
    )
    combined = combinations.set_index(["model", "term"])
    for label, rank in [
        ("Staff", "staff"),
        ("Senior", "senior"),
        ("Manager+", "mgrplus"),
    ]:
        coefficient_cells = []
        error_cells = []
        for model in models:
            row = combined.loc[(model, f"post_net_female_{rank}")]
            coefficient_cells.append(
                f"{float(row.coefficient):.3f}{star(float(row.p_value))}"
            )
            error_cells.append(f"({float(row.standard_error):.3f})")
        lines.append(
            rf"\quad {label} & "
            + " & ".join(coefficient_cells)
            + r"\\"
        )
        lines.append(" & " + " & ".join(error_cells) + r"\\")
    lines.extend(metadata_rows(estimates, models))
    lines.extend(table_end())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    results = args.results_dir.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    estimates = pd.read_csv(results / "model_estimates_python.csv")
    combinations = pd.read_csv(results / "linear_combinations_python.csv")
    summary = pd.read_csv(results / "summary_statistics_python.csv")

    write_summary(output / "summaryStats.tex", summary)
    write_regression_table(
        output / "mainB4Table.tex",
        estimates,
        ["main_b4"],
        [
            ("female_pre_2004", r"\FEMALExPREIV"),
            ("female_2004_2005", r"\FEMALExIVtoV"),
            ("female_2006_2007", r"\FEMALExVItoVII"),
            ("female_2008_2009", r"\FEMALExVIIItoIX"),
            ("female_2010_2011", r"\FEMALExXtoXI"),
            ("female_2012_2013", r"\FEMALExXIItoXIII"),
            ("female_2014_2015", r"\FEMALExXIVtoXV"),
            ("female_2016_2017", r"\FEMALExXVItoXVII"),
            ("female_2018_2019", r"\FEMALExXVIIItoXIX"),
            ("female_2020_2021", r"\FEMALExXXtoXXI"),
            ("female_2022_2023", r"\FEMALExXXIItoXXIII"),
            ("masterorhigher", r"\MASTERS"),
            ("top_university", r"\TOPUNIVERSITY"),
            ("api", r"\APIRACE"),
            ("black", r"\BLACKRACE"),
            ("other", r"\OTHERRACE"),
        ],
        [r"\shortstack{Big 4 Auditors\\ DV = Retained}"],
    )
    write_regression_table(
        output / "mechanismsTable.tex",
        estimates,
        [
            "mechanism_ac",
            "mechanism_dei",
            "mechanism_formap",
            "mechanism_horse_race",
        ],
        [
            ("female_ac", r"\FEMALE\ $\times$ AC Female \%"),
            ("ac_fem_pct_sf", r"AC Female \%"),
            ("female_dei", r"\FEMALE\ $\times$ Gender Keywords"),
            ("dei_proportion_firm", "Gender Keywords"),
            ("female_post_formap", r"\FEMALExPOSTFORMAP"),
            ("female", r"\FEMALE"),
        ],
    )
    write_regression_table(
        output / "destinationQualityPost.tex",
        estimates,
        ["destination_salary", "destination_log_gap"],
        [("female_post", r"\FEMALExPOST"), ("female", r"\FEMALE")],
        [
            r"\shortstack{Leavers w/ Next Job\\ DV = Salary \% Change}",
            r"\shortstack{Leavers w/ Next Job\\ DV = Log Gap Days}",
        ],
        fixed_effects="F,Y,C",
    )
    write_rank(output / "rankInteraction.tex", estimates, combinations)
    write_regression_table(
        output / "robustnessModels.tex",
        estimates,
        ["robustness_cox", "robustness_location"],
        [("female_post", r"\FEMALExPOST"), ("female", r"\FEMALE")],
        [
            r"\shortstack{Auditors\\ DV = Hazard}",
            r"\shortstack{Auditors\\ DV = Retained}",
        ],
        fixed_effects="Y,E / C,E,Y*M",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
