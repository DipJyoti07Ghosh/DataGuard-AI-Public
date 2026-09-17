"""
DataGuard AI — Pydantic Schemas for Data Quality Validation

Defines request/response data contracts for automated Great Expectations rules,
quality scores, categorical failure breakdowns, and expectation details.
"""

from datetime import datetime
from uuid import UUID
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class ExpectationRuleResult(BaseModel):
    """Granular outcome of an individual quality rule check."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = Field(None, description="Expectation result UUID")
    expectation_type: str = Field(..., description="Great Expectations rule name")
    category: str = Field(
        ...,
        description="Category: 'Missing Data' | 'Schema / Type' | 'Range / Distribution' | 'Uniqueness' | 'Duplicate Data' | 'Categorical Consistency' | 'Other'",
    )
    column_name: str | None = Field(None, description="Target column or None for table-level rules")
    success: bool = Field(..., description="True if rule passed, False if failed")
    observed_value: str | None = Field(None, description="Observed dataset value or percentage")
    expected_value: str | None = Field(None, description="Expected threshold or condition")
    failure_message: str | None = Field(None, description="Human-readable problem explanation")
    details: dict[str, Any] | None = Field(default_factory=dict, description="Safe execution diagnostics")


class CategorySummary(BaseModel):
    """Aggregate health summary for a specific quality category."""

    total: int = Field(0, description="Total rules evaluated in this category")
    passed: int = Field(0, description="Passed rules in this category")
    failed: int = Field(0, description="Failed rules in this category")
    pass_rate: float = Field(100.0, description="Percentage of passed rules (0.0 to 100.0)")
    status: str = Field("PASSED", description="'PASSED' | 'FAILED' | 'WARNING'")


class QualitySummary(BaseModel):
    """Structured quality summary with category breakdown and major problems."""

    overall_score: float = Field(..., description="Overall dataset quality score (0-100)")
    grade: str = Field(..., description="Score grade: 'Excellent' | 'Good' | 'Fair' | 'Poor'")
    total_expectations: int = Field(..., description="Total quality rules evaluated")
    passed_expectations: int = Field(..., description="Rules that succeeded")
    failed_expectations: int = Field(..., description="Rules that failed")
    categories: dict[str, CategorySummary] = Field(
        default_factory=dict, description="Category-wise metrics breakdown"
    )
    major_quality_problems: list[str] = Field(
        default_factory=list, description="Top identified quality anomalies requiring attention"
    )


class QualityResponse(BaseModel):
    """Complete quality validation scorecard response for a DatasetVersion."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="QualityValidationResult UUID")
    dataset_id: UUID = Field(..., description="Dataset UUID")
    dataset_version_id: UUID = Field(..., description="DatasetVersion UUID")
    version_number: int = Field(..., description="Sequential version number")
    dataset_name: str = Field(..., description="Logical dataset name")

    overall_score: float = Field(..., description="Calculated quality score (0.0 - 100.0)")
    grade: str = Field(..., description="'Excellent' | 'Good' | 'Fair' | 'Poor'")
    total_expectations: int = Field(..., description="Total rules evaluated")
    passed_expectations: int = Field(..., description="Total rules passed")
    failed_expectations: int = Field(..., description="Total rules failed")
    evaluated_at: datetime = Field(..., description="Timestamp of validation run")

    summary: QualitySummary = Field(..., description="Category metrics and problem highlights")
    failed_rules: list[ExpectationRuleResult] = Field(
        default_factory=list, description="List of failed expectations with problem details"
    )
    passed_rules: list[ExpectationRuleResult] = Field(
        default_factory=list, description="List of passing expectations"
    )
