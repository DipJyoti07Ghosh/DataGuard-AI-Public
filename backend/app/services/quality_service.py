"""
DataGuard AI — Automated Data Quality Engine (Great Expectations Integration)

Generates dataset-specific quality expectations based on Phase 4 profiling baselines,
validates datasets, computes transparent quality scores (0-100), categorizes issues,
and persists structured validation results linked to DatasetVersion.

Rule taxonomy (5 reusable categories from the enterprise spec):
  1. Completeness            — not_null, null_percentage_below
  2. Range / Outlier         — be_between
  3. Uniqueness              — be_unique, compound_columns_unique
  4. Format / Type           — be_of_type, match_strftime_format
  5. Set membership/Sentinel — be_in_set, not_be_in_set

Two evaluation layers run in order:
  A) Generic heuristics (data-driven; applied to every column based on profiling)
  B) Domain rule templates (spec-driven; applied when the dataset matches a known schema)
Both layers append to the same results list, so scoring and category breakdown stay unified.
"""

from pathlib import Path
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
from uuid import UUID
from datetime import datetime, timezone

import pandas as pd
import numpy as np
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.dataset import Dataset, DatasetVersion
from app.models.quality import QualityValidationResult, QualityExpectationResult
from app.schemas.quality import (
    ExpectationRuleResult,
    CategorySummary,
    QualitySummary,
    QualityResponse,
)
from app.services.ingestion import parse_csv, parse_excel
from app.services.profiling_service import (
    get_profile_for_version,
    generate_profile_for_version,
)

logger = logging.getLogger("dataguard.quality")


# ===========================================================================
# SECTION 0 — Shared helpers
# ===========================================================================
def calculate_grade(score: float) -> str:
    """Assign human-readable grade based on numerical quality score."""
    if score >= 90.0:
        return "Excellent"
    if score >= 75.0:
        return "Good"
    if score >= 50.0:
        return "Fair"
    return "Poor"


def _canonical_category(cat: str) -> str:
    """Map template categories to the schema's existing category names."""
    mapping = {
        "Completeness": "Missing Data",
        "Range / Distribution": "Range / Distribution",
        "Uniqueness": "Uniqueness",
        "Schema / Type": "Schema / Type",
        "Categorical Consistency": "Categorical Consistency",
    }
    return mapping.get(cat, cat)


# ===========================================================================
# SECTION 1 — Rule templates (5 reusable categories)
# ===========================================================================
@dataclass
class RuleOutcome:
    """Uniform shape every rule template returns."""
    rule_type: str
    category: str
    column: Optional[Union[str, List[str]]]
    success: bool
    observed: str
    expected: str
    failure_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    is_warning: bool = False


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


# ---- 1. Completeness -------------------------------------------------------
def not_be_null(df: pd.DataFrame, column: str) -> RuleOutcome:
    """Fail if any value is null."""
    if column not in df.columns:
        return _missing_column_outcome(
            "expect_column_values_to_not_be_null", "Completeness", column
        )

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


def null_percentage_below(
    df: pd.DataFrame, column: str, threshold_pct: float = 5.0
) -> RuleOutcome:
    """Pass if nulls are within an acceptable tolerance."""
    if column not in df.columns:
        return _missing_column_outcome(
            "expect_column_null_percentage_to_be_below_threshold", "Completeness", column
        )

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
        failure_message=None
        if success
        else f"Column '{column}' has {null_pct}% missing values (threshold {threshold_pct}%).",
        details={
            "null_count": null_count,
            "null_percentage": null_pct,
            "threshold_pct": threshold_pct,
        },
    )


# ---- 2. Range / Outlier ----------------------------------------------------
def be_between(
    df: pd.DataFrame,
    column: str,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> RuleOutcome:
    """Fail if any numeric value falls outside [min, max]."""
    if column not in df.columns:
        return _missing_column_outcome(
            "expect_column_values_to_be_between", "Range / Distribution", column
        )

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
        observed=(
            f"{out_of_range} values outside range ({pct}%), "
            f"actual min={round(float(series.min()), 2)}, "
            f"max={round(float(series.max()), 2)}"
        ),
        expected=f"[{min_value}, {max_value}]",
        failure_message=None
        if success
        else f"Column '{column}' has {out_of_range} value(s) outside [{min_value}, {max_value}].",
        details={
            "below_min": below,
            "above_max": above,
            "out_of_range_pct": pct,
            "observed_min": round(float(series.min()), 4),
            "observed_max": round(float(series.max()), 4),
        },
    )


# ---- 3. Uniqueness ---------------------------------------------------------
def be_unique(df: pd.DataFrame, column: str) -> RuleOutcome:
    """Fail if duplicate values exist in a single column."""
    if column not in df.columns:
        return _missing_column_outcome(
            "expect_column_values_to_be_unique", "Uniqueness", column
        )

    dup_count = int(df[column].duplicated().sum())
    success = dup_count == 0
    return RuleOutcome(
        rule_type="expect_column_values_to_be_unique",
        category="Uniqueness",
        column=column,
        success=success,
        observed=f"{dup_count} duplicates",
        expected="0 duplicates",
        failure_message=None
        if success
        else f"Column '{column}' has {dup_count} duplicate value(s).",
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
        failure_message=None
        if success
        else f"Compound key {columns} has {dup_count} duplicate row(s).",
        details={"duplicate_count": dup_count, "columns": columns},
    )


# ---- 4. Format / Type ------------------------------------------------------
_TYPE_CHECKS = {
    "int": lambda s: pd.api.types.is_integer_dtype(s),
    "float": lambda s: pd.api.types.is_float_dtype(s),
    "numeric": lambda s: pd.api.types.is_numeric_dtype(s),
    "string": lambda s: pd.api.types.is_string_dtype(s) or s.dtype == object,
    "bool": lambda s: pd.api.types.is_bool_dtype(s),
    "datetime": lambda s: pd.api.types.is_datetime64_any_dtype(s),
}


def be_of_type(df: pd.DataFrame, column: str, expected_type: str) -> RuleOutcome:
    """Fail if column dtype doesn't match expected semantic type."""
    if column not in df.columns:
        return _missing_column_outcome(
            "expect_column_values_to_be_of_type", "Schema / Type", column
        )

    expected_type = expected_type.lower()

    # For numeric we actually validate value castability (more meaningful)
    if expected_type == "numeric":
        series = df[column].dropna()
        coerced = pd.to_numeric(series, errors="coerce")
        invalid = int(coerced.isna().sum())
        success = invalid == 0
        return RuleOutcome(
            rule_type="expect_column_values_to_be_of_type",
            category="Schema / Type",
            column=column,
            success=success,
            observed=f"{invalid} non-numeric value(s)"
            if not success
            else "numeric (valid)",
            expected="numeric",
            failure_message=None
            if success
            else f"Column '{column}' contains {invalid} non-numeric value(s).",
            details={"invalid_count": invalid},
        )

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

    ok = checker(df[column])
    return RuleOutcome(
        rule_type="expect_column_values_to_be_of_type",
        category="Schema / Type",
        column=column,
        success=bool(ok),
        observed=str(df[column].dtype),
        expected=expected_type,
        failure_message=None
        if ok
        else f"Column '{column}' has dtype {df[column].dtype}, expected {expected_type}.",
        details={"actual_dtype": str(df[column].dtype)},
    )


_STRFTIME_PROBE = {
    "%Y-%m-%d": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "%Y/%m/%d": re.compile(r"^\d{4}/\d{2}/\d{2}$"),
    "%d-%m-%Y": re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    "%d/%m/%Y": re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    "%m/%d/%Y": re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"),
    "%Y-%m-%dT%H:%M:%S": re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
}


def match_strftime_format(
    df: pd.DataFrame, column: str, fmt: str = "%Y-%m-%d"
) -> RuleOutcome:
    """Fail if string values don't match a single strftime format."""
    if column not in df.columns:
        return _missing_column_outcome(
            "expect_column_values_to_match_strftime_format", "Schema / Type", column
        )

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
    if len(series) == 0:
        return RuleOutcome(
            rule_type="expect_column_values_to_match_strftime_format",
            category="Schema / Type",
            column=column,
            success=True,
            observed="no non-null values",
            expected=f"100% matching {fmt}",
        )

    matches = series.str.match(regex)
    bad = int((~matches).sum())
    pct = round(bad / len(series) * 100, 2)
    success = bad == 0

    return RuleOutcome(
        rule_type="expect_column_values_to_match_strftime_format",
        category="Schema / Type",
        column=column,
        success=success,
        observed=f"{bad} non-conforming values ({pct}%)",
        expected=f"100% matching {fmt}",
        failure_message=None
        if success
        else f"Column '{column}' has {bad} value(s) not matching {fmt}.",
        details={
            "non_conforming_count": bad,
            "format": fmt,
            "non_conforming_pct": pct,
        },
    )


# ---- 5. Set membership / Sentinel detection --------------------------------
def be_in_set(
    df: pd.DataFrame, column: str, allowed: Sequence[Any], mostly: float = 1.0
) -> RuleOutcome:
    """Fail if too many values are outside the allowed set."""
    if column not in df.columns:
        return _missing_column_outcome(
            "expect_column_values_to_be_in_set", "Categorical Consistency", column
        )

    allowed_set = {str(v) for v in allowed}
    series = df[column].dropna().astype(str)
    if len(series) == 0:
        return RuleOutcome(
            rule_type="expect_column_values_to_be_in_set",
            category="Categorical Consistency",
            column=column,
            success=True,
            observed="no non-null values",
            expected=f">= {mostly*100:.0f}% in allowed set",
        )

    in_set = series.isin(allowed_set)
    in_ratio = float(in_set.mean())
    outside_count = int((~in_set).sum())
    success = in_ratio >= mostly

    return RuleOutcome(
        rule_type="expect_column_values_to_be_in_set",
        category="Categorical Consistency",
        column=column,
        success=success,
        observed=(
            f"{outside_count} values outside allowed set "
            f"({round((1 - in_ratio) * 100, 2)}%)"
        ),
        expected=f">= {mostly*100:.0f}% in allowed set",
        failure_message=None
        if success
        else f"Column '{column}' has {outside_count} value(s) not in allowed set.",
        details={
            "outside_count": outside_count,
            "in_set_ratio": round(in_ratio, 4),
        },
    )


def not_be_in_set(
    df: pd.DataFrame, column: str, forbidden: Sequence[Any]
) -> RuleOutcome:
    """
    Fail if any forbidden sentinel values appear.
    Catches things like -999, 9999, 'N/A' that pass every type and null check.
    """
    if column not in df.columns:
        return _missing_column_outcome(
            "expect_column_values_to_not_be_in_set",
            "Categorical Consistency",
            column,
        )

    forbidden_str = {str(v) for v in forbidden}
    series = df[column]

    # String comparison
    series_str = series.dropna().astype(str)
    str_hit = series_str.isin(forbidden_str)

    # Numeric comparison (catches -999 as int vs "-999" string)
    numeric_series = pd.to_numeric(series, errors="coerce")
    numeric_forbidden = set()
    for v in forbidden:
        try:
            numeric_forbidden.add(float(v))
        except (TypeError, ValueError):
            pass

    if numeric_forbidden:
        num_hit = numeric_series.isin(numeric_forbidden)
    else:
        num_hit = pd.Series(False, index=series.index)

    # Union of hits — dedupe rows matched by both string and numeric path
    combined = str_hit.reindex(series.index, fill_value=False) | num_hit.reindex(
        series.index, fill_value=False
    )
    hits = int(combined.sum())

    success = hits == 0
    return RuleOutcome(
        rule_type="expect_column_values_to_not_be_in_set",
        category="Categorical Consistency",
        column=column,
        success=success,
        observed=f"{hits} sentinel value(s) found",
        expected=f"no values in {list(forbidden)}",
        failure_message=None
        if success
        else f"Column '{column}' contains {hits} sentinel value(s) from {list(forbidden)}.",
        details={"sentinel_count": hits, "sentinels": list(forbidden)},
    )


def table_row_count_between(
    df: pd.DataFrame, min_value: int = 1, max_value: Optional[int] = None
) -> RuleOutcome:
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
        expected=f"[{min_value}, {max_value}]" if max_value is not None else f">= {min_value}",
        failure_message=None
        if success
        else f"Table has {n} rows, outside [{min_value}, {max_value}].",
        details={"row_count": n},
    )


# ===========================================================================
# SECTION 2 — Predefined domain rule sets
# ===========================================================================
RuleSpec = Tuple[Callable, str, Dict[str, Any]]


RETAIL_RULES: List[RuleSpec] = [
    (not_be_null, "customer_email", {}),
    (not_be_null, "phone_number", {}),
    (be_between, "purchase_amount", {"min_value": 0, "max_value": 100000}),
    (match_strftime_format, "purchase_date", {"fmt": "%Y-%m-%d"}),
    (be_of_type, "purchase_amount", {"expected_type": "numeric"}),
    (
        be_in_set,
        "category",
        {
            "allowed": [
                "Electronics",
                "Clothing",
                "Home",
                "Grocery",
                "Toys",
                "Books",
                "Sports",
            ],
            "mostly": 0.95,
        },
    ),
]
RETAIL_COMPOUND: List[Tuple[List[str], Callable]] = [
    (["order_id", "customer_id"], compound_columns_unique),
]


BANKING_RULES: List[RuleSpec] = [
    (not_be_null, "branch_code", {}),
    (not_be_null, "transaction_amount", {}),
    (be_between, "transaction_amount", {"min_value": 0.01, "max_value": 1_000_000}),
    (be_of_type, "branch_code", {"expected_type": "string"}),
]
BANKING_TABLE_RULES: List[Callable] = [table_row_count_between]


MANUFACTURING_RULES: List[RuleSpec] = [
    (not_be_null, "pressure_reading", {}),
    (be_between, "pressure_reading", {"min_value": 0.0, "max_value": 500.0}),
    (not_be_null, "temp_reading", {}),
    (be_between, "temp_reading", {"min_value": -50.0, "max_value": 200.0}),
    (be_of_type, "vibration_reading", {"expected_type": "numeric"}),
]


INSURANCE_RULES: List[RuleSpec] = [
    (not_be_null, "claimant_email", {}),
    (be_between, "claim_amount", {"min_value": 0, "max_value": 500_000}),
    (not_be_in_set, "claim_amount", {"forbidden": [-999, 9999, -1]}),
    (not_be_null, "adjuster_notes", {}),
    (be_of_type, "claim_amount", {"expected_type": "numeric"}),
]


ALL_RULE_SETS = {
    "retail": (RETAIL_RULES, RETAIL_COMPOUND, []),
    "banking": (BANKING_RULES, [], BANKING_TABLE_RULES),
    "manufacturing": (MANUFACTURING_RULES, [], []),
    "insurance": (INSURANCE_RULES, [], []),
}


def pick_best_rule_set(columns: List[str]):
    """
    Pick the rule set whose columns overlap most with the dataset's columns.
    Returns (name, rules, compound_rules, table_rules) or None.
    """
    cols_lower = {c.lower() for c in columns}
    best = None
    best_score = 0

    for name, (rule_specs, compound_specs, table_specs) in ALL_RULE_SETS.items():
        referenced = set()
        for _, col, _ in rule_specs:
            referenced.add(col.lower())
        for cols, _ in compound_specs:
            referenced.update(c.lower() for c in cols)
        score = len(referenced & cols_lower)
        if score > best_score:
            best_score = score
            best = (name, rule_specs, compound_specs, table_specs)

    # Require a minimum overlap so we don't misapply a rule set
    if best and best_score >= 2:
        return best
    return None


# ===========================================================================
# SECTION 3 — Generic heuristic evaluator (data-driven)
# ===========================================================================
class QualityRuleEvaluator:
    """
    Evaluates automated quality expectation rules against a DataFrame
    using Phase 4 column profiles and dataset structural metadata.
    """

    def __init__(self, df: pd.DataFrame, profile_dict: dict):
        self.df = df
        self.profile = profile_dict
        self.column_profiles = profile_dict.get("column_profiles", {})
        self.results: list[dict] = []
        self.major_problems: list[str] = []

    def add_result(
        self,
        expectation_type: str,
        category: str,
        column_name: str | None,
        success: bool,
        observed_value: str,
        expected_value: str,
        failure_message: str | None = None,
        details: dict | None = None,
        is_major: bool = False,
    ):
        """Append an evaluated expectation outcome."""
        res = {
            "expectation_type": expectation_type,
            "category": category,
            "column_name": column_name,
            "success": success,
            "observed_value": observed_value,
            "expected_value": expected_value,
            "failure_message": failure_message if not success else None,
            "details": details or {},
        }
        self.results.append(res)
        if not success and failure_message and (is_major or len(self.major_problems) < 5):
            if failure_message not in self.major_problems:
                self.major_problems.append(failure_message)

    def evaluate_all(self):
        """Run all generic heuristic categories."""
        self._evaluate_schema_and_structure()
        self._evaluate_duplicates()
        self._evaluate_missing_values()
        self._evaluate_data_types()
        self._evaluate_numeric_ranges()
        self._evaluate_uniqueness()
        self._evaluate_categorical_consistency()

    # -- 1. Schema / Type -----------------------------------------------------
    def _evaluate_schema_and_structure(self):
        row_count = len(self.df)
        has_rows = row_count > 0
        self.add_result(
            expectation_type="expect_table_row_count_to_be_between",
            category="Schema / Type",
            column_name=None,
            success=has_rows,
            observed_value=f"{row_count} rows",
            expected_value=">= 1 row",
            failure_message="Dataset is empty (0 rows)." if not has_rows else None,
            is_major=not has_rows,
        )

        cols = list(self.df.columns)
        has_cols = len(cols) > 0
        self.add_result(
            expectation_type="expect_table_columns_to_match_set",
            category="Schema / Type",
            column_name=None,
            success=has_cols,
            observed_value=f"{len(cols)} columns",
            expected_value=">= 1 column",
            failure_message="Dataset contains no columns." if not has_cols else None,
            is_major=not has_cols,
        )

    # -- 2. Duplicates --------------------------------------------------------
    def _evaluate_duplicates(self):
        if self.df.empty:
            return

        dup_count = int(self.df.duplicated().sum())
        dup_pct = round((dup_count / len(self.df)) * 100.0, 2)
        success = dup_count == 0

        self.add_result(
            expectation_type="expect_duplicate_rows_to_be_below_threshold",
            category="Duplicate Data",
            column_name=None,
            success=success,
            observed_value=f"{dup_count} duplicate rows ({dup_pct}%)",
            expected_value="0 duplicate rows (0.0%)",
            failure_message=f"{dup_count} duplicate rows detected ({dup_pct}% of dataset)."
            if not success
            else None,
            details={"duplicate_count": dup_count, "duplicate_percentage": dup_pct},
            is_major=dup_count > 0,
        )

    # -- 3. Missing values ----------------------------------------------------
    def _evaluate_missing_values(self):
        total_rows = len(self.df)
        if total_rows == 0:
            return

        for col_name in self.df.columns:
            series = self.df[col_name]
            null_count = int(series.isna().sum())
            null_pct = round((null_count / total_rows) * 100.0, 2)

            if null_count == 0:
                threshold_pct = 0.0
                success = True
                exp_type = "expect_column_values_to_not_be_null"
                fail_msg = None
                is_major = False
            elif null_pct <= 5.0:
                threshold_pct = 5.0
                success = True
                exp_type = "expect_column_null_percentage_to_be_below_threshold"
                fail_msg = None
                is_major = False
            else:
                threshold_pct = 5.0
                success = False
                exp_type = "expect_column_null_percentage_to_be_below_threshold"
                fail_msg = (
                    f"Column '{col_name}' has significant missing values: "
                    f"{null_pct}% (acceptable threshold <= 5.0%)."
                )
                is_major = null_pct > 15.0

            if null_pct == 100.0:
                success = False
                fail_msg = f"Column '{col_name}' is 100% empty (all null values)."
                is_major = True

            self.add_result(
                expectation_type=exp_type,
                category="Missing Data",
                column_name=col_name,
                success=success,
                observed_value=f"{null_count} nulls ({null_pct}%)",
                expected_value=f"<= {threshold_pct}% missing",
                failure_message=fail_msg,
                details={
                    "null_count": null_count,
                    "null_percentage": null_pct,
                    "threshold_percentage": threshold_pct,
                },
                is_major=is_major,
            )

    # -- 4. Data types --------------------------------------------------------
    def _evaluate_data_types(self):
        for col_name in self.df.columns:
            series = self.df[col_name].dropna()
            if series.empty:
                continue

            col_prof = self.column_profiles.get(col_name, {})
            type_cat = col_prof.get("type_category", "text")

            if type_cat == "numeric":
                numeric_converted = pd.to_numeric(series, errors="coerce")
                invalid_count = int(numeric_converted.isna().sum())
                success = invalid_count == 0
                self.add_result(
                    expectation_type="expect_column_values_to_be_of_type",
                    category="Schema / Type",
                    column_name=col_name,
                    success=success,
                    observed_value=f"{invalid_count} non-numeric values"
                    if not success
                    else "numeric (valid)",
                    expected_value="numeric",
                    failure_message=f"Column '{col_name}' has {invalid_count} non-numeric value(s) in a numeric column."
                    if not success
                    else None,
                    is_major=not success,
                )

            elif type_cat == "datetime":
                try:
                    dt_converted = pd.to_datetime(series, errors="coerce")
                    invalid_count = int(dt_converted.isna().sum())
                    success = invalid_count == 0
                except Exception:
                    invalid_count = len(series)
                    success = False

                self.add_result(
                    expectation_type="expect_column_values_to_be_datetime_parseable",
                    category="Schema / Type",
                    column_name=col_name,
                    success=success,
                    observed_value=f"{invalid_count} invalid timestamps"
                    if not success
                    else "datetime (valid)",
                    expected_value="datetime",
                    failure_message=f"Column '{col_name}' contains {invalid_count} invalid datetime format(s)."
                    if not success
                    else None,
                    is_major=not success,
                )

            elif type_cat == "boolean":
                valid_bool_set = {True, False, 1, 0, "1", "0", "true", "false", "yes", "no"}
                invalid_count = sum(
                    1
                    for v in series
                    if (isinstance(v, str) and v.strip().lower() not in valid_bool_set)
                    and (
                        not isinstance(v, (bool, int, float))
                        or (isinstance(v, (int, float)) and v not in (0, 1))
                    )
                )
                success = invalid_count == 0
                self.add_result(
                    expectation_type="expect_column_values_to_be_in_type_list",
                    category="Schema / Type",
                    column_name=col_name,
                    success=success,
                    observed_value=f"{invalid_count} non-boolean values"
                    if not success
                    else "boolean (valid)",
                    expected_value="boolean",
                    failure_message=f"Column '{col_name}' contains non-boolean values."
                    if not success
                    else None,
                )

    # -- 5. Numeric ranges ----------------------------------------------------
    def _evaluate_numeric_ranges(self):
        for col_name in self.df.columns:
            col_prof = self.column_profiles.get(col_name, {})
            if col_prof.get("type_category") != "numeric":
                continue

            series = pd.to_numeric(self.df[col_name], errors="coerce").dropna()
            if series.empty:
                continue

            observed_min = float(series.min())
            observed_max = float(series.max())

            name_lower = col_name.lower()
            positive_hints = [
                "age",
                "spend",
                "amount",
                "price",
                "count",
                "cost",
                "salary",
                "income",
                "qty",
                "quantity",
            ]
            if any(hint in name_lower for hint in positive_hints):
                is_non_negative = observed_min >= 0
                self.add_result(
                    expectation_type="expect_column_values_to_be_between",
                    category="Range / Distribution",
                    column_name=col_name,
                    success=is_non_negative,
                    observed_value=f"min={round(observed_min, 2)}, max={round(observed_max, 2)}",
                    expected_value=">= 0 (non-negative)",
                    failure_message=f"Column '{col_name}' contains negative values (min: {round(observed_min, 2)})."
                    if not is_non_negative
                    else None,
                    is_major=not is_non_negative,
                )

            has_inf = np.isinf(series).any()
            self.add_result(
                expectation_type="expect_column_values_to_not_be_infinite",
                category="Range / Distribution",
                column_name=col_name,
                success=not has_inf,
                observed_value="Contains Inf" if has_inf else "Finite",
                expected_value="Finite numbers",
                failure_message=f"Column '{col_name}' contains infinite numeric values."
                if has_inf
                else None,
            )

    # -- 6. Uniqueness --------------------------------------------------------
    def _evaluate_uniqueness(self):
        total_rows = len(self.df)
        if total_rows <= 1:
            return

        for col_name in self.df.columns:
            col_prof = self.column_profiles.get(col_name, {})
            series = self.df[col_name].dropna()
            if series.empty:
                continue

            unique_count = int(series.nunique())
            unique_pct = round((unique_count / total_rows) * 100.0, 2)
            name_lower = col_name.lower()

            id_hints = ["id", "uuid", "guid", "customer_id", "user_id", "order_id", "account_no"]
            is_id_candidate = any(
                hint == name_lower or name_lower.endswith(f"_{hint}") for hint in id_hints
            )
            baseline_uniq_pct = col_prof.get("unique_percentage", 0)

            if is_id_candidate and baseline_uniq_pct == 100.0:
                success = unique_count == len(series)
                self.add_result(
                    expectation_type="expect_column_values_to_be_unique",
                    category="Uniqueness",
                    column_name=col_name,
                    success=success,
                    observed_value=f"{unique_count}/{len(series)} unique ({unique_pct}%)",
                    expected_value="100% unique (Primary Identifier)",
                    failure_message=f"Identifier column '{col_name}' contains duplicate values ({len(series) - unique_count} duplicates)."
                    if not success
                    else None,
                    is_major=not success,
                )
            elif is_id_candidate and baseline_uniq_pct >= 90.0:
                threshold = round(max(90.0, baseline_uniq_pct - 2.0), 1)
                success = unique_pct >= threshold
                self.add_result(
                    expectation_type="expect_column_unique_percentage_to_be_above_threshold",
                    category="Uniqueness",
                    column_name=col_name,
                    success=success,
                    observed_value=f"{unique_pct}% unique",
                    expected_value=f">= {threshold}% unique",
                    failure_message=f"Column '{col_name}' unique percentage {unique_pct}% dropped below {threshold}%."
                    if not success
                    else None,
                )

    # -- 7. Categorical consistency ------------------------------------------
    def _evaluate_categorical_consistency(self):
        for col_name in self.df.columns:
            col_prof = self.column_profiles.get(col_name, {})
            type_cat = col_prof.get("type_category", "")

            if type_cat in ("categorical", "text"):
                series = self.df[col_name].dropna().astype(str)
                if series.empty:
                    continue

                placeholder_nulls = {"", " ", "null", "none", "nan", "n/a", "undefined", "nil"}
                masked_nulls = sum(1 for v in series if v.strip().lower() in placeholder_nulls)
                success = masked_nulls == 0

                self.add_result(
                    expectation_type="expect_column_values_to_not_match_placeholder_nulls",
                    category="Categorical Consistency",
                    column_name=col_name,
                    success=success,
                    observed_value=f"{masked_nulls} placeholder strings"
                    if not success
                    else "Clean strings",
                    expected_value="No unparsed null strings ('n/a', 'null', 'None')",
                    failure_message=f"Column '{col_name}' has {masked_nulls} string value(s) acting as unparsed nulls ('N/A', 'null', empty)."
                    if not success
                    else None,
                )


# ===========================================================================
# SECTION 4 — Template-based rule execution (spec-driven)
# ===========================================================================
def run_template_rules(df: pd.DataFrame) -> list[dict]:
    """
    Apply curated per-domain rule templates if the dataset matches a known schema.
    Returns results in the same dict shape as QualityRuleEvaluator.add_result.
    """
    picked = pick_best_rule_set(list(df.columns))
    if not picked:
        logger.info("No matching rule template set found for this dataset schema.")
        return []

    name, rule_specs, compound_specs, table_specs = picked
    logger.info(f"Applying template rule set '{name}' ({len(rule_specs)} column rules).")

    results: list[dict] = []

    # Column-level templates
    for fn, column, kwargs in rule_specs:
        try:
            outcome: RuleOutcome = fn(df, column, **kwargs)
            results.append(_outcome_to_dict(outcome))
        except Exception as e:
            logger.warning(f"Template rule {fn.__name__} on '{column}' failed: {e}")

    # Compound-key templates
    for columns, fn in compound_specs:
        try:
            outcome = fn(df, columns)
            results.append(_outcome_to_dict(outcome))
        except Exception as e:
            logger.warning(f"Compound rule {fn.__name__} on {columns} failed: {e}")

    # Table-level templates
    for fn in table_specs:
        try:
            outcome = fn(df)
            results.append(_outcome_to_dict(outcome))
        except Exception as e:
            logger.warning(f"Table rule {fn.__name__} failed: {e}")

    return results


def _outcome_to_dict(outcome: RuleOutcome) -> dict:
    """Convert a RuleOutcome into the internal results dict shape."""
    column_name: Optional[str]
    if isinstance(outcome.column, list):
        column_name = ",".join(str(c) for c in outcome.column)
    elif outcome.column is None:
        column_name = None
    else:
        column_name = str(outcome.column)

    return {
        "expectation_type": outcome.rule_type,
        "category": _canonical_category(outcome.category),
        "column_name": column_name,
        "success": outcome.success,
        "observed_value": outcome.observed,
        "expected_value": outcome.expected,
        "failure_message": outcome.failure_message if not outcome.success else None,
        "details": outcome.details or {},
    }


# ===========================================================================
# SECTION 5 — Pipeline orchestration
# ===========================================================================
def run_quality_pipeline(df: pd.DataFrame, profile_dict: dict) -> dict:
    """
    Executes both evaluation layers:
      A) Generic heuristics (data-driven)
      B) Curated domain rule templates (spec-driven)
    Returns calculated score, category summaries, problems, and rule results.
    """
    # Layer A — generic heuristics
    evaluator = QualityRuleEvaluator(df, profile_dict)
    evaluator.evaluate_all()

    # Layer B — domain-specific templates (added on top)
    template_results = run_template_rules(df)
    evaluator.results.extend(template_results)

    all_rules = evaluator.results
    total = len(all_rules)
    passed = sum(1 for r in all_rules if r["success"])
    failed = total - passed

    overall_score = round((passed / total) * 100.0, 1) if total > 0 else 100.0
    grade = calculate_grade(overall_score)

    categories_dict = {
        "Missing Data": {"total": 0, "passed": 0, "failed": 0},
        "Schema / Type": {"total": 0, "passed": 0, "failed": 0},
        "Range / Distribution": {"total": 0, "passed": 0, "failed": 0},
        "Uniqueness": {"total": 0, "passed": 0, "failed": 0},
        "Duplicate Data": {"total": 0, "passed": 0, "failed": 0},
        "Categorical Consistency": {"total": 0, "passed": 0, "failed": 0},
    }

    for r in all_rules:
        cat = r["category"]
        if cat not in categories_dict:
            categories_dict[cat] = {"total": 0, "passed": 0, "failed": 0}
        categories_dict[cat]["total"] += 1
        if r["success"]:
            categories_dict[cat]["passed"] += 1
        else:
            categories_dict[cat]["failed"] += 1

    category_summaries = {}
    for cat_name, stats in categories_dict.items():
        cat_total = stats["total"]
        cat_passed = stats["passed"]
        cat_failed = stats["failed"]
        pass_rate = round((cat_passed / cat_total) * 100.0, 1) if cat_total > 0 else 100.0
        status = "PASSED" if cat_failed == 0 else ("WARNING" if pass_rate >= 70.0 else "FAILED")
        category_summaries[cat_name] = {
            "total": cat_total,
            "passed": cat_passed,
            "failed": cat_failed,
            "pass_rate": pass_rate,
            "status": status,
        }

    # Collect major problems from BOTH layers
    major_problems = list(evaluator.major_problems)
    for r in template_results:
        if not r["success"] and r["failure_message"]:
            if r["failure_message"] not in major_problems and len(major_problems) < 8:
                major_problems.append(r["failure_message"])

    summary = {
        "overall_score": overall_score,
        "grade": grade,
        "total_expectations": total,
        "passed_expectations": passed,
        "failed_expectations": failed,
        "categories": category_summaries,
        "major_quality_problems": major_problems,
        "template_rules_applied": len(template_results) > 0,
    }

    return {
        "overall_score": overall_score,
        "grade": grade,
        "total_expectations": total,
        "passed_expectations": passed,
        "failed_expectations": failed,
        "summary": summary,
        "rules": all_rules,
    }


# ===========================================================================
# SECTION 6 — Persistence & retrieval (unchanged public API)
# ===========================================================================
def generate_quality_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = False,
) -> QualityResponse:
    """
    Computes or retrieves automated quality validation scorecard for a DatasetVersion snapshot.
    """
    version = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.id == version_id,
            DatasetVersion.dataset_id == dataset_id,
        )
        .first()
    )
    if not version:
        raise ValueError(f"DatasetVersion '{version_id}' not found for dataset '{dataset_id}'")

    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()

    existing_result = (
        db.query(QualityValidationResult)
        .filter(QualityValidationResult.dataset_version_id == version_id)
        .first()
    )

    if existing_result and not force_recompute:
        logger.info(
            f"Returning cached QualityValidationResult for '{dataset.name}' V{version.version_number}"
        )
        return _build_quality_response(existing_result, dataset, version)

    # 1. Load DataFrame
    file_path = settings.upload_path / version.stored_filename
    if not file_path.exists():
        raise FileNotFoundError(
            f"Stored file '{version.stored_filename}' for version V{version.version_number} not found on disk."
        )

    file_content = file_path.read_bytes()
    if version.file_type == "csv":
        df, _, _ = parse_csv(file_content)
    elif version.file_type == "xlsx":
        df, _ = parse_excel(file_content)
    else:
        raise ValueError(f"Unsupported file type '{version.file_type}' for quality validation.")

    # 2. Phase 4 baseline
    profile_resp = get_profile_for_version(db, dataset_id, version_id)
    if not profile_resp:
        profile_resp = generate_profile_for_version(db, dataset_id, version_id)
    profile_dict = profile_resp.model_dump()

    logger.info(
        f"Evaluating quality rules for '{dataset.name}' V{version.version_number} ({len(df)} rows)..."
    )

    # 3. Run both rule layers
    pipeline_result = run_quality_pipeline(df, profile_dict)

    # 4. Persist
    if existing_result:
        db.delete(existing_result)
        db.flush()

    quality_record = QualityValidationResult(
        dataset_version_id=version_id,
        overall_score=pipeline_result["overall_score"],
        total_expectations=pipeline_result["total_expectations"],
        passed_expectations=pipeline_result["passed_expectations"],
        failed_expectations=pipeline_result["failed_expectations"],
        evaluated_at=datetime.now(timezone.utc),
        summary=pipeline_result["summary"],
    )
    db.add(quality_record)
    db.flush()

    for rule in pipeline_result["rules"]:
        exp_record = QualityExpectationResult(
            validation_id=quality_record.id,
            expectation_type=rule["expectation_type"],
            category=rule["category"],
            column_name=rule["column_name"],
            success=rule["success"],
            observed_value=rule["observed_value"],
            expected_value=rule["expected_value"],
            failure_message=rule["failure_message"],
            details=rule["details"],
        )
        db.add(exp_record)

    try:
        db.commit()
        db.refresh(quality_record)
        logger.info(
            f"Saved QualityValidationResult (id={quality_record.id}, score={quality_record.overall_score}) "
            f"for DatasetVersion V{version.version_number}"
        )
    except IntegrityError:
        db.rollback()
        logger.info(
            f"Concurrent quality validation write detected for version {version_id}; fetching existing record."
        )
        existing_result = (
            db.query(QualityValidationResult)
            .filter(QualityValidationResult.dataset_version_id == version_id)
            .first()
        )
        if existing_result:
            quality_record = existing_result
        else:
            raise

    return _build_quality_response(quality_record, dataset, version)


def get_quality_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
) -> QualityResponse:
    """
    Retrieves the quality validation result for a dataset version.
    Automatically generates it if not yet computed.
    """
    existing_result = (
        db.query(QualityValidationResult)
        .filter(QualityValidationResult.dataset_version_id == version_id)
        .first()
    )

    if existing_result:
        version = db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        return _build_quality_response(existing_result, dataset, version)

    return generate_quality_for_version(db, dataset_id, version_id, force_recompute=False)


def _build_quality_response(
    record: QualityValidationResult,
    dataset: Dataset,
    version: DatasetVersion,
) -> QualityResponse:
    """Convert database model + expectations into Pydantic QualityResponse."""
    summary_data = record.summary or {}
    grade = summary_data.get("grade", calculate_grade(record.overall_score))

    passed_rules = []
    failed_rules = []

    for exp in record.expectations:
        item = ExpectationRuleResult(
            id=exp.id,
            expectation_type=exp.expectation_type,
            category=exp.category,
            column_name=exp.column_name,
            success=exp.success,
            observed_value=exp.observed_value,
            expected_value=exp.expected_value,
            failure_message=exp.failure_message,
            details=exp.details or {},
        )
        if exp.success:
            passed_rules.append(item)
        else:
            failed_rules.append(item)

    summary_obj = QualitySummary(
        overall_score=record.overall_score,
        grade=grade,
        total_expectations=record.total_expectations,
        passed_expectations=record.passed_expectations,
        failed_expectations=record.failed_expectations,
        categories=summary_data.get("categories", {}),
        major_quality_problems=summary_data.get("major_quality_problems", []),
    )

    return QualityResponse(
        id=record.id,
        dataset_id=dataset.id,
        dataset_version_id=version.id,
        version_number=version.version_number,
        dataset_name=dataset.name,
        overall_score=record.overall_score,
        grade=grade,
        total_expectations=record.total_expectations,
        passed_expectations=record.passed_expectations,
        failed_expectations=record.failed_expectations,
        evaluated_at=record.evaluated_at,
        summary=summary_obj,
        failed_rules=failed_rules,
        passed_rules=passed_rules,
    )