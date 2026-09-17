"""
DataGuard AI — Dataset & DatasetVersion SQLAlchemy Models

Defines the core persistence entities for logical datasets and their snapshot versions.
Central entity model for all downstream profiling, quality, PII, and drift metadata.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class Dataset(Base):
    """
    Logical dataset entity.
    Groups one or more chronological versions of the same conceptual data asset.
    """

    __tablename__ = "datasets"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        doc="Unique human-readable dataset name",
    )
    description = Column(
        Text,
        nullable=True,
        doc="Optional description of the dataset purpose and domain",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    versions = relationship(
        "DatasetVersion",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="desc(DatasetVersion.version_number)",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Dataset id={self.id} name='{self.name}'>"


class DatasetVersion(Base):
    """
    Individual snapshot version of a logical dataset.
    Stores ingestion metadata, file reference, and structural schema details.
    """

    __tablename__ = "dataset_versions"

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
    version_number = Column(
        Integer,
        nullable=False,
        doc="Sequential version number (1, 2, 3...)",
    )
    original_filename = Column(
        String(255),
        nullable=False,
        doc="Original filename uploaded by the user",
    )
    stored_filename = Column(
        String(255),
        nullable=False,
        doc="Collision-safe filename on disk inside backend/uploads/",
    )
    file_type = Column(
        String(20),
        nullable=False,
        doc="File extension / format (csv, xlsx)",
    )
    file_size_bytes = Column(
        BigInteger,
        nullable=False,
        doc="File size in bytes",
    )
    row_count = Column(
        Integer,
        nullable=False,
        doc="Total row count extracted during ingestion",
    )
    column_count = Column(
        Integer,
        nullable=False,
        doc="Total column count extracted during ingestion",
    )
    column_names = Column(
        JSONB,
        nullable=False,
        doc="Ordered list of column names (JSON array)",
    )
    column_dtypes = Column(
        JSONB,
        nullable=False,
        doc="Mapping of column name to inferred pandas dtype (JSON object)",
    )
    encoding = Column(
        String(50),
        nullable=True,
        doc="Character encoding detected for CSV files (e.g. utf-8)",
    )
    delimiter = Column(
        String(10),
        nullable=True,
        doc="Detected delimiter for CSV files",
    )
    sheet_name = Column(
        String(100),
        nullable=True,
        doc="Selected sheet name for Excel workbooks",
    )
    uploaded_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    dataset = relationship(
        "Dataset",
        back_populates="versions",
    )
    profiling_result = relationship(
        "ProfilingResult",
        back_populates="version",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    quality_result = relationship(
        "QualityValidationResult",
        back_populates="version",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    pii_result = relationship(
        "PIIScanResult",
        back_populates="version",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "version_number", name="uq_dataset_version_number"
        ),
        CheckConstraint(
            "version_number > 0", name="ck_version_number_positive"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DatasetVersion id={self.id} dataset_id={self.dataset_id} "
            f"v={self.version_number} rows={self.row_count} cols={self.column_count}>"
        )
