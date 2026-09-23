"""
DataGuard AI — Phase 13 Dashboard Pydantic Schemas

Strict presentation schemas aggregating Phase 4-10 stored results.
Never includes raw PII values or raw dataset records.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Component Summaries
# ---------------------------------------------------------------------------

class DashboardHealthSummary(BaseModel):
    available: bool = False
    dataset_health_score: Optional[float] = None
    grade: Optional[str] = None
    quality_health: Optional[float] = None
    risk_health: Optional[float] = None
    anomaly_health: Optional[float] = None
    privacy_health: Optional[float] = None
    computed_at: Optional[datetime] = None


class QualityFailedRule(BaseModel):
    rule_name: str
    column_name: Optional[str] = None
    severity: str
    status: str
    details: Optional[str] = None


class DashboardQualitySummary(BaseModel):
    available: bool = False
    quality_score: Optional[float] = None
    grade: Optional[str] = None
    status: str = "NOT_EVALUATED"  # "EVALUATED" or "NOT_EVALUATED"
    total_rules_evaluated: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    categories: Dict[str, Any] = Field(default_factory=dict)
    failed_expectations: List[QualityFailedRule] = Field(default_factory=list)
    computed_at: Optional[datetime] = None


class ColumnRiskItem(BaseModel):
    column_name: str
    domain: Optional[str] = None
    risk_level: str
    risk_score: float
    confidence: Optional[float] = None


class DashboardRiskSummary(BaseModel):
    available: bool = False
    columns_analyzed: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    distribution: List[Dict[str, Any]] = Field(default_factory=list)
    column_risks: List[ColumnRiskItem] = Field(default_factory=list)
    computed_at: Optional[datetime] = None


class PIICategoryItem(BaseModel):
    category: str
    count: int
    severity: str
    confidence: Optional[float] = None


class PIIColumnItem(BaseModel):
    column_name: str
    entity_types: List[str] = Field(default_factory=list)
    highest_severity: str
    findings_count: int = 0


class DashboardPrivacySummary(BaseModel):
    available: bool = False
    pii_columns_count: int = 0
    total_findings_count: int = 0
    highest_severity: Optional[str] = None
    detected_categories: List[PIICategoryItem] = Field(default_factory=list)
    columns: List[PIIColumnItem] = Field(default_factory=list)
    computed_at: Optional[datetime] = None


class AnomalyColumnItem(BaseModel):
    column_name: str
    detector_method: str
    severity: str
    anomaly_rate: float
    anomaly_count: int


class DashboardAnomalySummary(BaseModel):
    available: bool = False
    anomalous_columns_count: int = 0
    total_anomalies_count: int = 0
    dataset_anomaly_score: Optional[float] = None
    detector_methods: List[Dict[str, Any]] = Field(default_factory=list)
    severity_distribution: Dict[str, int] = Field(default_factory=dict)
    anomalous_columns: List[AnomalyColumnItem] = Field(default_factory=list)
    computed_at: Optional[datetime] = None


class DashboardIssueItem(BaseModel):
    id: str
    title: str
    issue_type: str
    severity: str
    priority_score: float
    affected_columns: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    status: str = "OPEN"


class DashboardIssuesSummary(BaseModel):
    available: bool = False
    total_issues: int = 0
    high_priority_count: int = 0
    medium_priority_count: int = 0
    low_priority_count: int = 0
    prioritized_issues: List[DashboardIssueItem] = Field(default_factory=list)
    computed_at: Optional[datetime] = None


class ColumnMissingnessItem(BaseModel):
    column_name: str
    data_type: str
    missing_count: int
    missing_percentage: float


class DashboardProfilingSummary(BaseModel):
    available: bool = False
    row_count: int = 0
    column_count: int = 0
    numeric_columns_count: int = 0
    categorical_columns_count: int = 0
    total_missing_cells: int = 0
    missing_percentage: float = 0.0
    duplicate_rows: int = 0
    duplicate_percentage: float = 0.0
    top_missing_columns: List[ColumnMissingnessItem] = Field(default_factory=list)
    column_distributions: Dict[str, Any] = Field(default_factory=dict)
    computed_at: Optional[datetime] = None


class ColumnDriftItem(BaseModel):
    column_name: str
    drift_type: str
    severity: str
    metric_name: Optional[str] = None
    drift_score: Optional[float] = None
    p_value: Optional[float] = None


class DashboardDriftSummary(BaseModel):
    available: bool = False
    has_comparison: bool = False
    comparison_id: Optional[str] = None
    baseline_version_id: Optional[str] = None
    baseline_version_number: Optional[int] = None
    current_version_id: Optional[str] = None
    current_version_number: Optional[int] = None
    overall_drift_severity: Optional[str] = None
    drift_score: Optional[float] = None
    drifted_columns_count: int = 0
    column_drifts: List[ColumnDriftItem] = Field(default_factory=list)
    computed_at: Optional[datetime] = None


class DashboardVersionTrendItem(BaseModel):
    version_id: str
    version_number: int
    created_at: Optional[datetime] = None
    dataset_health: Optional[float] = None
    quality_health: Optional[float] = None
    risk_health: Optional[float] = None
    privacy_health: Optional[float] = None
    anomaly_health: Optional[float] = None


class DashboardTrendsSummary(BaseModel):
    available: bool = False
    has_sufficient_history: bool = False
    versions: List[DashboardVersionTrendItem] = Field(default_factory=list)


class AttentionColumn(BaseModel):
    column_name: str
    risk_level: Optional[str] = None
    quality_status: Optional[str] = None
    anomaly_severity: Optional[str] = None
    pii_severity: Optional[str] = None
    issue_count: int = 0


class DashboardInsight(BaseModel):
    category: str
    severity: str
    message: str


class DashboardDatasetInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class DashboardVersionInfo(BaseModel):
    id: str
    dataset_id: str
    version_number: int
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    created_at: Optional[datetime] = None


class DashboardVersionOption(BaseModel):
    id: str
    version_number: int
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Main Dashboard Response
# ---------------------------------------------------------------------------

class DashboardResponse(BaseModel):
    dataset: DashboardDatasetInfo
    version: DashboardVersionInfo
    all_versions: List[DashboardVersionOption] = Field(default_factory=list)
    health: DashboardHealthSummary
    quality: DashboardQualitySummary
    risk: DashboardRiskSummary
    privacy: DashboardPrivacySummary
    anomalies: DashboardAnomalySummary
    issues: DashboardIssuesSummary
    profiling: DashboardProfilingSummary
    drift: DashboardDriftSummary
    trends: DashboardTrendsSummary
    attention_columns: List[AttentionColumn] = Field(default_factory=list)
    insights: List[DashboardInsight] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
