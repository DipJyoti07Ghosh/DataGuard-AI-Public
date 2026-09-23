"""
DataGuard AI — Phase 13 Dashboard API Endpoints

Read-only presentation API aggregating stored analytical results from Phases 4-10.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import get_dataset_version_dashboard

router = APIRouter(tags=["Dashboard"])


@router.get(
    "/{dataset_id}/versions/{version_id}/dashboard",
    response_model=DashboardResponse,
    summary="Get aggregated dashboard metrics for a specific dataset version",
    description=(
        "Returns unified, read-only dashboard presentation data synthesizing Phase 4-10 "
        "stored results including health overview, data quality status, column risk, "
        "privacy exposure, anomalies, prioritized issues, missingness, and drift metrics."
    ),
)
def get_version_dashboard(
    dataset_id: uuid.UUID = Path(..., description="Unique dataset UUID"),
    version_id: uuid.UUID = Path(..., description="Unique dataset version snapshot UUID"),
    db: Session = Depends(get_db),
):
    res = get_dataset_version_dashboard(dataset_id=dataset_id, version_id=version_id, db=db)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} or version {version_id} not found",
        )
    return res


@router.get(
    "/{dataset_id}/dashboard",
    response_model=DashboardResponse,
    summary="Get aggregated dashboard metrics for the latest dataset version",
    description="Returns unified, read-only dashboard presentation data for the latest version of the dataset.",
)
def get_latest_dashboard(
    dataset_id: uuid.UUID = Path(..., description="Unique dataset UUID"),
    db: Session = Depends(get_db),
):
    res = get_dataset_version_dashboard(dataset_id=dataset_id, version_id=None, db=db)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found or has no versions",
        )
    return res
