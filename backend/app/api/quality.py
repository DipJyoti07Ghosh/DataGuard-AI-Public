"""
DataGuard AI — Data Quality API Endpoints

Provides REST endpoints to trigger automated quality validation,
retrieve dataset version quality scorecards, and inspect rule-level failure details.

Ownership enforced.
"""

from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, assert_dataset_owner
from app.auth.models import User
from app.database import get_db
from app.schemas.quality import QualityResponse, ExpectationRuleResult
from app.services.quality_service import (
    generate_quality_for_version,
    get_quality_for_version,
)

logger = logging.getLogger("dataguard.api.quality")

router = APIRouter(prefix="", tags=["Data Quality"])


@router.post(
    "/{dataset_id}/versions/{version_id}/quality",
    response_model=QualityResponse,
)
def compute_dataset_quality(
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        assert_dataset_owner(db, dataset_id, current_user)
        return generate_quality_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
            force_recompute=force_recompute,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Underlying dataset file could not be found: {e}",
        )
    except Exception as e:
        logger.error(f"Error computing quality for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute quality validation: {str(e)}",
        )


@router.get(
    "/{dataset_id}/versions/{version_id}/quality",
    response_model=QualityResponse,
)
def get_dataset_quality(
    dataset_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        assert_dataset_owner(db, dataset_id, current_user)
        return get_quality_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Underlying dataset file could not be found: {e}",
        )
    except Exception as e:
        logger.error(f"Error retrieving quality for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve quality validation: {str(e)}",
        )


@router.get(
    "/{dataset_id}/versions/{version_id}/quality/details",
    response_model=list[ExpectationRuleResult],
)
def get_dataset_quality_details(
    dataset_id: UUID,
    version_id: UUID,
    status_filter: str | None = Query(None),
    category_filter: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        assert_dataset_owner(db, dataset_id, current_user)
        quality_resp = get_quality_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
        )
        rules = quality_resp.failed_rules + quality_resp.passed_rules

        if status_filter:
            sf = status_filter.lower()
            if sf == "failed":
                rules = [r for r in rules if not r.success]
            elif sf == "passed":
                rules = [r for r in rules if r.success]

        if category_filter:
            cf = category_filter.lower()
            rules = [r for r in rules if r.category.lower() == cf]

        return rules
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving quality details for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve quality details: {str(e)}",
        )