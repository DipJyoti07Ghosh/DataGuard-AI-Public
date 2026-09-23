"""
DataGuard AI — Anomaly & Outlier Detection Pydantic Schemas

Defines request/response contracts for dataset-level anomaly summaries,
column-level anomaly findings, detector evidence breakdown, and filtered views.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class AnomalyFindingResponse(BaseModel):
    """Schema representing granular anomaly detection findings for a single column."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    detection_result_id: UUID
    column_name: str
    detection_method: str
    anomaly_count: int
    anomaly_rate: float
    severity: str
    score: float
    statistical_summary: Dict[str, Any] = Field(default_factory=dict)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    explanation: Dict[str, Any] = Field(default_factory=dict)


class DatasetAnomalySummaryResponse(BaseModel):
    """Aggregated dataset-level anomaly summary and column findings scorecard."""

    model_config = ConfigDict(from_attributes=True)

    dataset_id: UUID
    dataset_version_id: UUID
    version_number: int
    dataset_name: str
    total_columns_analyzed: int
    columns_with_anomalies: int
    total_anomalies: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    dataset_anomaly_score: float
    overall_severity: str
    method_breakdown: Dict[str, int] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    analyzed_at: datetime
    findings: List[AnomalyFindingResponse] = Field(default_factory=list)


class AnomalyDetailsResponse(BaseModel):
    """Detailed response for column anomaly inspection with query filtering."""

    model_config = ConfigDict(from_attributes=True)

    summary: Dict[str, Any] = Field(default_factory=dict)
    findings: List[AnomalyFindingResponse] = Field(default_factory=list)
    total_findings: int
    filtered_count: int
    filters_applied: Dict[str, Any] = Field(default_factory=dict)
