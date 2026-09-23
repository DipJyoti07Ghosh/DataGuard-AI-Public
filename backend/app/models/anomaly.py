"""
DataGuard AI — Anomaly & Outlier Detection SQLAlchemy Models

Defines database models for storing dataset-level anomaly detection summaries
and column-level anomaly findings across IQR, Z-score, Isolation Forest,
and categorical frequency analysis.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class AnomalyDetectionResult(Base):
    """
    Dataset-version level anomaly detection execution result.
    Summarizes anomaly findings across statistical, ML, and categorical detectors.
    """

    __tablename__ = "anomaly_detection_results"

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
        doc="Reference to the dataset version snapshot analyzed",
    )
    analyzed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    total_columns_analyzed = Column(
        Integer,
        default=0,
        nullable=False,
    )
    columns_with_anomalies = Column(
        Integer,
        default=0,
        nullable=False,
    )
    total_anomalies = Column(
        Integer,
        default=0,
        nullable=False,
        doc="Aggregate count of distinct anomalous observation flags across columns",
    )
    critical_count = Column(
        Integer,
        default=0,
        nullable=False,
    )
    high_count = Column(
        Integer,
        default=0,
        nullable=False,
    )
    medium_count = Column(
        Integer,
        default=0,
        nullable=False,
    )
    low_count = Column(
        Integer,
        default=0,
        nullable=False,
    )
    dataset_anomaly_score = Column(
        Float,
        default=0.0,
        nullable=False,
        doc="Composite dataset anomaly severity index (0.0 to 100.0)",
    )
    summary = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Method breakdown, sampling metadata, and execution parameters",
    )

    # Relationships
    version = relationship(
        "DatasetVersion",
        back_populates="anomaly_result",
        lazy="selectin",
    )
    findings = relationship(
        "AnomalyFinding",
        back_populates="detection_result",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AnomalyFinding.score.desc(), AnomalyFinding.column_name.asc()",
    )

    def __repr__(self) -> str:
        return (
            f"<AnomalyDetectionResult id={self.id} version_id={self.dataset_version_id} "
            f"score={self.dataset_anomaly_score} total_anomalies={self.total_anomalies}>"
        )


class AnomalyFinding(Base):
    """
    Granular column-level anomaly finding.
    Preserves detector-specific evidence (IQR, Z-Score, Isolation Forest, Categorical)
    and transparent severity scoring with zero raw PII persistence.
    """

    __tablename__ = "anomaly_findings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    detection_result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("anomaly_detection_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name = Column(
        String(255),
        nullable=False,
        index=True,
    )
    detection_method = Column(
        String(100),
        nullable=False,
        doc="Primary classification method or 'MULTI_METHOD_CONSENSUS'",
    )
    anomaly_count = Column(
        Integer,
        default=0,
        nullable=False,
    )
    anomaly_rate = Column(
        Float,
        default=0.0,
        nullable=False,
        doc="Percentage of evaluated rows exhibiting anomalous characteristics",
    )
    severity = Column(
        String(50),
        default="LOW",
        nullable=False,
        doc="'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'",
    )
    score = Column(
        Float,
        default=0.0,
        nullable=False,
        doc="Deterministic anomaly severity score (0.0 to 100.0)",
    )
    statistical_summary = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Numerical bounds, quartiles, moments, or categorical frequency distributions",
    )
    evidence = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Individual detector outputs: iqr, zscore, isolation_forest, categorical_frequency",
    )
    explanation = Column(
        JSONB,
        default=dict,
        nullable=False,
        doc="Structured explainability drivers, caveats, and contextual Phase 7 risk info",
    )

    # Relationships
    detection_result = relationship(
        "AnomalyDetectionResult",
        back_populates="findings",
    )

    __table_args__ = (
        Index("ix_anomaly_findings_result_severity", "detection_result_id", "severity"),
        Index("ix_anomaly_findings_result_score", "detection_result_id", "score"),
    )

    def __repr__(self) -> str:
        return (
            f"<AnomalyFinding id={self.id} col='{self.column_name}' "
            f"method='{self.detection_method}' severity='{self.severity}' score={self.score}>"
        )
