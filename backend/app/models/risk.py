"""
DataGuard AI — Column Risk Prediction & ML Classification SQLAlchemy Models

Defines persistence entities for ML-inferred column domain predictions,
composite risk scores (0–100), explainability factors, and feature snapshots
associated with a DatasetVersion snapshot.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class ColumnRiskPrediction(Base):
    """
    ML domain classification and composite risk assessment for an individual dataset column.
    Integrates Profiling baselines, Quality validations, and PII findings.
    NEVER stores raw sensitive values.
    """

    __tablename__ = "column_risk_predictions"

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
        index=True,
    )
    column_name = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Name of the evaluated dataset column",
    )
    predicted_domain = Column(
        String(100),
        nullable=False,
        index=True,
        doc="ML-classified domain (e.g. Financial, Contact Information, Identifier, Temporal)",
    )
    model_confidence = Column(
        Float,
        nullable=False,
        doc="Calibrated probability score from the scikit-learn classifier (0.0 to 1.0)",
    )
    risk_score = Column(
        Float,
        nullable=False,
        doc="Composite risk score from 0.0 to 100.0 based on PII, domain sensitivity, uniqueness, and quality",
    )
    risk_level = Column(
        String(20),
        nullable=False,
        index=True,
        doc="Risk classification: 'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'",
    )
    pii_signal = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether PII was detected in column name or sample values",
    )
    pii_confidence = Column(
        Float,
        nullable=False,
        default=0.0,
        doc="Highest Presidio PII confidence score for this column",
    )
    pii_detection_rate = Column(
        Float,
        nullable=False,
        default=0.0,
        doc="Highest PII sample match rate",
    )
    quality_failure_count = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of failed Great Expectations quality rules for this column",
    )
    feature_snapshot = Column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Sanitized statistical feature vector snapshot used during inference",
    )
    explanation = Column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Structured explainability breakdown containing risk_factors and protective_factors",
    )
    model_version = Column(
        String(50),
        nullable=False,
        default="column-risk-v1",
        doc="Semantic identifier of the serialized ML model pipeline",
    )
    predicted_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    version = relationship(
        "DatasetVersion",
        back_populates="risk_predictions",
    )

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id", "column_name", name="uq_version_column_risk"
        ),
        Index("ix_column_risk_version_domain", "dataset_version_id", "predicted_domain"),
        Index("ix_column_risk_version_level", "dataset_version_id", "risk_level"),
    )

    def __repr__(self) -> str:
        return (
            f"<ColumnRiskPrediction id={self.id} col='{self.column_name}' "
            f"domain='{self.predicted_domain}' score={self.risk_score} "
            f"level='{self.risk_level}'>"
        )
