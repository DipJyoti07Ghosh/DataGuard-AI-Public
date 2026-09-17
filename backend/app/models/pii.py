"""
DataGuard AI — PII & Sensitive Data Detection SQLAlchemy Models

Defines persistence entities for automated PII detection results,
scanned column metrics, and sensitive entity findings associated with a DatasetVersion.
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
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class PIIScanResult(Base):
    """
    Top-level PII scan execution result for a single DatasetVersion snapshot.
    Stores summary metadata, risk counts, and total findings.
    """

    __tablename__ = "pii_scan_results"

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
    scanned_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    total_columns_scanned = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Total number of dataset columns inspected",
    )
    pii_columns_count = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of distinct columns where PII was identified",
    )
    total_findings = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Total count of individual PII entity findings across all columns",
    )
    summary = Column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Structured summary containing risk breakdown, entity counts, and scan metadata",
    )

    # Relationships
    version = relationship(
        "DatasetVersion",
        back_populates="pii_result",
    )
    findings = relationship(
        "PIIFinding",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PIIFinding.risk_level.asc(), PIIFinding.column_name.asc()",
    )

    def __repr__(self) -> str:
        return (
            f"<PIIScanResult id={self.id} version_id={self.dataset_version_id} "
            f"pii_cols={self.pii_columns_count} findings={self.total_findings}>"
        )


class PIIFinding(Base):
    """
    Specific PII entity detection finding within a single column.
    Stores detection source, confidence, sampling rates, risk level, and masked preview.
    NEVER stores raw sensitive values.
    """

    __tablename__ = "pii_findings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    scan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pii_scan_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_name = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Name of the column containing sensitive data",
    )
    entity_type = Column(
        String(100),
        nullable=False,
        index=True,
        doc="Presidio entity type (e.g., EMAIL_ADDRESS, PHONE_NUMBER, PERSON, IP_ADDRESS, CREDIT_CARD, US_SSN, LOCATION, URL)",
    )
    detection_source = Column(
        String(50),
        nullable=False,
        doc="Source of evidence: 'VALUE', 'COLUMN_NAME', or 'COLUMN_AND_VALUE'",
    )
    confidence = Column(
        Float,
        nullable=False,
        doc="Detection confidence score between 0.0 and 1.0",
    )
    sampled_count = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of sample values inspected for this column",
    )
    detected_count = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of sampled values that matched this entity type",
    )
    detection_rate = Column(
        Float,
        nullable=False,
        default=0.0,
        doc="Ratio of detected values to total sampled values (0.0 to 1.0)",
    )
    risk_level = Column(
        String(20),
        nullable=False,
        index=True,
        doc="Application-level risk classification: 'HIGH', 'MEDIUM', or 'LOW'",
    )
    masked_preview = Column(
        String(255),
        nullable=True,
        doc="Sanitized/masked sample representation (e.g. j***@e******.com, ******3210)",
    )
    details = Column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Additional metadata, recognizer scores, and heuristic matching signals",
    )

    # Relationship
    scan = relationship(
        "PIIScanResult",
        back_populates="findings",
    )

    __table_args__ = (
        Index("ix_pii_findings_scan_entity", "scan_id", "entity_type"),
        Index("ix_pii_findings_scan_risk", "scan_id", "risk_level"),
    )

    def __repr__(self) -> str:
        return (
            f"<PIIFinding id={self.id} col='{self.column_name}' "
            f"entity='{self.entity_type}' risk='{self.risk_level}' "
            f"conf={self.confidence:.2f}>"
        )
