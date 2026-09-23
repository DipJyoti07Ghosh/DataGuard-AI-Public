"""
DataGuard AI — Phase 9 Dataset Health & Prioritized Quality Issues Models

Persists:
1. DatasetHealthResult: Dataset-level holistic health score (0-100), health grade,
   and 4-way breakdown (quality_health, risk_health, anomaly_health, privacy_health).
2. DataQualityIssue: Deduplicated logical issues synthesized from Phases 5-8 with
   deterministic priority scoring (0-100) and actionable remediation suggestions.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class DatasetHealthResult(Base):
    """
    Holistic dataset health summary snapshot for a specific DatasetVersion.
    Aggregates signals from Data Quality (P5), PII (P6), ML Column Risk (P7), and Anomalies (P8).
    """

    __tablename__ = "dataset_health_results"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    dataset_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        doc="Reference to the dataset version snapshot evaluated",
    )
    calculated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 0-100 Holistic Health Score & Qualitative Grade
    health_score = Column(
        Float,
        nullable=False,
        default=100.0,
        doc="0-100 composite dataset health score",
    )
    health_grade = Column(
        String(50),
        nullable=False,
        default="EXCELLENT",
        doc="EXCELLENT, GOOD, NEEDS ATTENTION, POOR, CRITICAL",
    )

    # 4-Way Health Breakdown Components (0-100 each)
    quality_health = Column(
        Float,
        nullable=False,
        default=100.0,
        doc="0-100 Quality Health (Phase 5 data quality score)",
    )
    risk_health = Column(
        Float,
        nullable=False,
        default=100.0,
        doc="0-100 Risk Health (100.0 - mean Phase 7 column risk score)",
    )
    anomaly_health = Column(
        Float,
        nullable=False,
        default=100.0,
        doc="0-100 Anomaly Health (100.0 - Phase 8 dataset anomaly score)",
    )
    privacy_health = Column(
        Float,
        nullable=False,
        default=100.0,
        doc="0-100 Privacy Health (100.0 - bounded Phase 6 privacy exposure)",
    )

    # Issue Counts by Severity
    total_issues = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Total number of deduplicated logical issues",
    )
    critical_issues = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of CRITICAL severity issues",
    )
    high_issues = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of HIGH severity issues",
    )
    medium_issues = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of MEDIUM severity issues",
    )
    low_issues = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of LOW severity issues",
    )

    # Structured metadata & cross-signal summary
    summary = Column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Summary metadata, column health cross-tabulation, and top drivers",
    )

    # Relationships
    version = relationship(
        "DatasetVersion",
        back_populates="health_result",
    )
    issues = relationship(
        "DataQualityIssue",
        back_populates="health_result",
        cascade="all, delete-orphan",
        order_by="DataQualityIssue.priority_score.desc(), DataQualityIssue.created_at.asc()",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<DatasetHealthResult id={self.id} version={self.dataset_version_id} "
            f"score={self.health_score:.1f} grade='{self.health_grade}' issues={self.total_issues}>"
        )


class DataQualityIssue(Base):
    """
    Deduplicated, prioritized logical data quality/risk issue.
    Synthesized across upstream Phase 5, 6, 7, and 8 signals.
    """

    __tablename__ = "data_quality_issues"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    dataset_health_result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_health_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Scope & Classification
    column_name = Column(
        String(255),
        nullable=True,
        index=True,
        doc="Target column name, or null for dataset-wide issues like duplicates",
    )
    issue_type = Column(
        String(100),
        nullable=False,
        index=True,
        doc="MISSING_VALUES, DUPLICATES, QUALITY_RULE_VIOLATION, ANOMALY, RARE_CATEGORY, PII_EXPOSURE, HIGH_RISK_COLUMN, TYPE_INCONSISTENCY",
    )
    source = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Primary source subsystem: QUALITY, PII, RISK, ANOMALY, PROFILE",
    )

    # Upstream source severity preserved
    severity = Column(
        String(50),
        nullable=False,
        default="LOW",
        index=True,
        doc="Preserved upstream severity: CRITICAL, HIGH, MEDIUM, LOW",
    )

    # 0-100 Deterministic Priority Score
    priority_score = Column(
        Float,
        nullable=False,
        default=0.0,
        index=True,
        doc="0-100 Deterministic Priority Score for ranking attention",
    )

    # Human-readable Titles & Explanations (Zero raw PII)
    title = Column(
        String(255),
        nullable=False,
        doc="Concise human-readable issue title",
    )
    description = Column(
        Text,
        nullable=False,
        doc="Clear explainable description of what problem was detected",
    )

    # Data Impact
    affected_rows = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Estimated count of rows affected",
    )
    affected_percentage = Column(
        Float,
        nullable=False,
        default=0.0,
        doc="Percentage of dataset rows affected (0-100)",
    )

    # Deterministic Score Components (0-100 heuristics)
    sensitivity_score = Column(
        Float,
        nullable=False,
        default=20.0,
        doc="0-100 data_sensitivity heuristic based on domain/PII context",
    )
    confidence_score = Column(
        Float,
        nullable=False,
        default=80.0,
        doc="0-100 confidence heuristic from upstream detection signals",
    )
    evidence_score = Column(
        Float,
        nullable=False,
        default=25.0,
        doc="0-100 cross-signal evidence heuristic based on multi-phase agreement",
    )

    # Structured Payloads (Privacy-safe: Zero raw PII)
    risk_context = Column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Phase 6/7 context: domain classification, PII entity types, risk score",
    )
    evidence = Column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Detector-specific evidence, thresholds, bounds, detected_methods list",
    )
    recommendation = Column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Safe, non-destructive remediation guidance and suggested investigation actions",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    health_result = relationship(
        "DatasetHealthResult",
        back_populates="issues",
    )
    version = relationship(
        "DatasetVersion",
    )

    __table_args__ = (
        Index("ix_data_quality_issues_health_priority", "dataset_health_result_id", "priority_score"),
        Index("ix_data_quality_issues_version_source", "dataset_version_id", "source"),
    )

    def __repr__(self) -> str:
        return (
            f"<DataQualityIssue id={self.id} col='{self.column_name}' type='{self.issue_type}' "
            f"severity='{self.severity}' priority={self.priority_score:.1f}>"
        )
