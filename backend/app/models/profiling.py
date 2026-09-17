"""
DataGuard AI — Profiling Result SQLAlchemy Model

Stores automated statistical profiling metadata for a specific DatasetVersion.
Serves as the foundation for data quality scoring, anomaly detection, and drift analysis.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class ProfilingResult(Base):
    """
    Comprehensive statistical profile for a single snapshot DatasetVersion.
    """

    __tablename__ = "profiling_results"

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

    # Dataset-level summary metrics
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)
    missing_cells = Column(Integer, nullable=False)
    missing_cells_percentage = Column(Float, nullable=False)
    duplicate_rows = Column(Integer, nullable=False)
    duplicate_rows_percentage = Column(Float, nullable=False)
    memory_size_bytes = Column(BigInteger, nullable=False)

    # Type breakdown counts
    numeric_columns_count = Column(Integer, nullable=False, default=0)
    categorical_columns_count = Column(Integer, nullable=False, default=0)
    datetime_columns_count = Column(Integer, nullable=False, default=0)
    boolean_columns_count = Column(Integer, nullable=False, default=0)

    # Detailed Column Profiles (JSONB)
    # Mapping of column_name -> { stats, quantiles, histogram, top_categories, etc. }
    column_profiles = Column(
        JSONB,
        nullable=False,
        doc="Detailed per-column summary stats, quantiles, distributions, and histograms",
    )

    # Correlation Matrix (JSONB)
    # Mapping of colA -> { colB: corr_val, ... }
    correlations = Column(
        JSONB,
        nullable=True,
        doc="Pearson correlation matrix for numerical columns",
    )

    generated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship to DatasetVersion
    version = relationship(
        "DatasetVersion",
        back_populates="profiling_result",
    )

    __table_args__ = (
        UniqueConstraint(
            "dataset_version_id", name="uq_profiling_result_dataset_version"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProfilingResult id={self.id} version_id={self.dataset_version_id} "
            f"rows={self.row_count} cols={self.column_count}>"
        )
