"""Stata-compatible repeated-record Cox estimation in pure Python.

The important compatibility detail is the risk-set interval.  Stata's
multiple-record ``stset`` representation uses ``(entry, exit]``.  Statsmodels
0.14.6 includes records at ``entry == failure_time`` when entry times are
passed directly, which is consequential for this integer-time panel.  This
module evaluates the strict-open-left Breslow likelihood directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import minimize


@dataclass
class StataCoxResult:
    names: list[str]
    coefficients: np.ndarray
    covariance: np.ndarray
    standard_errors: np.ndarray
    nobs: int
    clusters: int
    diagnostics: dict


class _BreslowObjective:
    """Fast strict-open-left Breslow objective on an integer time grid."""

    def __init__(
        self,
        exog: np.ndarray,
        duration: np.ndarray,
        status: np.ndarray,
        entry: np.ndarray,
    ) -> None:
        self.exog = exog
        self.duration = duration
        self.status = status
        self.entry = entry
        self.max_time = int(duration.max())
        self.width = self.max_time + 1
        self.event_count = np.bincount(
            duration, weights=status, minlength=self.width
        )
        self.event_times = np.flatnonzero(self.event_count)
        self.event_x = exog.T @ status
        self.cell = entry * self.width + duration
        self.cell_count = self.width**2
        self.calls = 0

    def value_gradient(self, beta: np.ndarray) -> tuple[float, np.ndarray]:
        self.calls += 1
        eta = self.exog @ beta
        center = float(eta.max())
        weight = np.exp(eta - center)
        weight_by_cell = np.bincount(
            self.cell, weights=weight, minlength=self.cell_count
        ).reshape(self.width, self.width)

        denominator = np.zeros(self.width)
        for time_value in self.event_times:
            denominator[time_value] = weight_by_cell[
                :time_value, time_value:
            ].sum()
        event_count = self.event_count[self.event_times]
        loglike = float(
            self.status @ eta
            - np.sum(
                event_count
                * (center + np.log(denominator[self.event_times]))
            )
        )

        hazard_increment = np.zeros(self.width)
        hazard_increment[self.event_times] = (
            event_count / denominator[self.event_times]
        )
        cumulative_hazard = np.cumsum(hazard_increment)
        alpha = (
            cumulative_hazard[self.duration]
            - cumulative_hazard[self.entry]
        )
        risk_multiplier = weight * alpha
        gradient = self.event_x - self.exog.T @ risk_multiplier
        return -loglike, -gradient


def _absorbed_regressors(
    frame: pd.DataFrame,
    regressors: Iterable[str],
    categorical_effects: Iterable[str],
) -> list[str]:
    return [
        regressor
        for regressor in regressors
        if any(
            frame.groupby(effect, observed=True)[regressor]
            .nunique()
            .max()
            <= 1
            for effect in categorical_effects
        )
    ]


def _build_design(
    frame: pd.DataFrame,
    regressors: list[str],
    categorical_effects: list[str],
    status: str,
) -> tuple[pd.DataFrame, list[str]]:
    absorbed = _absorbed_regressors(
        frame, regressors, categorical_effects
    )
    continuous = (
        frame[
            [value for value in regressors if value not in absorbed]
        ]
        .astype(float)
        .reset_index(drop=True)
    )
    encoded_effects = []
    for effect in categorical_effects:
        event_counts = frame.groupby(effect, observed=True)[status].sum()
        if not (event_counts > 0).any():
            raise ValueError(f"{effect!r} has no event-bearing level")
        base = event_counts.idxmax()
        levels = [
            base,
            *[
                value
                for value in sorted(event_counts.index)
                if value != base
            ],
        ]
        encoded_effects.append(
            pd.get_dummies(
                pd.Categorical(frame[effect], categories=levels),
                prefix=effect,
                drop_first=True,
                dtype=float,
            ).reset_index(drop=True)
        )
    design = pd.concat([continuous, *encoded_effects], axis=1)
    return design, absorbed


def _robust_covariance(
    objective: _BreslowObjective,
    beta: np.ndarray,
    userid: np.ndarray,
    all_userids: np.ndarray,
) -> tuple[np.ndarray, dict]:
    """Lin-Wei efficient-score sandwich, clustered at the subject level."""
    exog = objective.exog
    duration = objective.duration
    status = objective.status
    entry = objective.entry
    eta = exog @ beta
    center = float(eta.max())
    weight = np.exp(eta - center)
    width = objective.width
    cell = objective.cell

    weight_by_cell = np.bincount(
        cell, weights=weight, minlength=objective.cell_count
    ).reshape(width, width)
    weighted_x_by_cell = np.empty((width, width, exog.shape[1]))
    for column_index in range(exog.shape[1]):
        weighted_x_by_cell[:, :, column_index] = np.bincount(
            cell,
            weights=weight * exog[:, column_index],
            minlength=objective.cell_count,
        ).reshape(width, width)

    denominator = np.zeros(width)
    mean = np.zeros((width, exog.shape[1]))
    for time_value in objective.event_times:
        denominator[time_value] = weight_by_cell[
            :time_value, time_value:
        ].sum()
        mean[time_value] = (
            weighted_x_by_cell[:time_value, time_value:, :].sum(axis=(0, 1))
            / denominator[time_value]
        )

    hazard_increment = np.zeros(width)
    hazard_increment[objective.event_times] = (
        objective.event_count[objective.event_times]
        / denominator[objective.event_times]
    )
    cumulative_hazard = np.cumsum(hazard_increment)
    cumulative_bar = np.cumsum(hazard_increment[:, None] * mean, axis=0)
    alpha = cumulative_hazard[duration] - cumulative_hazard[entry]
    bar_alpha = cumulative_bar[duration] - cumulative_bar[entry]

    information = np.zeros((exog.shape[1], exog.shape[1]))
    information_weight = weight * alpha
    block_size = 50_000
    for block_start in range(0, len(exog), block_size):
        block_end = min(block_start + block_size, len(exog))
        x_block = exog[block_start:block_end]
        information += x_block.T @ (
            x_block * information_weight[block_start:block_end, None]
        )
    for time_value in objective.event_times:
        information -= objective.event_count[time_value] * np.outer(
            mean[time_value], mean[time_value]
        )

    user_index = pd.Index(all_userids)
    user_codes = user_index.get_indexer(userid)
    if np.any(user_codes < 0):
        raise RuntimeError("Risk-row subject missing from the full sample")
    cluster_scores = np.empty((len(user_index), exog.shape[1]))
    mean_at_exit = mean[duration]
    for column_index in range(exog.shape[1]):
        row_score = (
            status
            * (
                exog[:, column_index]
                - mean_at_exit[:, column_index]
            )
            - weight * alpha * exog[:, column_index]
            + weight * bar_alpha[:, column_index]
        )
        cluster_scores[:, column_index] = np.bincount(
            user_codes,
            weights=row_score,
            minlength=len(user_index),
        )

    meat = cluster_scores.T @ cluster_scores
    bread = np.linalg.inv(information)
    cluster_adjustment = len(user_index) / (len(user_index) - 1)
    covariance = cluster_adjustment * bread @ meat @ bread
    return covariance, {
        "information_condition_number": float(np.linalg.cond(information)),
        "cluster_adjustment": float(cluster_adjustment),
        "cluster_score_sum_max_abs": float(
            np.abs(cluster_scores.sum(axis=0)).max()
        ),
    }


def fit_stata_style_cox(
    data: pd.DataFrame,
    *,
    duration: str,
    status: str,
    regressors: list[str],
    categorical_effects: list[str],
    subject: str,
    maxiter: int = 700,
) -> StataCoxResult:
    """Fit the replication package's Stata Cox specification.

    Zero-failure categorical levels have negative-infinite Cox coefficients.
    Their rows are removed from finite risk contributions only after entry
    times are constructed on the complete panel.  The returned observation and
    cluster counts remain those of Stata's full estimation sample.
    """
    columns = [
        duration,
        status,
        subject,
        *regressors,
        *categorical_effects,
    ]
    frame = data.loc[:, columns].dropna().copy()
    frame = frame.sort_values([subject, duration], kind="stable").reset_index(
        drop=True
    )
    entry = (
        frame.groupby(subject, sort=False)[duration]
        .shift()
        .fillna(0)
        .astype(float)
    )
    valid = frame[duration].astype(float) > entry
    frame = frame.loc[valid].reset_index(drop=True)
    entry = entry.loc[valid].reset_index(drop=True)
    full_nobs = int(len(frame))
    all_userids = frame[subject].drop_duplicates().to_numpy()

    separated_levels: dict[str, list] = {}
    finite_risk = np.ones(len(frame), dtype=bool)
    for effect in categorical_effects:
        event_counts = frame.groupby(effect, observed=True)[status].sum()
        levels = event_counts[event_counts == 0].index.tolist()
        separated_levels[effect] = levels
        if levels:
            finite_risk &= ~frame[effect].isin(levels).to_numpy()

    risk_frame = frame.loc[finite_risk].reset_index(drop=True)
    risk_entry = entry.loc[finite_risk].to_numpy(int)
    design, absorbed = _build_design(
        risk_frame, regressors, categorical_effects, status
    )
    exog = design.to_numpy(float)
    duration_values = risk_frame[duration].to_numpy(int)
    status_values = risk_frame[status].to_numpy(int)
    objective = _BreslowObjective(
        exog, duration_values, status_values, risk_entry
    )

    start = np.zeros(exog.shape[1])
    optimizations = []
    for _ in range(2):
        result = minimize(
            objective.value_gradient,
            start,
            method="L-BFGS-B",
            jac=True,
            options={
                "maxiter": maxiter,
                "ftol": 1e-13,
                "gtol": 1e-7,
                "maxls": 50,
            },
        )
        start = result.x
        value, gradient = objective.value_gradient(start)
        optimizations.append(
            {
                "success": bool(result.success),
                "message": str(result.message),
                "iterations": int(result.nit),
                "loglike": -float(value),
                "score_max_abs": float(np.abs(gradient).max()),
            }
        )
        if np.abs(gradient).max() < 0.25:
            break

    covariance, covariance_diagnostics = _robust_covariance(
        objective,
        start,
        risk_frame[subject].to_numpy(),
        all_userids,
    )
    standard_errors = np.sqrt(np.diag(covariance))
    final_value, final_gradient = objective.value_gradient(start)
    diagnostics = {
        "risk_interval": "(entry, exit]",
        "ties": "breslow",
        "full_rows": full_nobs,
        "finite_risk_rows": int(len(risk_frame)),
        "zero_risk_rows_from_separation": int((~finite_risk).sum()),
        "events": int(status_values.sum()),
        "clusters": int(len(all_userids)),
        "absorbed_regressors": absorbed,
        "separated_levels": separated_levels,
        "loglike": -float(final_value),
        "score_max_abs": float(np.abs(final_gradient).max()),
        "objective_calls": int(objective.calls),
        "optimization_passes": optimizations,
        **covariance_diagnostics,
    }
    return StataCoxResult(
        names=[str(value) for value in design.columns],
        coefficients=start,
        covariance=covariance,
        standard_errors=standard_errors,
        nobs=full_nobs,
        clusters=int(len(all_userids)),
        diagnostics=diagnostics,
    )
