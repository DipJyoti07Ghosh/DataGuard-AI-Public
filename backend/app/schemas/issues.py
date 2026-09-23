"""
DataGuard AI — Phase 9 Dataset Health & Data Quality Issues Schemas

Defines Pydantic response models for:
- Holistic Dataset Health & Grades
- Prioritized & Deduplicated Logical Issues
- Safe non-destructive remediation recommendations
- Zero Raw PII exposure guaranteed
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, ConfigDict, Field


class RemediationRecommendation(BaseModel):
    """Structured, safe, non-destructive remediation suggestion."""
    summary: str = Field(..., description="High-level remediation overview")
    investigation_steps: List[str] = Field(default_factory=list, description="Recommended diagnostic and verification actions")
    preventive_measures: List[str] = Field(default_factory=list, description="Long-term data engineering and validation safeguards")
    caution_note: Optional[str] = Field(None, description="Important caution warning regarding non-destructive processing")


class DataQualityIssueResponse(BaseModel):
    """Detailed response model for a single deduplicated logical issue."""
    id: uuid.UUID
    dataset_health_result_id: uuid.UUID
    dataset_version_id: uuid.UUID
    column_name: Optional[str] = None
    issue_type: str
    source: str
    severity: str
    priority_score: float
    title: str
    description: str
    affected_rows: int
    affected_percentage: float
    sensitivity_score: float
    confidence_score: float
    evidence_score: float
    risk_context: Dict[str, Any] = Field(default_factory=dict)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    recommendation: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ColumnHealthMatrixItem(BaseModel):
    """Matrix summary of cross-signal health for an individual column."""
    column_name: str
    data_type: Optional[str] = None
    quality_status: str = "CLEAN"  # CLEAN, VIOLATION
    quality_issues_count: int = 0
    pii_detected: bool = False
    pii_entities: List[str] = Field(default_factory=list)
    risk_level: str = "LOW"
    risk_score: float = 0.0
    domain: Optional[str] = None
    anomaly_detected: bool = False
    anomaly_severity: str = "NONE"
    anomaly_score: float = 0.0
    issue_count: int = 0
    highest_priority: float = 0.0
    cross_signal_count: int = 0


class DatasetHealthSummaryResponse(BaseModel):
    """Holistic Dataset Health & Issues Overview response."""
    id: uuid.UUID
    dataset_version_id: uuid.UUID
    calculated_at: datetime
    health_score: float = Field(..., description="0-100 Holistic Health Score")
    health_grade: str = Field(..., description="EXCELLENT, GOOD, NEEDS ATTENTION, POOR, CRITICAL")
    
    # 4-Way Health Breakdown
    quality_health: float = Field(..., description="0-100 Quality Health")
    risk_health: float = Field(..., description="0-100 Risk Health")
    anomaly_health: float = Field(..., description="0-100 Anomaly Health")
    privacy_health: float = Field(..., description="0-100 Privacy Health")

    # Counts
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    columns_affected_count: int = 0
    total_columns_evaluated: int = 0

    # Top Prioritized Issues
    top_issues: List[DataQualityIssueResponse] = Field(default_factory=list)
    column_health_matrix: List[ColumnHealthMatrixItem] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class IssueListResponse(BaseModel):
    """Filtered list of prioritized issues."""
    dataset_version_id: uuid.UUID
    health_score: float
    health_grade: str
    total_count: int
    issues: List[DataQualityIssueResponse]
