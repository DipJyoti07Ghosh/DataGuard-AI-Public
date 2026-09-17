"""
DataGuard AI — Pydantic Schemas for Automated Data Profiling

Defines response structures for comprehensive dataset-level and
column-level statistical profiles, histograms, and correlations.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class HistogramBin(BaseModel):
    """A single bucket in a numerical distribution histogram."""

    bin_start: float = Field(..., description="Lower bound of the bin")
    bin_end: float = Field(..., description="Upper bound of the bin")
    count: int = Field(..., description="Frequency count of values within this bin")
    label: str = Field(..., description="Display label for charts (e.g. '10.5 - 20.0')")


class TopCategory(BaseModel):
    """A top recurring category value with frequency."""

    value: str = Field(..., description="Category label")
    count: int = Field(..., description="Frequency count")
    percentage: float = Field(..., description="Frequency percentage of non-null values")


class ColumnProfile(BaseModel):
    """
    Comprehensive statistical profile for an individual column.
    Adapts based on whether the column is numeric, categorical, datetime, or text.
    """

    name: str = Field(..., description="Column name")
    type_category: str = Field(
        ..., description="'numeric' | 'categorical' | 'datetime' | 'boolean' | 'text'"
    )
    dtype: str = Field(..., description="Underlying pandas/numpy dtype")
    count: int = Field(..., description="Total non-null rows")
    missing_count: int = Field(..., description="Number of null/missing values")
    missing_percentage: float = Field(..., description="Percentage of null values (0-100)")
    unique_count: int = Field(..., description="Number of distinct non-null values")
    unique_percentage: float = Field(..., description="Distinct values percentage")

    # Numerical metrics
    mean: float | None = Field(None, description="Arithmetic mean")
    std: float | None = Field(None, description="Standard deviation")
    min: float | None = Field(None, description="Minimum value")
    max: float | None = Field(None, description="Maximum value")
    q25: float | None = Field(None, description="25th percentile (1st quartile)")
    q50: float | None = Field(None, description="50th percentile (median)")
    q75: float | None = Field(None, description="75th percentile (3rd quartile)")
    q95: float | None = Field(None, description="95th percentile")
    skewness: float | None = Field(None, description="Distribution skewness coefficient")
    kurtosis: float | None = Field(None, description="Distribution kurtosis coefficient")
    zeros_count: int = Field(0, description="Number of zero values")
    negative_count: int = Field(0, description="Number of negative values")
    histogram: list[HistogramBin] = Field(
        default_factory=list, description="Distribution histogram bins"
    )

    # Categorical & Text metrics
    top_categories: list[TopCategory] = Field(
        default_factory=list, description="Top recurring values by frequency"
    )
    min_length: int | None = Field(None, description="Shortest text character length")
    max_length: int | None = Field(None, description="Longest text character length")
    avg_length: float | None = Field(None, description="Average text character length")

    # Datetime metrics
    min_date: str | None = Field(None, description="Earliest timestamp")
    max_date: str | None = Field(None, description="Latest timestamp")


class ProfilingResponse(BaseModel):
    """
    Complete profiling response for a dataset snapshot version.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ProfilingResult UUID")
    dataset_id: UUID = Field(..., description="Dataset UUID")
    dataset_version_id: UUID = Field(..., description="DatasetVersion UUID")
    version_number: int = Field(..., description="Sequential version number")
    dataset_name: str = Field(..., description="Logical dataset name")

    # Dataset overview metrics
    row_count: int = Field(..., description="Total rows")
    column_count: int = Field(..., description="Total columns")
    missing_cells: int = Field(..., description="Total missing cells across all rows/cols")
    missing_cells_percentage: float = Field(..., description="Percentage of cells missing")
    duplicate_rows: int = Field(..., description="Number of fully duplicate rows")
    duplicate_rows_percentage: float = Field(..., description="Percentage of rows duplicated")
    memory_size_bytes: int = Field(..., description="DataFrame memory size in bytes")
    memory_size_display: str = Field(..., description="Human-readable memory footprint")

    # Column type summary counts
    numeric_columns_count: int = Field(0, description="Number of numeric columns")
    categorical_columns_count: int = Field(0, description="Number of categorical columns")
    datetime_columns_count: int = Field(0, description="Number of datetime columns")
    boolean_columns_count: int = Field(0, description="Number of boolean columns")

    # Column profiles map: col_name -> ColumnProfile
    column_profiles: dict[str, ColumnProfile] = Field(
        default_factory=dict, description="Detailed profile per column"
    )

    # Correlation Matrix: colA -> colB -> correlation_coefficient (-1.0 to 1.0)
    correlations: dict[str, dict[str, float]] | None = Field(
        None, description="Pearson correlation matrix for numeric features"
    )

    generated_at: datetime = Field(..., description="Timestamp of profile generation")
