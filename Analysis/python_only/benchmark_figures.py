#!/usr/bin/env python
"""Generate the four Stata-dependent benchmark figures with Python only."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from models import fit_linear_fe


def _setup_repo_imports(repo: Path):
    analysis = str(repo / "Analysis")
    if analysis not in sys.path:
        sys.path.insert(0, analysis)
    from shared import benchmark_utils as bu

    return bu


def _fit_panel(
    panel: pd.DataFrame,
    name: str,
    periods: list[str],
    firm_fe: str,
):
    result = fit_linear_fe(
        panel,
        name=name,
        dependent="retained",
        regressors=periods
        + ["masterorhigher", "top_university", "api", "black", "other"],
        fixed_effects=[firm_fe, "year", "yearfirst"],
        cluster="userid",
    )
    coefficients = result.coefficients.reindex(periods).to_numpy()
    standard_errors = result.standard_errors.reindex(periods).to_numpy()
    return coefficients, standard_errors, int(panel["userid"].nunique())


def _build_top50_fs(repo: Path, bu) -> pd.DataFrame:
    source = pd.read_feather(
        repo / "Analysis" / "Data" / "interim" / "revOtherFs.feather"
    )
    source["startdate"] = pd.to_datetime(source["startdate"], errors="coerce")
    source["enddate"] = pd.to_datetime(source["enddate"], errors="coerce")
    source = source[
        source["startdate"].notna()
        & (source["startdate"] <= source["enddate"])
    ]
    source = source[
        source["highest_degree"].isin(["Bachelor", "Master", "MBA", "Doctor"])
    ]
    source = source[
        ~source["title_raw"].str.contains("intern", case=False, na=False)
    ]
    source = source[source["ultimate_parent_rcid"].notna()]
    source = source[~source["company_raw"].apply(bu.fs_exclude)]
    professional = source[source["role_k1500"].isin(bu.PROFESSIONAL_ROLES)]
    top50 = set(
        professional.groupby("ultimate_parent_rcid")["user_id"]
        .nunique()
        .sort_values(ascending=False)
        .head(50)
        .index
    )
    raw = source[
        source["role_k1500"].isin(bu.PROFESSIONAL_ROLES)
        & source["ultimate_parent_rcid"].isin(top50)
    ].copy()
    raw = raw.sort_values(
        ["user_id", "ultimate_parent_rcid", "startdate"]
    )
    raw["new_spell"] = (
        (raw["user_id"] != raw["user_id"].shift())
        | (
            raw["ultimate_parent_rcid"]
            != raw["ultimate_parent_rcid"].shift()
        )
    ).fillna(True).astype("int8")
    raw["spell_id"] = raw["new_spell"].cumsum()
    raw["spell_startdate"] = raw.groupby("spell_id")["startdate"].transform(
        "min"
    )
    raw["spell_enddate"] = raw.groupby("spell_id")["enddate"].transform("max")
    raw = raw.drop_duplicates(["user_id", "spell_id"], keep="last")
    raw["position_year"] = raw.apply(
        lambda row: list(
            range(
                row["spell_startdate"].year,
                row["spell_enddate"].year + 1,
            )
        ),
        axis=1,
    )
    panel = raw[
        [
            "user_id",
            "ultimate_parent_rcid",
            "sex_predicted",
            "ethnicity_predicted",
            "spell_startdate",
            "spell_enddate",
            "position_year",
            "degree",
            "university_name",
        ]
    ].explode("position_year", ignore_index=True)
    panel["position_year"] = panel["position_year"].astype(int)
    panel = panel.sort_values(
        ["user_id", "position_year", "spell_enddate"]
    ).drop_duplicates(["user_id", "position_year"], keep="last")
    panel = panel[panel["position_year"] <= 2023]
    panel["userid"] = panel["user_id"]
    panel["year"] = panel["position_year"]
    panel["retained"] = (
        panel["spell_enddate"].dt.year > panel["year"]
    ).astype("int8")
    panel["female"] = (panel["sex_predicted"] == "F").astype("int8")
    panel["yearfirst"] = panel["spell_startdate"].dt.year
    ethnicity = panel["ethnicity_predicted"].fillna("")
    panel["api"] = (ethnicity == "API").astype("int8")
    panel["black"] = (ethnicity == "Black").astype("int8")
    panel["other"] = (
        ~ethnicity.isin(["White", "API", "Black", "Hispanic", ""])
    ).astype("int8")
    panel["university_name"] = panel["university_name"].apply(
        lambda value: (
            bu.school_mapping.get(value, "other")
            if pd.notna(value)
            else "other"
        )
    )
    panel["masterorhigher"] = panel["degree"].isin(
        ["Master", "MBA", "Doctor"]
    ).astype("int8")
    panel["top_university"] = (
        panel["university_name"] != "other"
    ).astype("int8")
    bu.add_period_dummies(panel)
    codes = {
        value: index + 1
        for index, value in enumerate(
            sorted(panel["ultimate_parent_rcid"].unique())
        )
    }
    panel["firmkey"] = panel["ultimate_parent_rcid"].map(codes)
    return panel


def _build_b4_tax(repo: Path, bu) -> pd.DataFrame:
    frames = []
    for role in ["tax", "tax accountant", "tax analyst", "tax consultant"]:
        source = pd.read_feather(
            repo
            / "Analysis"
            / "Data"
            / "raw"
            / "revelio"
            / f"revelioPosUsr_role_{role}.feather"
        )
        source["aud_firm"] = source["company_raw"].map(
            bu.AUDIT_FIRM_MAPPING
        )
        frames.append(source[source["aud_firm"].notna()].copy())
    raw = pd.concat(frames, ignore_index=True)
    raw["female"] = (raw["sex_predicted"] == "F").astype("int8")
    ethnicity = raw["ethnicity_predicted"].fillna("")
    raw["api"] = (ethnicity == "API").astype("int8")
    raw["black"] = (ethnicity == "Black").astype("int8")
    raw["other"] = (
        ~ethnicity.isin(["White", "API", "Black", "Hispanic", ""])
    ).astype("int8")
    raw["startdate"] = pd.to_datetime(raw["startdate"], errors="coerce")
    raw["enddate"] = pd.to_datetime(raw["enddate"], errors="coerce")
    raw = raw[
        (raw["country"] == "United States") & raw["startdate"].notna()
    ].copy()
    raw["start_year"] = raw["startdate"].dt.year.clip(lower=1990)
    raw["end_year"] = (
        raw["enddate"].dt.year.fillna(2024).astype(int).clip(upper=2024)
    )
    raw = raw[(raw["end_year"] - raw["start_year"] + 1) > 0]
    raw["position_year"] = [
        list(range(start, end + 1))
        for start, end in zip(raw["start_year"], raw["end_year"])
    ]
    panel = raw[
        [
            "user_id",
            "aud_firm",
            "female",
            "api",
            "black",
            "other",
            "start_year",
            "position_year",
        ]
    ].explode("position_year", ignore_index=True)
    panel["position_year"] = panel["position_year"].astype(int)
    panel = panel.sort_values(
        ["user_id", "position_year", "start_year"]
    ).drop_duplicates(["user_id", "position_year"], keep="last")
    panel["yearfirst"] = panel.groupby("user_id")[
        "position_year"
    ].transform("min")
    following = panel[["user_id", "position_year"]].copy()
    following["position_year"] -= 1
    following["retained"] = 1
    panel = panel.merge(
        following, on=["user_id", "position_year"], how="left"
    )
    panel["retained"] = panel["retained"].fillna(0).astype("int8")
    panel = panel[panel["position_year"] <= 2023].copy()

    education = pd.read_feather(
        repo
        / "Analysis"
        / "Data"
        / "raw"
        / "revelio"
        / "revelioEdu_role_combined.feather"
    )
    education = education[
        education["user_id"].isin(panel["user_id"].unique())
        & education["degree"].isin(["Bachelor", "Master", "MBA", "Doctor"])
    ].copy()
    education["degree_rank"] = education["degree"].map(
        {"Doctor": 4, "MBA": 3, "Master": 2, "Bachelor": 1}
    )
    education["enddate"] = pd.to_datetime(
        education["enddate"], errors="coerce"
    ).fillna(pd.Timestamp("2025-10-01"))
    education = (
        education.sort_values(
            ["user_id", "degree_rank", "enddate"],
            ascending=[False, True, True],
        )
        .groupby("user_id")
        .tail(1)[["user_id", "university_name", "degree"]]
    )
    education["university_name"] = education["university_name"].apply(
        lambda value: bu.school_mapping.get(value, "other")
    )
    panel = panel.merge(education, on="user_id", how="left")
    panel["masterorhigher"] = panel["degree"].isin(
        ["Master", "MBA", "Doctor"]
    ).astype("int8")
    panel["top_university"] = (
        panel["university_name"] != "other"
    ).fillna(False).astype("int8")
    panel["auditorkey"] = panel["aud_firm"].map(bu.AUDIT_FIRM_KEYS)
    panel["year"] = panel["position_year"]
    panel["userid"] = panel["user_id"].astype("category").cat.codes + 1
    bu.add_period_dummies(panel)
    return panel


def _draw_single(
    output: Path,
    periods: list[str],
    labels: list[str],
    audit: tuple[np.ndarray, np.ndarray, int],
    comparison: tuple[np.ndarray, np.ndarray, int],
    comparison_label: str,
    comparison_color: str,
    comparison_marker: str,
    difference_label: str,
    *,
    figsize: tuple[float, float] = (13, 7),
    comparison_markersize: float = 9,
    xtick_fontsize: float = 11,
):
    audit_coef, audit_se, audit_n = audit
    comp_coef, comp_se, comp_n = comparison
    x = np.arange(len(periods))
    fig, ax = plt.subplots(figsize=figsize)
    ax.errorbar(
        x,
        audit_coef,
        yerr=audit_se,
        color="#2171B5",
        marker="o",
        markersize=9,
        linestyle="-",
        linewidth=2.5,
        capsize=4,
        capthick=1.2,
        label=f"Big 4 Audit (n={audit_n:,})",
        zorder=5,
    )
    ax.errorbar(
        x,
        comp_coef,
        yerr=comp_se,
        color=comparison_color,
        marker=comparison_marker,
        markersize=comparison_markersize,
        linestyle="--",
        linewidth=2.5,
        capsize=4,
        capthick=1.2,
        label=f"{comparison_label} (n={comp_n:,})",
        zorder=4,
    )
    ax.axhline(
        0, color="gray", linestyle="--", linewidth=0.8, zorder=1
    )
    post_index = 6 if len(periods) == 11 else 4
    ax.axvspan(
        post_index - 0.5,
        len(periods) - 0.5,
        alpha=0.10,
        color="gray",
        zorder=0,
    )
    ax.text(
        (post_index - 0.5 + len(periods) - 0.5) / 2,
        0.02,
        "Post Form AP",
        ha="center",
        va="bottom",
        fontsize=10,
        color="gray",
        fontstyle="italic",
        transform=ax.get_xaxis_transform(),
    )
    ax.set_xlabel("Period", fontsize=14, labelpad=28)
    ax.set_ylabel(
        "Female × Period coefficient\n(effect on retention probability)",
        fontsize=14,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=xtick_fontsize)
    ax.tick_params(axis="y", labelsize=12)
    ax.legend(fontsize=12)
    differences = (audit_coef - comp_coef) / np.sqrt(
        audit_se**2 + comp_se**2
    )
    for index, z_value in enumerate(differences):
        symbol = (
            "***"
            if abs(z_value) > 2.576
            else "**"
            if abs(z_value) > 1.960
            else "*"
            if abs(z_value) > 1.645
            else ""
        )
        if symbol:
            ax.annotate(
                symbol,
                xy=(index, 0),
                xycoords=("data", "axes fraction"),
                xytext=(0, -42),
                textcoords="offset points",
                ha="center",
                va="top",
                fontsize=9,
                color="#222222",
                annotation_clip=False,
            )
    ax.annotate(
        (
            f"*p\u202f<\u202f0.10\u2003 **p\u202f<\u202f0.05\u2003 "
            f"***p\u202f<\u202f0.01\u2003 ({difference_label})"
        ),
        xy=(0.5, 0),
        xycoords="axes fraction",
        xytext=(0, -78),
        textcoords="offset points",
        ha="center",
        va="top",
        fontsize=8.5,
        color="#555555",
        annotation_clip=False,
    )
    fig.tight_layout()
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (defaults to the checkout containing this file).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Figure output directory. Defaults to the repository path "
            "selected by shared.paths."
        ),
    )
    args = parser.parse_args()
    repo = args.repo.resolve()
    bu = _setup_repo_imports(repo)
    if args.output_dir is None:
        from shared.paths import REPO_DIR, figures_dir

        if os.environ.get("CHS_OUTPUT_DIR"):
            output = Path(figures_dir)
        else:
            output = Path(REPO_DIR) / "PythonOutput" / "Figures"
    else:
        output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    b4 = pd.read_feather(
        repo
        / "Analysis"
        / "Data"
        / "processed"
        / "revB4AudStata.feather"
    )
    bu.add_period_dummies(b4)
    audit = _fit_panel(b4, "b4_audit", bu.PERIODS, "auditorkey")

    bb5 = bu.build_ib_panel(None, bu.BB5_MAPPING, bu.BB5_KEYS, "BB5")
    bb5_result = _fit_panel(bb5, "bb5", bu.PERIODS, "firmkey")
    top50 = _build_top50_fs(repo, bu)
    top50_result = _fit_panel(top50, "top50_fs", bu.PERIODS, "firmkey")
    tax = _build_b4_tax(repo, bu)
    tax_result = _fit_panel(tax, "b4_tax", bu.PERIODS, "auditorkey")

    _draw_single(
        output / "benchmarkBB5IB.png",
        bu.PERIODS,
        bu.SHORT_LABELS,
        audit,
        bb5_result,
        "BB5 Investment Banks",
        "#D62728",
        "^",
        "audit vs. IB difference",
    )
    _draw_single(
        output / "benchmarkOFS.png",
        bu.PERIODS,
        bu.SHORT_LABELS,
        audit,
        top50_result,
        "FS Prof. Top 50",
        "#888888",
        "s",
        "audit vs. FS difference",
    )
    _draw_single(
        output / "benchmarkB4Tax.png",
        bu.PERIODS,
        bu.SHORT_LABELS,
        audit,
        tax_result,
        "Big 4 Tax",
        "#6BAED6",
        "s",
        "audit vs. tax difference",
        figsize=(12, 7),
        comparison_markersize=8,
        xtick_fontsize=12,
    )

    nonb4, annual_firms, other_firms = bu.build_nonb4_audit_panel()
    b4_nb = b4.copy()
    bu.add_nb4_period_dummies(b4_nb)
    audit_nb = _fit_panel(
        b4_nb, "b4_audit_nb", bu.NB4_PERIODS, "auditorkey"
    )
    annual = nonb4[nonb4["at_firm"].isin(annual_firms)].copy()
    annual["auditorkey"] = (
        annual["at_firm"].astype("category").cat.codes + 1
    )
    annual_result = _fit_panel(
        annual, "annual_nonb4", bu.NB4_PERIODS, "auditorkey"
    )
    other = nonb4[nonb4["at_firm"].isin(other_firms)].copy()
    other["auditorkey"] = other["at_firm"].astype("category").cat.codes + 1
    other_result = _fit_panel(
        other, "other_nonb4", bu.NB4_PERIODS, "auditorkey"
    )

    x = np.arange(len(bu.NB4_PERIODS))
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    for ax, result, label, color, marker, title in [
        (
            axes[0],
            annual_result,
            "Annually Inspected AT",
            "#FF7F0E",
            "^",
            "Big 4 Audit vs. Annually Inspected AT",
        ),
        (
            axes[1],
            other_result,
            "Other AT Firms",
            "#2CA02C",
            "s",
            "Big 4 Audit vs. Other AT Firms",
        ),
    ]:
        ax.errorbar(
            x,
            audit_nb[0],
            yerr=audit_nb[1],
            color="#2171B5",
            marker="o",
            markersize=7,
            linestyle="-",
            linewidth=2.2,
            capsize=3,
            capthick=1,
            label=f"Big 4 Audit (n={audit_nb[2]:,})",
            zorder=5,
        )
        ax.errorbar(
            x,
            result[0],
            yerr=result[1],
            color=color,
            marker=marker,
            markersize=7,
            linestyle="--",
            linewidth=2.2,
            capsize=3,
            capthick=1,
            label=f"{label} (n={result[2]:,})",
            zorder=4,
        )
        ax.axhline(
            0, color="gray", linestyle="--", linewidth=0.8, zorder=1
        )
        ax.axvspan(
            3.5,
            len(x) - 0.5,
            alpha=0.10,
            color="gray",
            zorder=0,
        )
        ax.text(
            (3.5 + len(x) - 0.5) / 2,
            0.02,
            "Post Form AP",
            ha="center",
            va="bottom",
            fontsize=9,
            color="gray",
            fontstyle="italic",
            transform=ax.get_xaxis_transform(),
        )
        ax.set_xticks(x)
        ax.set_xticklabels(
            bu.NB4_SHORT_LABELS, fontsize=9, rotation=45, ha="right"
        )
        ax.set_xlabel("Period", fontsize=12)
        ax.tick_params(axis="y", labelsize=10)
        ax.set_title(title, fontsize=12)
        ax.legend(fontsize=9, loc="upper left")
        differences = (audit_nb[0] - result[0]) / np.sqrt(
            audit_nb[1] ** 2 + result[1] ** 2
        )
        for index, z_value in enumerate(differences):
            symbol = (
                "***"
                if abs(z_value) > 2.576
                else "**"
                if abs(z_value) > 1.960
                else "*"
                if abs(z_value) > 1.645
                else ""
            )
            if symbol:
                ax.annotate(
                    symbol,
                    xy=(index, 0),
                    xycoords=("data", "axes fraction"),
                    xytext=(0, -36),
                    textcoords="offset points",
                    ha="center",
                    va="top",
                    fontsize=8,
                    color="#222222",
                    annotation_clip=False,
                )
    axes[0].set_ylabel(
        "Female × Period coefficient\n(effect on retention probability)",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(
        output / "benchmarkATCombined.png", dpi=300, bbox_inches="tight"
    )
    plt.close(fig)

    series = []
    for label, result, periods in [
        ("b4_audit", audit, bu.PERIODS),
        ("bb5", bb5_result, bu.PERIODS),
        ("top50_fs", top50_result, bu.PERIODS),
        ("b4_tax", tax_result, bu.PERIODS),
        ("b4_audit_nb", audit_nb, bu.NB4_PERIODS),
        ("annual_nonb4", annual_result, bu.NB4_PERIODS),
        ("other_nonb4", other_result, bu.NB4_PERIODS),
    ]:
        for period, coefficient, standard_error in zip(
            periods, result[0], result[1]
        ):
            series.append(
                {
                    "series": label,
                    "period": period,
                    "coefficient": coefficient,
                    "standard_error": standard_error,
                    "employees": result[2],
                }
            )
    pd.DataFrame(series).to_csv(
        output / "benchmark_plot_data_python.csv", index=False
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
