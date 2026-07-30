"""Python-only estimators matching the Stata specifications in the package.

The main linear models use pyfixest's high-dimensional fixed-effect solver.
Its default singleton removal and CRV1 covariance are the closest direct
Python analogues to ``reghdfe ..., vce(cluster ...) version(5)``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
import pandas as pd
from pyfixest.estimation import feols
from scipy import stats

from cox import fit_stata_style_cox


@dataclass
class ModelResult:
    name: str
    dependent: str
    coefficients: pd.Series
    standard_errors: pd.Series
    p_values: pd.Series
    covariance: pd.DataFrame
    nobs: int
    adjusted_r2: float | None
    within_adjusted_r2: float | None
    clusters: int | None
    fixed_effects: tuple[str, ...]
    backend: str = "pyfixest.feols"
    diagnostics: dict | None = None

    def linear_combination(
        self, terms: dict[str, float]
    ) -> tuple[float, float, float]:
        names = list(terms)
        weights = np.array([terms[name] for name in names], dtype=float)
        beta = self.coefficients.reindex(names).to_numpy(dtype=float)
        vcov = self.covariance.loc[names, names].to_numpy(dtype=float)
        estimate = float(weights @ beta)
        standard_error = float(math.sqrt(max(weights @ vcov @ weights, 0.0)))
        if standard_error == 0:
            p_value = 0.0 if estimate else 1.0
        elif self.clusters and self.clusters > 1:
            p_value = float(
                2
                * stats.t.sf(
                    abs(estimate / standard_error),
                    df=self.clusters - 1,
                )
            )
        else:
            p_value = float(
                2 * stats.norm.sf(abs(estimate / standard_error))
            )
        return estimate, standard_error, p_value


def _formula(
    dependent: str, regressors: Iterable[str], fixed_effects: Iterable[str]
) -> str:
    rhs = " + ".join(regressors) or "1"
    fixed = " + ".join(fixed_effects)
    return f"{dependent} ~ {rhs}" + (f" | {fixed}" if fixed else "")


def fit_linear_fe(
    data: pd.DataFrame,
    *,
    name: str,
    dependent: str,
    regressors: list[str],
    fixed_effects: list[str],
    cluster: str | None = None,
    robust: bool = False,
) -> ModelResult:
    """Fit a linear model with absorbed fixed effects.

    ``fixef_rm='singleton'`` intentionally mirrors reghdfe's iterative
    singleton removal. CRV1 is used for one-way clustered standard errors;
    HC1 is used for Stata's ``vce(robust)`` specifications.
    """
    if cluster and robust:
        raise ValueError("Choose clustered or robust covariance, not both.")

    required = list(
        dict.fromkeys(
            [dependent]
            + regressors
            + fixed_effects
            + ([cluster] if cluster else [])
        )
    )
    model_data = data.loc[:, required].dropna()
    absorbed: list[str] = []
    estimable: list[str] = []
    for regressor in regressors:
        is_absorbed = any(
            model_data.groupby(effect, observed=True)[regressor]
            .nunique(dropna=False)
            .max()
            <= 1
            for effect in fixed_effects
        )
        if is_absorbed:
            absorbed.append(regressor)
        else:
            estimable.append(regressor)

    covariance_spec: str | dict[str, str]
    if cluster:
        covariance_spec = {"CRV1": cluster}
    elif robust:
        covariance_spec = "HC1"
    else:
        covariance_spec = "iid"

    model = feols(
        _formula(dependent, estimable, fixed_effects),
        data=model_data,
        vcov=covariance_spec,
        fixef_rm="singleton",
        copy_data=False,
        store_data=False,
        lean=True,
    )
    names = [str(value) for value in model._coefnames]
    covariance = pd.DataFrame(
        np.asarray(model._vcov, dtype=float),
        index=names,
        columns=names,
    )
    # pyfixest's _G is counted on the actual estimation sample after
    # listwise deletion and iterative singleton removal.  Counting on the
    # input frame would overstate Stata's e(N_clust).
    clusters = (
        int(model._G[0])
        if cluster
        else (int(model._N) if robust else None)
    )
    return ModelResult(
        name=name,
        dependent=dependent,
        coefficients=model.coef().rename(index=str),
        standard_errors=model.se().rename(index=str),
        p_values=model.pvalue().rename(index=str),
        covariance=covariance,
        nobs=int(model._N),
        adjusted_r2=float(model._adj_r2),
        within_adjusted_r2=float(model._adj_r2_within),
        clusters=clusters,
        fixed_effects=tuple(fixed_effects),
        diagnostics={"absorbed_regressors": absorbed},
    )


def fit_cox_ph(
    data: pd.DataFrame,
    *,
    name: str,
    duration: str,
    status: str,
    regressors: list[str],
    categorical_effects: list[str],
    subject: str,
) -> ModelResult:
    """Fit the strict-open-left Stata repeated-record Cox specification."""
    fitted = fit_stata_style_cox(
        data,
        duration=duration,
        status=status,
        regressors=regressors,
        categorical_effects=categorical_effects,
        subject=subject,
    )
    names = fitted.names
    covariance_values = fitted.covariance
    standard_errors = fitted.standard_errors
    p_values = 2 * stats.norm.sf(
        np.abs(fitted.coefficients / standard_errors)
    )
    covariance = pd.DataFrame(
        covariance_values,
        index=names,
        columns=names,
    )
    return ModelResult(
        name=name,
        dependent="hazard",
        coefficients=pd.Series(
            fitted.coefficients, index=names
        ),
        standard_errors=pd.Series(
            standard_errors, index=names
        ),
        p_values=pd.Series(
            p_values, index=names
        ),
        covariance=covariance,
        nobs=fitted.nobs,
        adjusted_r2=None,
        within_adjusted_r2=None,
        clusters=fitted.clusters,
        fixed_effects=tuple(categorical_effects),
        backend="Python strict Breslow + Lin-Wei clustered sandwich",
        diagnostics=fitted.diagnostics,
    )


def add_period_dummies(data: pd.DataFrame) -> pd.DataFrame:
    periods = {
        "female_pre_2004": data["year"] < 2004,
        "female_2004_2005": data["year"].isin([2004, 2005]),
        "female_2006_2007": data["year"].isin([2006, 2007]),
        "female_2008_2009": data["year"].isin([2008, 2009]),
        "female_2010_2011": data["year"].isin([2010, 2011]),
        "female_2012_2013": data["year"].isin([2012, 2013]),
        "female_2014_2015": data["year"].isin([2014, 2015]),
        "female_2016_2017": data["year"].isin([2016, 2017]),
        "female_2018_2019": data["year"].isin([2018, 2019]),
        "female_2020_2021": data["year"].isin([2020, 2021]),
        "female_2022_2023": data["year"].isin([2022, 2023]),
    }
    for name, condition in periods.items():
        data[name] = data["female"] * condition.astype("int8")
    return data


def summary_statistics(
    data: pd.DataFrame, variables: list[str], gender: str = "female"
) -> pd.DataFrame:
    """Replicate estpost summarize plus unequal-variance t tests."""
    records: list[dict[str, float | str | int]] = []
    groups = [
        ("total", data),
        ("female", data[data[gender] == 1]),
        ("male", data[data[gender] == 0]),
    ]
    for variable in variables:
        row: dict[str, float | str | int] = {"variable": variable}
        for label, frame in groups:
            values = pd.to_numeric(
                frame[variable], errors="coerce"
            ).dropna()
            row[f"{label}_n"] = int(values.size)
            row[f"{label}_mean"] = float(values.mean())
            row[f"{label}_sd"] = float(values.std(ddof=1))
        female = pd.to_numeric(
            data.loc[data[gender] == 1, variable], errors="coerce"
        ).dropna()
        male = pd.to_numeric(
            data.loc[data[gender] == 0, variable], errors="coerce"
        ).dropna()
        row["welch_p"] = float(
            stats.ttest_ind(female, male, equal_var=False).pvalue
        )
        records.append(row)
    return pd.DataFrame.from_records(records)


def model_to_long(result: ModelResult) -> pd.DataFrame:
    rows = []
    for term in result.coefficients.index:
        rows.append(
            {
                "model": result.name,
                "dependent": result.dependent,
                "term": term,
                "coefficient": float(result.coefficients[term]),
                "standard_error": float(result.standard_errors[term]),
                "p_value": float(result.p_values[term]),
                "nobs": result.nobs,
                "adjusted_r2": result.adjusted_r2,
                "within_adjusted_r2": result.within_adjusted_r2,
                "clusters": result.clusters,
                "fixed_effects": ",".join(result.fixed_effects),
                "backend": result.backend,
            }
        )
    return pd.DataFrame(rows)
