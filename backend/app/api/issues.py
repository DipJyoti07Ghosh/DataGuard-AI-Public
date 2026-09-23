"""
DataGuard AI — Phase 9 Dataset Health & Issue Prioritization API Endpoints

Provides REST endpoints to:
1. POST /{dataset_id}/versions/{version_id}/issues/analyze (Analyze & synthesize health & issues)
2. GET  /{dataset_id}/versions/{version_id}/issues (List issues with multi-attribute filtering)
3. GET  /{dataset_id}/versions/{version_id}/issues/summary (Holistic health & score breakdown)
4. GET  /{dataset_id}/versions/{version_id}/issues/{issue_id} (Detailed issue explanation & remediation)

Ownership enforced: only the dataset's owner can trigger or read health/issues data.
"""

import uuid
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth.dependencies import get_current_user, assert_dataset_owner
from app.auth.models import User
from app.database import get_db
from app.models.dataset import Dataset, DatasetVersion
from app.models.issues import DatasetHealthResult, DataQualityIssue
from app.schemas.issues import (
    DatasetHealthSummaryResponse,
    DataQualityIssueResponse,
    IssueListResponse,
    ColumnHealthMatrixItem,
)
from app.services.issue_service import analyze_and_save_dataset_health

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Phase 9 — Health & Prioritized Issues"])


def _get_version_or_404(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session,
) -> DatasetVersion:
    """Helper to fetch and validate dataset and version existence."""
    dataset = db.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    ).scalar_one_or_none()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID '{dataset_id}' not found",
        )

    version = db.execute(
        select(DatasetVersion).where(
            DatasetVersion.id == version_id,
            DatasetVersion.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DatasetVersion with ID '{version_id}' not found for dataset '{dataset_id}'",
        )
    return version


def _build_health_summary_response(
    health_res: DatasetHealthResult,
    version: DatasetVersion,
) -> DatasetHealthSummaryResponse:
    """Helper to format DatasetHealthSummaryResponse payload."""
    summary_data = health_res.summary or {}
    matrix_raw = summary_data.get("column_health_matrix", [])
    matrix_items = [ColumnHealthMatrixItem(**item) for item in matrix_raw]

    top_issues = [
        DataQualityIssueResponse.model_validate(issue)
        for issue in (health_res.issues or [])[:10]
    ]

    return DatasetHealthSummaryResponse(
        id=health_res.id,
        dataset_version_id=health_res.dataset_version_id,
        calculated_at=health_res.calculated_at,
        health_score=health_res.health_score,
        health_grade=health_res.health_grade,
        quality_health=health_res.quality_health,
        risk_health=health_res.risk_health,
        anomaly_health=health_res.anomaly_health,
        privacy_health=health_res.privacy_health,
        total_issues=health_res.total_issues,
        critical_issues=health_res.critical_issues,
        high_issues=health_res.high_issues,
        medium_issues=health_res.medium_issues,
        low_issues=health_res.low_issues,
        columns_affected_count=summary_data.get("columns_affected_count", 0),
        total_columns_evaluated=summary_data.get(
            "total_columns_evaluated", version.column_count or 0
        ),
        top_issues=top_issues,
        column_health_matrix=matrix_items,
        summary=summary_data,
    )


# ---------------------------------------------------------------------------
# 1. POST /issues/analyze — Trigger health synthesis
# ---------------------------------------------------------------------------
@router.post(
    "/{dataset_id}/versions/{version_id}/issues/analyze",
    response_model=DatasetHealthSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Dataset Health & Synthesize Prioritized Issues",
)
def analyze_issues_endpoint(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    force_recompute: bool = Query(
        False, description="Force re-synthesis even if cached result exists"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Synthesizes upstream Quality, PII, Risk, and Anomaly results to compute
    Dataset Health (0-100), health grade, and prioritized remediation issues.
    """
    assert_dataset_owner(db, dataset_id, current_user)

    version = _get_version_or_404(dataset_id, version_id, db)
    health_result = analyze_and_save_dataset_health(
        version, db, force=force_recompute
    )
    return _build_health_summary_response(health_result, version)


# ---------------------------------------------------------------------------
# 2. GET /issues/summary — Cached holistic health
# ---------------------------------------------------------------------------
@router.get(
    "/{dataset_id}/versions/{version_id}/issues/summary",
    response_model=DatasetHealthSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Holistic Dataset Health & Issues Summary",
)
def get_health_summary_endpoint(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves the cached holistic Dataset Health summary, 4-way breakdown,
    and column health matrix. Auto-computes if not yet analyzed.
    """
    assert_dataset_owner(db, dataset_id, current_user)

    version = _get_version_or_404(dataset_id, version_id, db)
    health_result = analyze_and_save_dataset_health(version, db, force=False)
    return _build_health_summary_response(health_result, version)


# ---------------------------------------------------------------------------
# 3. GET /issues — Filtered list of prioritized issues
# ---------------------------------------------------------------------------
@router.get(
    "/{dataset_id}/versions/{version_id}/issues",
    response_model=IssueListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Prioritized Data Quality Issues with Filters",
)
def list_issues_endpoint(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    severity: Optional[str] = Query(
        None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW"
    ),
    source: Optional[str] = Query(
        None, description="Filter by source: QUALITY, PII, RISK, ANOMALY, PROFILE"
    ),
    issue_type: Optional[str] = Query(
        None, description="Filter by issue type: MISSING_VALUES, DUPLICATES, ANOMALY, PII_EXPOSURE, etc."
    ),
    column: Optional[str] = Query(
        None, description="Filter by column name"
    ),
    min_priority: Optional[float] = Query(
        None, description="Filter by minimum priority score (0.0 - 100.0)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns prioritized issues sorted by priority_score descending with optional filtering.
    """
    assert_dataset_owner(db, dataset_id, current_user)

    version = _get_version_or_404(dataset_id, version_id, db)
    health_result = analyze_and_save_dataset_health(version, db, force=False)

    issues = list(health_result.issues or [])

    # Apply in-memory filters
    if severity:
        issues = [i for i in issues if i.severity.upper() == severity.upper()]
    if source:
        issues = [i for i in issues if i.source.upper() == source.upper()]
    if issue_type:
        issues = [i for i in issues if i.issue_type.upper() == issue_type.upper()]
    if column:
        issues = [i for i in issues if i.column_name and i.column_name.lower() == column.lower()]
    if min_priority is not None:
        issues = [i for i in issues if i.priority_score >= min_priority]

    return IssueListResponse(
        dataset_version_id=version.id,
        health_score=health_result.health_score,
        health_grade=health_result.health_grade,
        total_count=len(issues),
        issues=[DataQualityIssueResponse.model_validate(i) for i in issues],
    )


# ---------------------------------------------------------------------------
# 4. GET /issues/{issue_id} — Detailed single issue
# ---------------------------------------------------------------------------
@router.get(
    "/{dataset_id}/versions/{version_id}/issues/{issue_id}",
    response_model=DataQualityIssueResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Detailed Issue Explanation & Remediation Suggestion",
)
def get_issue_detail_endpoint(
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    issue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves complete explanation, score components, and safe remediation
    recommendations for a single issue.
    """
    assert_dataset_owner(db, dataset_id, current_user)

    _get_version_or_404(dataset_id, version_id, db)

    issue = db.execute(
        select(DataQualityIssue).where(
            DataQualityIssue.id == issue_id,
            DataQualityIssue.dataset_version_id == version_id,
        )
    ).scalar_one_or_none()

    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID '{issue_id}' not found for version '{version_id}'",
        )

    return DataQualityIssueResponse.model_validate(issue)