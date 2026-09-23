"""
DataGuard AI — Reusable Data Quality Rule Templates

Implements the 5 recurring rule categories from the enterprise spec:
  1. Completeness       — not_null, null_percentage_below
  2. Range / Outlier    — between (inclusive bounds)
  3. Uniqueness         — be_unique (single col), compound_unique (multi col)
  4. Format / Type      — be_of_type, match_strftime_format
  5. Set membership     — in_set, not_in_set (sentinel detection)

Each template is a pure function:
    (df, column(s), params) -> RuleOutcome

so it can be reused across any dataset without knowing domain specifics.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Outcome dataclass — uniform shape every template must return
# ---------------------------------------------------------------------------
@dataclass
class RuleOutcome:
    rule_type: str                    # canonical GE-style name
    category: str                     # one of the 5 spec categories
    column: Optional[Union[str, List[str]]]
    success: bool
    observed: str                     # human-readable observed metric
    expected: str                     # human-readable expected threshold
    failure_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    is_warning: bool = False          # True for soft failures (warn, not fail)


# ---------------------------------------------------------------------------
# 1. Completeness
# ---------------------------------------------------------------------------
def not_be_null(df: pd.DataFrame, column: str) -> RuleOutcome:
    """Fail if any value is null."""
    if column not in df.columns:
        return _missing_column_outcome("expect_column_values_to_not_be_null",
                                       "Completeness", column)

    null_count = int(df[column].isna().sum())
    total = len(df)
    null_pct = round(null_count / total * 100, 2) if total else 0.0

    if null_count == 0:
        return RuleOutcome(
            rule_type="expect_column_values_to_not_be_null",
            category="Completeness",
            column=column,
            success=True,
            observed="0 nulls (0.00%)",
            expected="0 nulls",
        )

    return RuleOutcome(
        rule_type="expect_column_values_to_not_be_null",
        category="Completeness",
        column=column,
        success=False,
        observed=f"{null_count} nulls ({null_pct}%)",
        expected="0 nulls",
        failure_message=f"Column '{column}' has {null_count} missing values ({null_pct}%).",
        details={"null_count": null_count, "null_percentage": null_pct},
    )


def null_percentage_below(df: pd.DataFrame, column: str, threshold_pct: float = 5.0) -> RuleOutcome:
    """Warn if nulls exceed threshold but dataset is still usable."""
    if column not in df.columns:
        return _missing_column_outcome("expect_column_null_percentage_to_be_below_threshold",
                                       "Completeness", column)

    null_count = int(df[column].isna().sum())
    total = len(df)
    null_pct = round(null_count / total * 100, 2) if total else 0.0
    success = null_pct <= threshold_pct

    return RuleOutcome(
        rule_type="expect_column_null_percentage_to_be_below_threshold",
        category="Completeness",
        column=column,
        success=success,
        observed=f"{null_count} nulls ({null_pct}%)",
        expected=f"<= {threshold_pct}% nulls",
        failure_message=None if success else
            f"Column '{column}' has {null_pct}% missing values (threshold {threshold_pct}%).",
        details={"null_count": null_count, "null_percentage": null_pct,
                 "threshold_pct": threshold_pct},
    )


# ---------------------------------------------------------------------------
# 2. Range / Outlier
# ---------------------------------------------------------------------------
def be_between(df: pd.DataFrame, column: str,
               min_value: Optional[float] = None,
               max_value: Optional[float] = None,
               strict: bool = False) -> RuleOutcome:
    """Fail if any numeric value falls outside [min, max]."""
    if column not in df.columns:
        return _missing_column_outcome("expect_column_values_to_be_between",
                                       "Range / Distribution", column)

    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if len(series) == 0:
        return RuleOutcome(
            rule_type="expect_column_values_to_be_between",
            category="Range / Distribution",
            column=column,
            success=True,
            observed="no numeric values",
            expected=f"[{min_value}, {max_value}]",
            details={"note": "column has no numeric data to evaluate"},
        )

    below = int((series < min_value).sum()) if min_value is not None else 0
    above = int((series > max_value).sum()) if max_value is not None else 0
    out_of_range = below + above
    pct = round(out_of_range / len(series) * 100, 2)

    success = out_of_range == 0
    return RuleOutcome(
        rule_type="expect_column_values_to_be_between",
        category="Range / Distribution",
        column=column,
        success=success,
        observed=f"{out_of_range} values outside range ({pct}%), "
                 f"actual min={round(float(series.min()), 2)}, "
                 f"max={round(float(series.max()), 2)}",
        expected=f"[{min_value}, {max_value}]",
        failure_message=None if success else
            f"Column '{column}' has {out_of_range} value(s) outside [{min_value}, {max_value}].",
        details={"below_min": below, "above_max": above, "out_of_range_pct": pct,
                 "observed_min": round(float(series.min()), 4),
                 "observed_max": round(float(series.max()), 4)},
    )


# ---------------------------------------------------------------------------
# 3. Uniqueness
# ---------------------------------------------------------------------------
def be_unique(df: pd.DataFrame, column: str) -> RuleOutcome:
    """Fail if duplicate values exist in a single column."""
    if column not in df.columns:
        return _missing_column_outcome("expect_column_values_to_be_unique",
                                       "Uniqueness", column)

    dup_count = int(df[column].duplicated().sum())
    success = dup_count == 0
    return RuleOutcome(
        rule_type="expect_column_values_to_be_unique",
        category="Uniqueness",
        column=column,
        success=success,
        observed=f"{dup_count} duplicates",
        expected="0 duplicates",
        failure_message=None if success else
            f"Column '{column}' has {dup_count} duplicate value(s).",
        details={"duplicate_count": dup_count},
    )


def compound_columns_unique(df: pd.DataFrame, columns: List[str]) -> RuleOutcome:
    """Fail if the combination of columns has duplicate rows."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        return RuleOutcome(
            rule_type="expect_compound_columns_to_be_unique",
            category="Uniqueness",
            column=columns,
            success=False,
            observed=f"missing columns: {missing}",
            expected="all columns present",
            failure_message=f"Cannot evaluate compound uniqueness: columns {missing} not found.",
        )

    dup_count = int(df.duplicated(subset=columns).sum())
    success = dup_count == 0
    return RuleOutcome(
        rule_type="expect_compound_columns_to_be_unique",
        category="Uniqueness",
        column=columns,
        success=success,
        observed=f"{dup_count} duplicate combinations",
        expected="0 duplicate combinations",
        failure_message=None if success else
            f"Compound key {columns} has {dup_count} duplicate row(s).",
        details={"duplicate_count": dup_count, "columns": columns},
    )


# ---------------------------------------------------------------------------
# 4. Format / Type
# ---------------------------------------------------------------------------
_TYPE_CHECKS = {
    "int":     lambda s: pd.api.types.is_integer_dtype(s),
    "float":   lambda s: pd.api.types.is_float_dtype(s),
    "numeric": lambda s: pd.api.types.is_numeric_dtype(s),
    "string":  lambda s: pd.api.types.is_string_dtype(s) or s.dtype == object,
    "bool":    lambda s: pd.api.types.is_bool_dtype(s),
    "datetime":lambda s: pd.api.types.is_datetime64_any_dtype(s),
}


def be_of_type(df: pd.DataFrame, column: str, expected_type: str) -> RuleOutcome:
    """Fail if column dtype doesn't match expected semantic type."""
    if column not in df.columns:
        return _missing_column_outcome("expect_column_values_to_be_of_type",
                                       "Schema / Type", column)

    expected_type = expected_type.lower()
    checker = _TYPE_CHECKS.get(expected_type)
    if checker is None:
        return RuleOutcome(
            rule_type="expect_column_values_to_be_of_type",
            category="Schema / Type",
            column=column,
            success=False,
            observed=f"unknown expected type '{expected_type}'",
            expected=expected_type,
            failure_message=f"Unsupported type '{expected_type}'.",
        )

    # For string/numeric actual coercion checks, also validate values castable
    series = df[column].dropna()
    if expected_type == "numeric":
        coerced = pd.to_numeric(series, errors="coerce")
        invalid = int(coerced.isna().sum())
        success = invalid == 0
        return RuleOutcome(
            rule_type="expect_column_values_to_be_of_type",
            category="Schema / Type",
            column=column,
            success=success,
            observed=f"{invalid} non-numeric value(s)",
            expected="numeric",
            failure_message=None if success else
                f"Column '{column}' contains {invalid} non-numeric value(s).",
            details={"invalid_count": invalid},
        )

    ok = checker(df[column])
    return RuleOutcome(
        rule_type="expect_column_values_to_be_of_type",
        category="Schema / Type",
        column=column,
        success=bool(ok),
        observed=str(df[column].dtype),
        expected=expected_type,
        failure_message=None if ok else
            f"Column '{column}' has dtype {df[column].dtype}, expected {expected_type}.",
        details={"actual_dtype": str(df[column].dtype)},
    )


_STRFTIME_PROBE = {
    "%Y-%m-%d":   re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "%Y/%m/%d":   re.compile(r"^\d{4}/\d{2}/\d{2}$"),
    "%d-%m-%Y":   re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    "%d/%m/%Y":   re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    "%m/%d/%Y":   re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"),
    "%Y-%m-%dT%H:%M:%S": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
}


def match_strftime_format(df: pd.DataFrame, column: str,
                          fmt: str = "%Y-%m-%d") -> RuleOutcome:
    """Fail if string values don't match a single strftime format."""
    if column not in df.columns:
        return _missing_column_outcome("expect_column_values_to_match_strftime_format",
                                       "Schema / Type", column)

    regex = _STRFTIME_PROBE.get(fmt)
    if regex is None:
        return RuleOutcome(
            rule_type="expect_column_values_to_match_strftime_format",
            category="Schema / Type",
            column=column,
            success=False,
            observed=f"unsupported format '{fmt}'",
            expected=fmt,
            failure_message=f"Format '{fmt}' not supported.",
        )

    series = df[column].dropna().astype(str)
    matches = series.str.match(regex)
    ok_count = int(matches.sum())
    bad = len(series) - ok_count
    pct = round(bad / len(series) * 100, 2) if len(series) else 0.0
    success = bad == 0

    return RuleOutcome(
        rule_type="expect_column_values_to_match_strftime_format",
        category="Schema / Type",
        column=column,
        success=success,
        observed=f"{bad} non-conforming values ({pct}%)",
        expected=f"100% matching {fmt}",
        failure_message=None if success else
            f"Column '{column}' has {bad} value(s) not matching {fmt}.",
        details={"non_conforming_count": bad, "format": fmt,
                 "non_conforming_pct": pct},
    )


# ---------------------------------------------------------------------------
# 5. Set membership / Sentinel detection
# ---------------------------------------------------------------------------
def be_in_set(df: pd.DataFrame, column: str,
              allowed: Sequence[Any],
              mostly: float = 1.0) -> RuleOutcome:
    """Fail if any value is outside the allowed set (e.g. valid category list)."""
    if column not in df.columns:
        return _missing_column_outcome("expect_column_values_to_be_in_set",
                                       "Categorical Consistency", column)

    allowed_set = {str(v) for v in allowed}
    series = df[column].dropna().astype(str)
    in_set = series.isin(allowed_set)
    in_ratio = float(in_set.mean()) if len(series) else 1.0
    outside_count = int((~in_set).sum())
    success = in_ratio >= mostly

    return RuleOutcome(
        rule_type="expect_column_values_to_be_in_set",
        category="Categorical Consistency",
        column=column,
        success=success,
        observed=f"{outside_count} values outside allowed set ({round((1 - in_ratio)*100, 2)}%)",
        expected=f">= {mostly*100:.0f}% in allowed set",
        failure_message=None if success else
            f"Column '{column}' has {outside_count} value(s) not in allowed set.",
        details={"outside_count": outside_count, "in_set_ratio": round(in_ratio, 4)},
    )


def not_be_in_set(df: pd.DataFrame, column: str,
                  forbidden: Sequence[Any]) -> RuleOutcome:
    """
    Fail if any forbidden sentinel values appear.
    Catches things like -999, 9999, 'N/A', '', 'NULL' that pass all other checks.
    """
    if column not in df.columns:
        return _missing_column_outcome("expect_column_values_to_not_be_in_set",
                                       "Categorical Consistency", column)

    # Normalize both sides to strings for comparison (handles int/float mix)
    forbidden_str = {str(v) for v in forbidden}

    # For numeric columns, also compare numerically
    series = df[column]
    series_str = series.dropna().astype(str)

    # Try numeric comparison too
    numeric_series = pd.to_numeric(series, errors="coerce")
    numeric_forbidden = set()
    for v in forbidden:
        try:
            numeric_forbidden.add(float(v))
        except (TypeError, ValueError):
            pass

    str_hit = series_str.isin(forbidden_str)
    num_hit = numeric_series.isin(numeric_forbidden) if numeric_forbidden else pd.Series(False, index=series.index)

    hits = int(str_hit.sum() + num_hit.sum())
    # dedupe double-count when both match the same row
    if len(str_hit) and len(num_hit):
        both = (str_hit & num_hit).sum()
        hits -= int(both)

    success = hits == 0
    return RuleOutcome(
        rule_type="expect_column_values_to_not_be_in_set",
        category="Categorical Consistency",
        column=column,
        success=success,
        observed=f"{hits} sentinel value(s) found",
        expected=f"no values in {list(forbidden)}",
        failure_message=None if success else
            f"Column '{column}' contains {hits} sentinel value(s) from {list(forbidden)}.",
        details={"sentinel_count": hits, "sentinels": list(forbidden)},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _missing_column_outcome(rule_type: str, category: str, column: str) -> RuleOutcome:
    return RuleOutcome(
        rule_type=rule_type,
        category=category,
        column=column,
        success=False,
        observed=f"column '{column}' not present",
        expected="column exists",
        failure_message=f"Column '{column}' not found in dataset.",
    )


def table_row_count_between(df: pd.DataFrame,
                            min_value: int = 1,
                            max_value: Optional[int] = None) -> RuleOutcome:
    """Volume check — table-level row count within expected range."""
    n = len(df)
    below = n < min_value
    above = max_value is not None and n > max_value
    success = not below and not above

    return RuleOutcome(
        rule_type="expect_table_row_count_to_be_between",
        category="Schema / Type",
        column=None,
        success=success,
        observed=f"{n} rows",
        expected=f"[{min_value}, {max_value}]" if max_value is not None
                 else f">= {min_value}",
        failure_message=None if success else
            f"Table has {n} rows, outside [{min_value}, {max_value}].",
        details={"row_count": n},
    )