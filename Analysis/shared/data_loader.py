"""Load processed datasets from independently supplied project data."""
import pandas as pd
from shared.r2 import ensure_data_file


def load_b4_exp():
    """Load Big 4 auditor employee-year panel (exploration/figures)."""
    return pd.read_feather(ensure_data_file("processed/revB4AudExp.feather"))


def load_b4_stata():
    """Load Big 4 auditor employee-year panel (Stata regressions)."""
    return pd.read_feather(ensure_data_file("processed/revB4AudStata.feather"))


def load_other_exp(columns=None):
    """Load other financial services employee-year panel (exploration/figures)."""
    return pd.read_feather(
        ensure_data_file("processed/revOtherFsExp.feather"),
        columns=columns,
    )


def load_other_stata():
    """Load other financial services employee-year panel (Stata regressions)."""
    return pd.read_feather(ensure_data_file("processed/revOtherFsStata.feather"))
