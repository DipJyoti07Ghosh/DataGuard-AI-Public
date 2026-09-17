"""
DataGuard AI — Pydantic Schemas for Datasets & Dataset Versions

These schemas define the API contracts for dataset upload, versioning,
listing, details, and inspections across Phase 2 and Phase 3.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Column & Ingestion Schemas (Phase 2 Compatible)
# ---------------------------------------------------------------------------
class ColumnMetadata(BaseModel):
    """Metadata for a single column in the dataset."""

    name: str = Field(..., description="Column name")
    dtype: str = Field(..., description="Inferred pandas dtype")
    nullable: bool = Field(..., description="Whether the column contains null values")
    missing_count: int = Field(..., description="Number of missing values")
    missing_percentage: float = Field(..., description="Percentage of missing values (0-100)")
    unique_count: int = Field(..., description="Number of unique non-null values")
    unique_percentage: float = Field(..., description="Percentage of unique values (0-100)")
    sample_values: list = Field(
        default_factory=list,
        description="Sample representative values (sensitive values masked)",
    )


# ---------------------------------------------------------------------------
# Dataset & Version Schemas (Phase 3 Persistence)
# ---------------------------------------------------------------------------
class DatasetVersionSummary(BaseModel):
    """Summary of a single dataset version."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="DatasetVersion UUID")
    dataset_id: UUID = Field(..., description="Parent Dataset UUID")
    version_number: int = Field(..., description="Sequential version number")
    original_filename: str = Field(..., description="Original filename")
    stored_filename: str = Field(..., description="Safe filename in uploads directory")
    file_type: str = Field(..., description="File format (csv, xlsx)")
    file_size_bytes: int = Field(..., description="File size in bytes")
    row_count: int = Field(..., description="Number of rows")
    column_count: int = Field(..., description="Number of columns")
    column_names: list[str] = Field(default_factory=list, description="List of column names")
    column_dtypes: dict[str, str] = Field(default_factory=dict, description="Mapping of col to dtype")
    encoding: str | None = Field(None, description="CSV encoding")
    delimiter: str | None = Field(None, description="CSV delimiter")
    sheet_name: str | None = Field(None, description="Excel sheet name")
    uploaded_at: datetime = Field(..., description="Timestamp of upload")


class DatasetListItem(BaseModel):
    """Item in the dataset browser listing."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Dataset UUID")
    name: str = Field(..., description="Logical dataset name")
    description: str | None = Field(None, description="Optional description")
    version_count: int = Field(..., description="Total number of versions available")
    latest_version_number: int = Field(..., description="Highest version number")
    latest_upload_time: datetime = Field(..., description="Timestamp of latest upload")
    latest_row_count: int = Field(..., description="Row count of latest version")
    latest_column_count: int = Field(..., description="Column count of latest version")
    created_at: datetime = Field(..., description="Dataset creation timestamp")
    updated_at: datetime = Field(..., description="Dataset last modified timestamp")


class DatasetDetailResponse(BaseModel):
    """Complete dataset details with full version history."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Dataset UUID")
    name: str = Field(..., description="Logical dataset name")
    description: str | None = Field(None, description="Optional description")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    versions: list[DatasetVersionSummary] = Field(
        default_factory=list, description="Chronological list of all versions (newest first)"
    )


class UploadResponse(BaseModel):
    """
    Combined response for dataset upload & inspection.
    Includes Phase 3 persistent identifiers + Phase 2 in-memory preview.
    """

    # Persistent IDs (Phase 3)
    dataset_id: UUID | None = Field(None, description="Persisted Dataset UUID")
    version_id: UUID | None = Field(None, description="Persisted DatasetVersion UUID")
    version_number: int | None = Field(None, description="Assigned sequential version number")
    dataset_name: str = Field(default="", description="Logical dataset name")

    # File info
    original_filename: str = Field(..., description="Original uploaded filename")
    stored_filename: str = Field(..., description="Safe unique filename on disk")
    file_type: str = Field(..., description="File extension (csv, xlsx)")
    file_size_bytes: int = Field(..., description="File size in bytes")
    file_size_display: str = Field(..., description="Human-readable file size")

    # Parse info
    encoding: str | None = Field(None, description="Detected encoding for CSV files")
    delimiter: str | None = Field(None, description="Detected delimiter for CSV files")
    sheet_name: str | None = Field(None, description="Selected sheet name for Excel files")

    # Dataset info
    row_count: int = Field(..., description="Number of rows")
    column_count: int = Field(..., description="Number of columns")
    duplicate_row_count: int = Field(0, description="Number of duplicate rows")

    # Column details
    columns: list[ColumnMetadata] = Field(
        default_factory=list, description="Per-column metadata"
    )

    # Data preview
    sample_rows: list[dict] = Field(
        default_factory=list, description="First N rows as list of dicts"
    )

    # Timestamps
    uploaded_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Upload timestamp",
    )

    # Convenience column lookups
    column_names: list[str] = Field(
        default_factory=list, description="Ordered list of column names"
    )
    column_dtypes: dict[str, str] = Field(
        default_factory=dict, description="Mapping of column name to dtype"
    )
