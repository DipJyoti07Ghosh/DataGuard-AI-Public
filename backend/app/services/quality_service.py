"""
DataGuard AI — Automated Data Quality Engine (Great Expectations Integration)

Generates dataset-specific quality expectations based on Phase 4 profiling baselines,
validates datasets, computes transparent quality scores (0-100), categorizes issues,
and persists structured validation results linked to DatasetVersion.
"""

from pathlib import Path
import logging
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


def calculate_grade(score: float) -> str:
    """Assign human-readable grade based on numerical quality score."""
    if score >= 90.0:
        return "Excellent"
    if score >= 75.0:
        return "Good"
    if score >= 50.0:
        return "Fair"
    return "Poor"


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
        """Run all quality expectation categories."""
        self._evaluate_schema_and_structure()
        self._evaluate_duplicates()
        self._evaluate_missing_values()
        self._evaluate_data_types()
        self._evaluate_numeric_ranges()
        self._evaluate_uniqueness()
        self._evaluate_categorical_consistency()

    def _evaluate_schema_and_structure(self):
        """1. Schema / Type: Validate table column existence and non-empty rows."""
        # Row count check
        row_count = len(self.df)
        expected_rows = self.profile.get("row_count", row_count)
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

        # Expected columns check
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

    def _evaluate_duplicates(self):
        """2. Duplicate Data: Validate dataset-level duplicate row percentage."""
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

    def _evaluate_missing_values(self):
        """3. Missing Data: Column-level null and empty cell validation."""
        total_rows = len(self.df)
        if total_rows == 0:
            return

        for col_name in self.df.columns:
            series = self.df[col_name]
            null_count = int(series.isna().sum())
            null_pct = round((null_count / total_rows) * 100.0, 2)

            col_prof = self.column_profiles.get(col_name, {})

            # Standard Data Quality Missingness Thresholds:
            # - Clean (0% nulls): Expect strictly 0% nulls
            # - Low missingness (<= 5% nulls): Expect <= 5.0% nulls (Passes)
            # - Significant missingness (> 5% nulls): Target acceptable standard is <= 5.0% nulls (Fails)
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
                fail_msg = f"Column '{col_name}' has significant missing values: {null_pct}% (acceptable threshold <= 5.0%)."
                is_major = null_pct > 15.0

            # 100% missing is a critical failure
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

    def _evaluate_data_types(self):
        """4. Schema / Type: Verify inferred column data types and parseability."""
        for col_name in self.df.columns:
            series = self.df[col_name].dropna()
            if series.empty:
                continue

            col_prof = self.column_profiles.get(col_name, {})
            type_cat = col_prof.get("type_category", "text")

            if type_cat == "numeric":
                # Check that non-null values can actually parse as numeric
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
                # Check datetime parseability
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
                # Check boolean or bool-like values
                valid_bool_set = {True, False, 1, 0, "1", "0", "true", "false", "yes", "no"}
                invalid_count = sum(
                    1
                    for v in series
                    if (isinstance(v, str) and v.strip().lower() not in valid_bool_set)
                    and (not isinstance(v, (bool, int, float)) or (isinstance(v, (int, float)) and v not in (0, 1)))
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

    def _evaluate_numeric_ranges(self):
        """5. Range / Distribution: Statistical boundary checks for numeric features."""
        for col_name in self.df.columns:
            col_prof = self.column_profiles.get(col_name, {})
            if col_prof.get("type_category") != "numeric":
                continue

            series = pd.to_numeric(self.df[col_name], errors="coerce").dropna()
            if series.empty:
                continue

            observed_min = float(series.min())
            observed_max = float(series.max())
            observed_mean = float(series.mean())

            # Check for non-negativity for typically positive features (e.g. age, price, spend, count)
            name_lower = col_name.lower()
            positive_hints = ["age", "spend", "amount", "price", "count", "cost", "salary", "income", "qty", "quantity"]
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

            # Check for infinite values
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

    def _evaluate_uniqueness(self):
        """6. Uniqueness: Identifier and unique column checks."""
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

            # If column name suggests ID/Primary Key and profile indicated 100% unique
            id_hints = ["id", "uuid", "guid", "customer_id", "user_id", "order_id", "account_no"]
            is_id_candidate = any(hint == name_lower or name_lower.endswith(f"_{hint}") for hint in id_hints)

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

    def _evaluate_categorical_consistency(self):
        """7. Categorical Consistency: Check text and categorical features for invalid string representations."""
        for col_name in self.df.columns:
            col_prof = self.column_profiles.get(col_name, {})
            type_cat = col_prof.get("type_category", "")

            if type_cat in ("categorical", "text"):
                series = self.df[col_name].dropna().astype(str)
                if series.empty:
                    continue

                # Check for empty whitespace strings or placeholder null strings ('null', 'n/a', 'nan', 'none', '')
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


def run_quality_pipeline(
    df: pd.DataFrame,
    profile_dict: dict,
) -> dict:
    """
    Executes the automated quality validation engine on a DataFrame against its Phase 4 profile.
    Returns calculated score, category summaries, problems, and rule results.
    """
    evaluator = QualityRuleEvaluator(df, profile_dict)
    evaluator.evaluate_all()

    all_rules = evaluator.results
    total = len(all_rules)
    passed = sum(1 for r in all_rules if r["success"])
    failed = total - passed

    overall_score = round((passed / total) * 100.0, 1) if total > 0 else 100.0
    grade = calculate_grade(overall_score)

    # Calculate Category-wise summaries
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

    summary = {
        "overall_score": overall_score,
        "grade": grade,
        "total_expectations": total,
        "passed_expectations": passed,
        "failed_expectations": failed,
        "categories": category_summaries,
        "major_quality_problems": evaluator.major_problems,
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

    # Check for existing cached quality result
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

    # 2. Retrieve or compute Phase 4 Profiling baseline
    profile_resp = get_profile_for_version(db, dataset_id, version_id)
    if not profile_resp:
        profile_resp = generate_profile_for_version(db, dataset_id, version_id)
    profile_dict = profile_resp.model_dump()

    logger.info(
        f"Evaluating quality rules for '{dataset.name}' V{version.version_number} ({len(df)} rows)..."
    )

    # 3. Run validation pipeline
    pipeline_result = run_quality_pipeline(df, profile_dict)

    # 4. Persist to PostgreSQL
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

    # Insert individual expectation results
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
        logger.info(f"Concurrent quality validation write detected for version {version_id}; fetching existing record.")
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
    """Helper to convert database model and expectations into Pydantic QualityResponse."""
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
