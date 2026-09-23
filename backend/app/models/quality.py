"""
DataGuard AI — Quality Validation SQLAlchemy Models

Defines persistence entities for automated data quality validation results
and individual expectation check outcomes associated with a DatasetVersion.
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class QualityValidationResult(Base):
    """
    Top-level quality validation run for a single DatasetVersion snapshot.
    Stores overall quality score, expectation counts, and summary breakdown.
    """

    __tablename__ = "quality_validation_results"

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
    )

    # Core scoring metrics
    overall_score = Column(
        Float,
        nullable=False,
        doc="Quality score from 0.0 to 100.0 based on passed vs total expectations",
    )
    total_expectations = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Total number of quality rules evaluated",
    )
    passed_expectations = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of quality rules that passed",
    )
    failed_expectations = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of quality rules that failed",
    )

    evaluated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Summary JSONB (category pass rates, major quality problems list)
    summary = Column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Structured summary containing category breakdown and major problems",
    )

    # Relationships
    version = relationship(
        "DatasetVersion",
        back_populates="quality_result",
    )
    expectations = relationship(
        "QualityExpectationResult",
        back_populates="validation_result",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="QualityExpectationResult.success.asc(), QualityExpectationResult.column_name.asc()",
    )

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id", name="uq_quality_validation_dataset_version"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<QualityValidationResult id={self.id} version_id={self.dataset_version_id} "
            f"score={self.overall_score} passed={self.passed_expectations}/{self.total_expectations}>"
        )


class QualityExpectationResult(Base):
    """
    Granular result for a single expectation rule evaluated against a DatasetVersion.
    """

    __tablename__ = "quality_expectation_results"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    validation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("quality_validation_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    expectation_type = Column(
        String(100),
        nullable=False,
        index=True,
        doc="Name of the Great Expectations rule (e.g. expect_column_values_to_not_be_null)",
    )
    category = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Category: 'Missing Data' | 'Schema / Type' | 'Range / Distribution' | 'Uniqueness' | 'Duplicate Data' | 'Categorical Consistency' | 'Other'",
    )
    column_name = Column(
        String(255),
        nullable=True,
        index=True,
        doc="Name of target column, or NULL for dataset-level expectations",
    )
    success = Column(
        Boolean,
        nullable=False,
        index=True,
        doc="Whether the expectation passed (True) or failed (False)",
    )
    observed_value = Column(
        String(255),
        nullable=True,
        doc="Human-readable observed metric (e.g. '18.2% missing', '7 duplicate rows')",
    )
    expected_value = Column(
        String(255),
        nullable=True,
        doc="Human-readable expected threshold (e.g. '<= 5.0% missing', '0 duplicate rows')",
    )
    failure_message = Column(
        Text,
        nullable=True,
        doc="Clear, non-technical explanation of the quality issue",
    )
    details = Column(
        JSONB,
        nullable=True,
        default=dict,
        doc="Safe structured parameters and execution diagnostics (no raw PII)",
    )

    # Relationship
    validation_result = relationship(
        "QualityValidationResult",
        back_populates="expectations",
    )

    def __repr__(self) -> str:
        return (
            f"<QualityExpectationResult id={self.id} rule='{self.expectation_type}' "
            f"col='{self.column_name}' success={self.success}>"
        )
