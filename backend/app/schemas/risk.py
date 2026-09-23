"""
DataGuard AI — ML Column Risk Prediction Pydantic Schemas

Defines request/response data contracts for ML domain predictions,
composite risk scores (0–100), explainability factors, and query filtering.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ColumnRiskPredictionResponse(BaseModel):
    """Schema representing ML prediction & risk assessment for a single column."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_version_id: UUID
    column_name: str
    predicted_domain: str
    model_confidence: float
    risk_score: float
    risk_level: str
    pii_signal: bool
    pii_confidence: float
    pii_detection_rate: float
    quality_failure_count: int
    feature_snapshot: Dict[str, Any] = Field(default_factory=dict)
    explanation: Dict[str, Any] = Field(default_factory=dict)
    model_version: str
    predicted_at: datetime


class DatasetRiskSummaryResponse(BaseModel):
    """Aggregated dataset-level risk score and column prediction list."""

    model_config = ConfigDict(from_attributes=True)

    dataset_id: UUID
    dataset_version_id: UUID
    version_number: int
    dataset_name: str
    total_columns: int
    dataset_risk_index: float
    overall_risk_level: str
    risk_breakdown: Dict[str, int] = Field(default_factory=dict)
    domain_breakdown: Dict[str, int] = Field(default_factory=dict)
    mean_model_confidence: float
    model_version: str
    predicted_at: datetime
    predictions: List[ColumnRiskPredictionResponse] = Field(default_factory=list)


class RiskDetailsResponse(BaseModel):
    """Detailed response for column risk inspection with applied query filters."""

    model_config = ConfigDict(from_attributes=True)

    summary: Dict[str, Any] = Field(default_factory=dict)
    predictions: List[ColumnRiskPredictionResponse] = Field(default_factory=list)
    total_columns: int
    filtered_count: int
    filters_applied: Dict[str, Any] = Field(default_factory=dict)
