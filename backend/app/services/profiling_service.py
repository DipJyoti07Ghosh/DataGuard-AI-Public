"""
DataGuard AI — Automated Data Profiling Engine

Computes comprehensive dataset-level and column-level statistical profiles:
- Quantiles (p25, p50, p75, p95), Mean, Std, Skewness, Kurtosis
- Frequency distribution histograms
- Top category breakdowns & text cardinality analysis
- Pearson correlation matrix across numeric features
- Persists profiling results into PostgreSQL attached to DatasetVersion
"""

import math
import logging
from pathlib import Path
from uuid import UUID
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.dataset import Dataset, DatasetVersion
from app.models.profiling import ProfilingResult
from app.schemas.profiling import (
    HistogramBin,
    TopCategory,
    ColumnProfile,
    ProfilingResponse,
)
from app.services.ingestion import parse_csv, parse_excel, _format_bytes

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core DataFrame Profiler
# ---------------------------------------------------------------------------
def profile_dataframe(df: pd.DataFrame) -> dict:
    """
    Perform deep statistical profiling on a pandas DataFrame.
    Returns a dictionary matching the ProfilingResult database columns.
    """
    row_count = int(len(df))
    column_count = int(len(df.columns))
    total_cells = row_count * column_count if column_count > 0 else 1

    missing_cells = int(df.isna().sum().sum())
    missing_pct = round((missing_cells / total_cells * 100) if total_cells > 0 else 0, 2)

    duplicate_rows = int(df.duplicated().sum()) if row_count > 0 else 0
    duplicate_pct = round((duplicate_rows / row_count * 100) if row_count > 0 else 0, 2)

    try:
        memory_size = int(df.memory_usage(deep=True).sum())
    except Exception:
        memory_size = 0

    num_cols_count = 0
    cat_cols_count = 0
    dt_cols_count = 0
    bool_cols_count = 0

    column_profiles = {}

    for col in df.columns:
        series = df[col]
        col_name = str(col)
        col_profile = _profile_single_column(series, col_name, row_count)
        column_profiles[col_name] = col_profile.model_dump()

        cat = col_profile.type_category
        if cat == "numeric":
            num_cols_count += 1
        elif cat == "datetime":
            dt_cols_count += 1
        elif cat == "boolean":
            bool_cols_count += 1
        else:
            cat_cols_count += 1

    # Correlation Matrix across numeric columns
    correlations = _calculate_correlations(df)

    return {
        "row_count": row_count,
        "column_count": column_count,
        "missing_cells": missing_cells,
        "missing_cells_percentage": missing_pct,
        "duplicate_rows": duplicate_rows,
        "duplicate_rows_percentage": duplicate_pct,
        "memory_size_bytes": memory_size,
        "numeric_columns_count": num_cols_count,
        "categorical_columns_count": cat_cols_count,
        "datetime_columns_count": dt_cols_count,
        "boolean_columns_count": bool_cols_count,
        "column_profiles": column_profiles,
        "correlations": correlations,
    }


def _profile_single_column(series: pd.Series, col_name: str, total_rows: int) -> ColumnProfile:
    """Profile an individual pandas Series based on its inferred data type."""
    non_null = series.dropna()
    count = int(len(non_null))
    missing_count = int(series.isna().sum())
    missing_pct = round((missing_count / total_rows * 100) if total_rows > 0 else 0, 2)
    unique_count = int(non_null.nunique())
    unique_pct = round((unique_count / count * 100) if count > 0 else 0, 2)

    dtype_str = str(series.dtype)

    # 1. Boolean check
    if pd.api.types.is_bool_dtype(series):
        top_cats = _get_top_categories(non_null, count)
        return ColumnProfile(
            name=col_name,
            type_category="boolean",
            dtype=dtype_str,
            count=count,
            missing_count=missing_count,
            missing_percentage=missing_pct,
            unique_count=unique_count,
            unique_percentage=unique_pct,
            top_categories=top_cats,
        )

    # 2. Numeric check (integer, float)
    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return _profile_numeric_column(
            series, non_null, col_name, dtype_str, count, missing_count, missing_pct, unique_count, unique_pct
        )

    # 3. Datetime check
    if pd.api.types.is_datetime64_any_dtype(series):
        min_d = non_null.min().isoformat() if count > 0 else None
        max_d = non_null.max().isoformat() if count > 0 else None
        return ColumnProfile(
            name=col_name,
            type_category="datetime",
            dtype=dtype_str,
            count=count,
            missing_count=missing_count,
            missing_percentage=missing_pct,
            unique_count=unique_count,
            unique_percentage=unique_pct,
            min_date=min_d,
            max_date=max_d,
        )

    # 4. Text / Categorical fallback
    top_cats = _get_top_categories(non_null, count)
    
    # Calculate string lengths
    str_series = non_null.astype(str)
    lengths = str_series.str.len()
    min_len = int(lengths.min()) if count > 0 else None
    max_len = int(lengths.max()) if count > 0 else None
    avg_len = round(float(lengths.mean()), 1) if count > 0 else None

    # Categorical if low unique count or explicit category
    is_cat = unique_count <= 50 or (unique_count / count < 0.15 if count > 0 else True)

    return ColumnProfile(
        name=col_name,
        type_category="categorical" if is_cat else "text",
        dtype=dtype_str,
        count=count,
        missing_count=missing_count,
        missing_percentage=missing_pct,
        unique_count=unique_count,
        unique_percentage=unique_pct,
        top_categories=top_cats,
        min_length=min_len,
        max_length=max_len,
        avg_length=avg_len,
    )


def _profile_numeric_column(
    series: pd.Series,
    non_null: pd.Series,
    col_name: str,
    dtype_str: str,
    count: int,
    missing_count: int,
    missing_pct: float,
    unique_count: int,
    unique_pct: float,
) -> ColumnProfile:
    """Compute detailed quantiles, moments, and histogram for numeric column."""
    if count == 0:
        return ColumnProfile(
            name=col_name,
            type_category="numeric",
            dtype=dtype_str,
            count=0,
            missing_count=missing_count,
            missing_percentage=missing_pct,
            unique_count=0,
            unique_percentage=0.0,
        )

    clean_vals = pd.to_numeric(non_null, errors="coerce").dropna()
    c_count = len(clean_vals)

    if c_count == 0:
        return ColumnProfile(
            name=col_name,
            type_category="numeric",
            dtype=dtype_str,
            count=count,
            missing_count=missing_count,
            missing_percentage=missing_pct,
            unique_count=unique_count,
            unique_percentage=unique_pct,
        )

    mean_val = _clean_float(clean_vals.mean())
    std_val = _clean_float(clean_vals.std()) if c_count > 1 else 0.0
    min_val = _clean_float(clean_vals.min())
    max_val = _clean_float(clean_vals.max())

    q25 = _clean_float(clean_vals.quantile(0.25))
    q50 = _clean_float(clean_vals.quantile(0.50))
    q75 = _clean_float(clean_vals.quantile(0.75))
    q95 = _clean_float(clean_vals.quantile(0.95))

    # Skewness & Kurtosis (require > 2 values and non-zero variance)
    skew_val = _clean_float(clean_vals.skew()) if c_count > 2 and (std_val or 0) > 0 else None
    kurt_val = _clean_float(clean_vals.kurt()) if c_count > 3 and (std_val or 0) > 0 else None

    zeros_count = int((clean_vals == 0).sum())
    neg_count = int((clean_vals < 0).sum())

    # Build 10-bin histogram
    histogram = _build_histogram(clean_vals)

    return ColumnProfile(
        name=col_name,
        type_category="numeric",
        dtype=dtype_str,
        count=count,
        missing_count=missing_count,
        missing_percentage=missing_pct,
        unique_count=unique_count,
        unique_percentage=unique_pct,
        mean=mean_val,
        std=std_val,
        min=min_val,
        max=max_val,
        q25=q25,
        q50=q50,
        q75=q75,
        q95=q95,
        skewness=skew_val,
        kurtosis=kurt_val,
        zeros_count=zeros_count,
        negative_count=neg_count,
        histogram=histogram,
    )


def _build_histogram(clean_vals: pd.Series, num_bins: int = 10) -> list[HistogramBin]:
    """Generate evenly spaced histogram bins and counts."""
    if len(clean_vals) == 0:
        return []

    min_v = clean_vals.min()
    max_v = clean_vals.max()

    if min_v == max_v:
        return [
            HistogramBin(
                bin_start=float(min_v),
                bin_end=float(max_v),
                count=len(clean_vals),
                label=f"{min_v:.1f}",
            )
        ]

    counts, bin_edges = np.histogram(clean_vals, bins=num_bins)
    bins = []
    for i in range(len(counts)):
        b_start = round(float(bin_edges[i]), 2)
        b_end = round(float(bin_edges[i + 1]), 2)
        bins.append(
            HistogramBin(
                bin_start=b_start,
                bin_end=b_end,
                count=int(counts[i]),
                label=f"{b_start} - {b_end}",
            )
        )
    return bins


def _get_top_categories(non_null: pd.Series, count: int, top_n: int = 10) -> list[TopCategory]:
    """Extract top N recurring categorical values."""
    if count == 0:
        return []

    val_counts = non_null.value_counts().head(top_n)
    result = []
    for val, freq in val_counts.items():
        pct = round((freq / count * 100), 2)
        result.append(TopCategory(value=str(val)[:50], count=int(freq), percentage=pct))
    return result


def _calculate_correlations(df: pd.DataFrame) -> dict[str, dict[str, float]] | None:
    """Compute Pearson correlation matrix for numeric columns."""
    num_df = df.select_dtypes(include=[np.number])
    if len(num_df.columns) < 2 or len(num_df) < 2:
        return None

    try:
        corr_matrix = num_df.corr(method="pearson")
        result = {}
        for colA in corr_matrix.columns:
            result[str(colA)] = {}
            for colB in corr_matrix.columns:
                val = corr_matrix.loc[colA, colB]
                result[str(colA)][str(colB)] = round(float(val), 3) if not math.isnan(val) else 0.0
        return result
    except Exception as e:
        logger.warning(f"Failed to calculate correlation matrix: {e}")
        return None


def _clean_float(val) -> float | None:
    """Convert numpy/pandas scalar to JSON-safe float."""
    if val is None or pd.isna(val) or math.isnan(val) or math.isinf(val):
        return None
    return round(float(val), 3)


# ---------------------------------------------------------------------------
# Database Ingestion & Persistence of Profiles
# ---------------------------------------------------------------------------
def generate_profile_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = False,
) -> ProfilingResponse:
    """
    Generate or fetch a cached profiling result for a specific DatasetVersion.
    """
    # 1. Fetch Dataset & Version entities
    stmt = (
        select(DatasetVersion)
        .join(Dataset)
        .where(DatasetVersion.id == version_id, Dataset.id == dataset_id)
    )
    version = db.scalar(stmt)
    if not version:
        raise ValueError(f"DatasetVersion '{version_id}' not found under dataset '{dataset_id}'.")

    # 2. Check if profile already exists in DB
    existing_profile = db.scalar(
        select(ProfilingResult).where(ProfilingResult.dataset_version_id == version_id)
    )

    if existing_profile and not force_recompute:
        logger.info(f"Returning cached profiling result for version {version.version_number}")
        return _to_profiling_response(existing_profile, version)

    # 3. Read uploaded file from disk inside backend/uploads/
    upload_dir = settings.upload_path
    file_path = upload_dir / version.stored_filename
    if not file_path.exists():
        raise FileNotFoundError(
            f"Stored file '{version.stored_filename}' for version V{version.version_number} not found on disk."
        )

    file_content = file_path.read_bytes()
    if version.file_type == "csv":
        df, _, _ = parse_csv(file_content)
    elif version.file_type == "xlsx":
        df, _ = parse_excel(file_content)
    else:
        raise ValueError(f"Unsupported file type '{version.file_type}' for profiling.")

    # 4. Profile DataFrame
    logger.info(f"Computing automated profile for '{version.dataset.name}' V{version.version_number}...")
    profile_data = profile_dataframe(df)

    # 5. Persist to PostgreSQL
    if existing_profile:
        for k, v in profile_data.items():
            setattr(existing_profile, k, v)
        profile_entity = existing_profile
    else:
        profile_entity = ProfilingResult(
            dataset_version_id=version.id,
            **profile_data,
        )
        db.add(profile_entity)

    db.commit()
    db.refresh(profile_entity)
    logger.info(f"Saved ProfilingResult (id={profile_entity.id}) for DatasetVersion V{version.version_number}")

    return _to_profiling_response(profile_entity, version)


def get_profile_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
) -> ProfilingResponse | None:
    """
    Retrieve existing profiling result if it has been generated.
    """
    stmt = (
        select(ProfilingResult)
        .join(DatasetVersion)
        .join(Dataset)
        .where(
            DatasetVersion.id == version_id,
            Dataset.id == dataset_id,
        )
    )
    profile = db.scalar(stmt)
    if not profile:
        return None

    return _to_profiling_response(profile, profile.version)


def _to_profiling_response(
    profile: ProfilingResult, version: DatasetVersion
) -> ProfilingResponse:
    """Convert database ProfilingResult and DatasetVersion to Pydantic ProfilingResponse."""
    return ProfilingResponse(
        id=profile.id,
        dataset_id=version.dataset_id,
        dataset_version_id=profile.dataset_version_id,
        version_number=version.version_number,
        dataset_name=version.dataset.name,
        row_count=profile.row_count,
        column_count=profile.column_count,
        missing_cells=profile.missing_cells,
        missing_cells_percentage=profile.missing_cells_percentage,
        duplicate_rows=profile.duplicate_rows,
        duplicate_rows_percentage=profile.duplicate_rows_percentage,
        memory_size_bytes=profile.memory_size_bytes,
        memory_size_display=_format_bytes(profile.memory_size_bytes),
        numeric_columns_count=profile.numeric_columns_count,
        categorical_columns_count=profile.categorical_columns_count,
        datetime_columns_count=profile.datetime_columns_count,
        boolean_columns_count=profile.boolean_columns_count,
        column_profiles=profile.column_profiles,
        correlations=profile.correlations,
        generated_at=profile.generated_at,
    )
