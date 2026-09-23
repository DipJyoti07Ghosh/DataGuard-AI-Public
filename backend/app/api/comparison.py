"""
DataGuard AI — Phase 10 Version Comparison & Drift Detection API Endpoints

Provides REST endpoints to:
1. POST /{dataset_id}/compare (Compare two versions and persist drift analysis)
2. GET  /{dataset_id}/comparisons/{comparison_id} (Retrieve detailed comparison and column drift)
3. GET  /{dataset_id}/comparisons (List past version comparisons)
4. GET  /{dataset_id}/comparisons/{comparison_id}/columns/{column_name} (Single column deep dive)
"""

import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.database import get_db
from app.models.dataset import Dataset, DatasetVersion
from app.models.comparison import DatasetComparison, ColumnDriftResult
from app.auth.dependencies import get_current_user, assert_dataset_owner
from app.auth.models import User
from app.schemas.comparison import (
    CompareVersionsRequest,
    DatasetComparisonResponse,
    ComparisonListItemResponse,
    ColumnDriftResponse,
    VersionBrief,
)
from app.services.comparison_service import compare_dataset_versions

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Phase 10 — Version Comparison & Drift Detection"])


def _format_comparison_response(comp: DatasetComparison, db: Session) -> DatasetComparisonResponse:
    """Helper to format DatasetComparison database record into Pydantic response."""
    dataset = db.execute(select(Dataset).where(Dataset.id == comp.dataset_id)).scalar_one_or_none()
    baseline = db.execute(select(DatasetVersion).where(DatasetVersion.id == comp.baseline_version_id)).scalar_one_or_none()
    current = db.execute(select(DatasetVersion).where(DatasetVersion.id == comp.current_version_id)).scalar_one_or_none()

    subsystem_deltas = {
        "quality": comp.quality_drift_summary or {},
        "risk": comp.risk_drift_summary or {},
        "anomaly": comp.anomaly_drift_summary or {},
        "privacy": comp.privacy_drift_summary or {},
        "quality_drift": comp.quality_drift_summary or {},
        "risk_drift": comp.risk_drift_summary or {},
        "anomaly_drift": comp.anomaly_drift_summary or {},
        "privacy_drift": comp.privacy_drift_summary or {},
    }

    columns_res = [
        ColumnDriftResponse(
            id=cdr.id,
            column_name=cdr.column_name,
            schema_status=cdr.schema_status,
            baseline_type=cdr.baseline_type,
            current_type=cdr.current_type,
            type_category=cdr.type_category,
            drift_status=cdr.drift_status,
            missingness=cdr.missingness_comparison or {},
            uniqueness=cdr.uniqueness_comparison or {},
            statistical_drift=cdr.statistical_comparison or {},
            quality_impact=cdr.quality_impact,
            risk_impact=cdr.risk_impact,
            anomaly_impact=cdr.anomaly_impact,
            privacy_impact=cdr.privacy_impact,
            drift_evidence=cdr.drift_evidence or [],
        )
        for cdr in (comp.column_drifts or [])
    ]

    return DatasetComparisonResponse(
        id=comp.id,
        dataset_id=comp.dataset_id,
        dataset_name=dataset.name if dataset else "Dataset",
        baseline_version=VersionBrief(
            id=baseline.id,
            version_number=baseline.version_number,
            row_count=baseline.row_count,
            column_count=baseline.column_count,
            created_at=getattr(baseline, "uploaded_at", getattr(baseline, "created_at", None)),
            uploaded_at=getattr(baseline, "uploaded_at", None),
        ) if baseline else VersionBrief(id=comp.baseline_version_id, version_number=1),
        current_version=VersionBrief(
            id=current.id,
            version_number=current.version_number,
            row_count=current.row_count,
            column_count=current.column_count,
            created_at=getattr(current, "uploaded_at", getattr(current, "created_at", None)),
            uploaded_at=getattr(current, "uploaded_at", None),
        ) if current else VersionBrief(id=comp.current_version_id, version_number=2),
        status=comp.status,
        overall_drift_status=comp.overall_drift_status,
        drift_drivers=comp.drift_drivers or [],
        schema_summary=comp.schema_drift_summary or {},
        numerical_summary=comp.numerical_drift_summary or {},
        categorical_summary=comp.categorical_drift_summary or {},
        missingness_summary=comp.missingness_drift_summary or {},
        uniqueness_summary=comp.uniqueness_drift_summary or {},
        subsystem_deltas=subsystem_deltas,
        columns=columns_res,
        created_at=comp.created_at,
        compared_at=comp.compared_at,
    )


@router.post(
    "/{dataset_id}/compare",
    response_model=DatasetComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare two snapshot versions of a dataset",
)
def compare_versions_endpoint(
    dataset_id: uuid.UUID,
    payload: CompareVersionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compare two snapshot versions (baseline vs current) of the same logical dataset.
    Detects schema breaks, missingness shifts, numerical KS-test distribution drift,
    categorical PSI drift, and cross-subsystem quality/risk/anomaly/PII impact.
    """
    try:
        assert_dataset_owner(db, dataset_id, current_user)
        comp = compare_dataset_versions(
            dataset_id=dataset_id,
            baseline_version_id=payload.baseline_version_id,
            current_version_id=payload.current_version_id,
            db=db,
            force_recompute=payload.force_recompute or False,
        )
        return _format_comparison_response(comp, db)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to execute version comparison for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Version comparison failed: {str(e)}",
        )


@router.get(
    "/{dataset_id}/comparisons/{comparison_id}",
    response_model=DatasetComparisonResponse,
    summary="Get detailed version comparison result",
)
def get_comparison_endpoint(
    dataset_id: uuid.UUID,
    comparison_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve an existing version comparison report with all column-level drift evidence."""
    assert_dataset_owner(db, dataset_id, current_user)
    comp = db.execute(
        select(DatasetComparison).where(
            DatasetComparison.id == comparison_id,
            DatasetComparison.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()

    if not comp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison with ID '{comparison_id}' not found for dataset '{dataset_id}'",
        )

    return _format_comparison_response(comp, db)


@router.get(
    "/{dataset_id}/comparisons",
    response_model=List[ComparisonListItemResponse],
    summary="List past version comparisons for a dataset",
)
def list_comparisons_endpoint(
    dataset_id: uuid.UUID,
    baseline_version_id: Optional[uuid.UUID] = Query(None),
    current_version_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List past version comparisons for a dataset with optional version filters."""
    assert_dataset_owner(db, dataset_id, current_user)
    query = select(DatasetComparison).where(DatasetComparison.dataset_id == dataset_id)

    if baseline_version_id:
        query = query.where(DatasetComparison.baseline_version_id == baseline_version_id)
    if current_version_id:
        query = query.where(DatasetComparison.current_version_id == current_version_id)

    query = query.order_by(desc(DatasetComparison.compared_at))
    comparisons = db.execute(query).scalars().all()

    results = []
    for c in comparisons:
        base_v = db.execute(select(DatasetVersion).where(DatasetVersion.id == c.baseline_version_id)).scalar_one_or_none()
        curr_v = db.execute(select(DatasetVersion).where(DatasetVersion.id == c.current_version_id)).scalar_one_or_none()
        schema_sum = c.schema_drift_summary or {}
        results.append(
            ComparisonListItemResponse(
                id=c.id,
                dataset_id=c.dataset_id,
                baseline_version_id=c.baseline_version_id,
                baseline_version_number=base_v.version_number if base_v else 1,
                current_version_id=c.current_version_id,
                current_version_number=curr_v.version_number if curr_v else 2,
                status=c.status,
                overall_drift_status=c.overall_drift_status,
                total_schema_changes=schema_sum.get("total_changes", 0),
                compared_at=c.compared_at,
            )
        )
    return results


@router.get(
    "/{dataset_id}/comparisons/{comparison_id}/columns/{column_name}",
    response_model=ColumnDriftResponse,
    summary="Get single column drift deep dive",
)
def get_column_drift_endpoint(
    dataset_id: uuid.UUID,
    comparison_id: uuid.UUID,
    column_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve detailed distribution comparison, test statistics, and drift evidence for a single column."""
    assert_dataset_owner(db, dataset_id, current_user)
    comp = db.execute(
        select(DatasetComparison).where(
            DatasetComparison.id == comparison_id,
            DatasetComparison.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()

    if not comp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison with ID '{comparison_id}' not found for dataset '{dataset_id}'",
        )

    cdr = db.execute(
        select(ColumnDriftResult).where(
            ColumnDriftResult.comparison_id == comparison_id,
            ColumnDriftResult.column_name == column_name,
        )
    ).scalar_one_or_none()

    if not cdr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Column '{column_name}' not found in comparison '{comparison_id}'",
        )

    return ColumnDriftResponse(
        id=cdr.id,
        column_name=cdr.column_name,
        schema_status=cdr.schema_status,
        baseline_type=cdr.baseline_type,
        current_type=cdr.current_type,
        type_category=cdr.type_category,
        drift_status=cdr.drift_status,
        missingness=cdr.missingness_comparison or {},
        uniqueness=cdr.uniqueness_comparison or {},
        statistical_drift=cdr.statistical_comparison or {},
        quality_impact=cdr.quality_impact,
        risk_impact=cdr.risk_impact,
        anomaly_impact=cdr.anomaly_impact,
        privacy_impact=cdr.privacy_impact,
        drift_evidence=cdr.drift_evidence or [],
    )
