"""
DataGuard AI — Phase 10 Comparison & Drift Pydantic Schemas

Defines request/response contracts for dataset version comparisons and column drift analysis.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class CompareVersionsRequest(BaseModel):
    """Request payload to initiate or retrieve a dataset version comparison."""

    baseline_version_id: UUID = Field(
        ..., description="Reference baseline snapshot version UUID"
    )
    current_version_id: UUID = Field(
        ..., description="Target current snapshot version UUID to compare against baseline"
    )
    force_recompute: Optional[bool] = Field(
        False, description="If True, recomputes drift analysis even if comparison already exists"
    )


class VersionBrief(BaseModel):
    """Brief metadata representing a version in a comparison."""

    id: UUID
    version_number: int
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    created_at: Optional[datetime] = None
    uploaded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SchemaDriftSummary(BaseModel):
    """Aggregated schema change statistics."""

    total_changes: int = 0
    added_columns: List[str] = Field(default_factory=list)
    removed_columns: List[str] = Field(default_factory=list)
    type_changed_columns: List[Dict[str, Any]] = Field(default_factory=list)
    unchanged_columns: List[str] = Field(default_factory=list)


class NumericalDriftSummary(BaseModel):
    """Aggregated numerical distribution drift metrics."""

    columns_evaluated: int = 0
    drifted_columns: List[str] = Field(default_factory=list)
    ks_executed_count: int = 0


class CategoricalDriftSummary(BaseModel):
    """Aggregated categorical distribution drift metrics."""

    columns_evaluated: int = 0
    drifted_columns: List[str] = Field(default_factory=list)
    psi_executed_count: int = 0


class MissingnessDriftSummary(BaseModel):
    """Aggregated missingness shifts across columns."""

    columns_with_increased_missingness: List[str] = Field(default_factory=list)
    max_pp_increase: float = 0.0


class UniquenessDriftSummary(BaseModel):
    """Aggregated uniqueness shifts across columns."""

    columns_with_uniqueness_shifts: List[str] = Field(default_factory=list)
    max_pp_shift: float = 0.0


class QualityDriftSummary(BaseModel):
    """Comparison of Phase 5 data quality results."""

    status: str = "NOT_EVALUATED"
    baseline_score: Optional[float] = None
    current_score: Optional[float] = None
    score_delta: Optional[float] = None
    new_violations_count: int = 0
    resolved_violations_count: int = 0
    new_violations: List[str] = Field(default_factory=list)
    resolved_violations: List[str] = Field(default_factory=list)


class RiskDriftSummary(BaseModel):
    """Comparison of Phase 7 ML column risk predictions."""

    status: str = "NOT_EVALUATED"
    baseline_risk_index: Optional[float] = None
    current_risk_index: Optional[float] = None
    risk_delta: Optional[float] = None
    newly_elevated_risk_columns: List[Dict[str, Any]] = Field(default_factory=list)
    domain_changed_columns: List[Dict[str, Any]] = Field(default_factory=list)


class AnomalyDriftSummary(BaseModel):
    """Comparison of Phase 8 anomaly detection results."""

    status: str = "NOT_EVALUATED"
    baseline_anomaly_score: Optional[float] = None
    current_anomaly_score: Optional[float] = None
    anomaly_delta: Optional[float] = None
    newly_anomalous_columns: List[Dict[str, Any]] = Field(default_factory=list)


class PrivacyDriftSummary(BaseModel):
    """Comparison of Phase 6 PII exposure findings (zero raw PII values)."""

    status: str = "NOT_EVALUATED"
    newly_exposed_pii_columns: List[Dict[str, Any]] = Field(default_factory=list)
    removed_pii_columns: List[str] = Field(default_factory=list)
    entity_changes: List[Dict[str, Any]] = Field(default_factory=list)


class ColumnDriftResponse(BaseModel):
    """Detailed column-level drift analysis and comparison metrics."""

    id: UUID
    column_name: str
    schema_status: str
    baseline_type: Optional[str] = None
    current_type: Optional[str] = None
    type_category: Optional[str] = None
    drift_status: str
    missingness: Dict[str, Any] = Field(default_factory=dict)
    uniqueness: Dict[str, Any] = Field(default_factory=dict)
    statistical_drift: Dict[str, Any] = Field(default_factory=dict)
    quality_impact: Optional[Dict[str, Any]] = None
    risk_impact: Optional[Dict[str, Any]] = None
    anomaly_impact: Optional[Dict[str, Any]] = None
    privacy_impact: Optional[Dict[str, Any]] = None
    drift_evidence: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DatasetComparisonResponse(BaseModel):
    """Comprehensive comparison and drift response payload."""

    id: UUID
    dataset_id: UUID
    dataset_name: str
    baseline_version: VersionBrief
    current_version: VersionBrief
    status: str
    overall_drift_status: str
    drift_drivers: List[str] = Field(default_factory=list)
    schema_summary: Dict[str, Any] = Field(default_factory=dict)
    numerical_summary: Dict[str, Any] = Field(default_factory=dict)
    categorical_summary: Dict[str, Any] = Field(default_factory=dict)
    missingness_summary: Dict[str, Any] = Field(default_factory=dict)
    uniqueness_summary: Dict[str, Any] = Field(default_factory=dict)
    subsystem_deltas: Dict[str, Any] = Field(default_factory=dict)
    columns: List[ColumnDriftResponse] = Field(default_factory=list)
    created_at: datetime
    compared_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComparisonListItemResponse(BaseModel):
    """Brief metadata summary of a past comparison."""

    id: UUID
    dataset_id: UUID
    baseline_version_id: UUID
    baseline_version_number: int
    current_version_id: UUID
    current_version_number: int
    status: str
    overall_drift_status: str
    total_schema_changes: int
    compared_at: datetime

    model_config = ConfigDict(from_attributes=True)
