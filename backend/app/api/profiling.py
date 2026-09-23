"""
DataGuard AI — Automated Data Profiling API Router

Endpoints to trigger statistical profiling and retrieve detailed
column profiles, distribution histograms, and feature correlation matrices.

Ownership enforced: only the dataset's owner can trigger or read profiling.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, assert_dataset_owner
from app.auth.models import User
from app.database import get_db
from app.schemas.profiling import ProfilingResponse
from app.services.profiling_service import (
    generate_profile_for_version,
    get_profile_for_version,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["Profiling"])


@router.post(
    "/{dataset_id}/versions/{version_id}/profile",
    response_model=ProfilingResponse,
)
def run_dataset_profiling(
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = Query(
        False, description="Force recomputation of profiling stats even if cached"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate comprehensive statistical profile for a specific dataset version snapshot.
    Computes quantiles, moments, histograms, top categories, and correlations.
    """
    try:
        assert_dataset_owner(db, dataset_id, current_user)
        profile = generate_profile_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
            force_recompute=force_recompute,
        )
        return profile
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload file missing on disk: {e}",
        )
    except Exception as e:
        logger.error(f"Profiling failed for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate profiling report: {str(e)[:200]}",
        )


@router.get(
    "/{dataset_id}/versions/{version_id}/profile",
    response_model=ProfilingResponse,
)
def get_dataset_profile(
    dataset_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve existing statistical profile for a specific dataset version snapshot.
    """
    try:
        assert_dataset_owner(db, dataset_id, current_user)
        profile = get_profile_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
        )
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profiling report has not been generated for this version yet. Call POST to generate.",
            )
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile for version {version_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profiling report.",
        )