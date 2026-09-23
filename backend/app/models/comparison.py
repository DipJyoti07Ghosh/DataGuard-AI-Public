"""
DataGuard AI — Phase 10 Dataset Version Comparison & Drift Models

Defines persistence models for version-to-version comparisons and column-level drift results.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class DatasetComparison(Base):
    """
    Comparison result between two snapshot versions of the SAME logical dataset.
    Stores overall drift classification, summary evidence, and subsystem deltas.
    """

    __tablename__ = "dataset_comparisons"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    dataset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    baseline_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Status & Overall Classification
    status = Column(String(50), nullable=False, default="COMPLETED")
    overall_drift_status = Column(
        String(50),
        nullable=False,
        default="NO_DRIFT",
        doc="Overall classification: NO_DRIFT | LOW_DRIFT | MEDIUM_DRIFT | HIGH_DRIFT",
    )

    # Subsystem Summary JSONB fields
    schema_drift_summary = Column(JSONB, nullable=False, default=dict)
    numerical_drift_summary = Column(JSONB, nullable=False, default=dict)
    categorical_drift_summary = Column(JSONB, nullable=False, default=dict)
    missingness_drift_summary = Column(JSONB, nullable=False, default=dict)
    uniqueness_drift_summary = Column(JSONB, nullable=False, default=dict)
    quality_drift_summary = Column(JSONB, nullable=True, default=dict)
    risk_drift_summary = Column(JSONB, nullable=True, default=dict)
    anomaly_drift_summary = Column(JSONB, nullable=True, default=dict)
    privacy_drift_summary = Column(JSONB, nullable=True, default=dict)

    # Key explanatory driver bullet strings for overall drift
    drift_drivers = Column(JSONB, nullable=False, default=list)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    compared_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    dataset = relationship("Dataset")
    baseline_version = relationship("DatasetVersion", foreign_keys=[baseline_version_id])
    current_version = relationship("DatasetVersion", foreign_keys=[current_version_id])
    column_drifts = relationship(
        "ColumnDriftResult",
        back_populates="comparison",
        cascade="all, delete-orphan",
        order_by="ColumnDriftResult.column_name",
        lazy="selectin",
    )
    rag_documents = relationship(
        "RAGDocument",
        back_populates="comparison",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "baseline_version_id",
            "current_version_id",
            name="uq_dataset_version_comparison",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DatasetComparison id={self.id} dataset_id={self.dataset_id} "
            f"baseline={self.baseline_version_id} current={self.current_version_id} "
            f"status={self.overall_drift_status}>"
        )


class ColumnDriftResult(Base):
    """
    Column-level comparison and drift evidence between baseline and current versions.
    """

    __tablename__ = "column_drift_results"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    comparison_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_comparisons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    column_name = Column(String(255), nullable=False)
    schema_status = Column(
        String(50),
        nullable=False,
        default="UNCHANGED",
        doc="UNCHANGED | ADDED | REMOVED | TYPE_CHANGED",
    )
    baseline_type = Column(String(100), nullable=True)
    current_type = Column(String(100), nullable=True)
    type_category = Column(String(50), nullable=True)

    # Column drift classification
    drift_status = Column(
        String(50),
        nullable=False,
        default="NO_DRIFT",
        doc="NO_DRIFT | LOW_DRIFT | MEDIUM_DRIFT | HIGH_DRIFT | NOT_APPLICABLE",
    )

    # Detailed metrics & comparisons
    missingness_comparison = Column(JSONB, nullable=False, default=dict)
    uniqueness_comparison = Column(JSONB, nullable=False, default=dict)
    statistical_comparison = Column(JSONB, nullable=False, default=dict)
    quality_impact = Column(JSONB, nullable=True, default=dict)
    risk_impact = Column(JSONB, nullable=True, default=dict)
    anomaly_impact = Column(JSONB, nullable=True, default=dict)
    privacy_impact = Column(JSONB, nullable=True, default=dict)

    # Factual bullet evidence list
    drift_evidence = Column(JSONB, nullable=False, default=list)

    # Relationship
    comparison = relationship("DatasetComparison", back_populates="column_drifts")

    def __repr__(self) -> str:
        return (
            f"<ColumnDriftResult col='{self.column_name}' schema={self.schema_status} "
            f"drift={self.drift_status}>"
        )
