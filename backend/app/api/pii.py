"""
DataGuard AI — PII & Sensitive Data Detection API Endpoints

Provides REST endpoints to:
1. Trigger PII detection scans for DatasetVersions
2. Retrieve cached PII scan summaries and risk metrics
3. Query detailed findings with column, risk, and entity filters
"""

import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.dataset import Dataset, DatasetVersion
from app.models.pii import PIIScanResult, PIIFinding
from app.schemas.pii import (
    PIIScanResultResponse,
    PIIScanSummaryResponse,
    PIIDetailsResponse,
    PIIFindingResponse,
)
from app.services.pii_service import (
    generate_pii_for_version,
    get_pii_for_version,
)

logger = logging.getLogger("dataguard.api.pii")

router = APIRouter(prefix="", tags=["PII Detection"])


@router.post(
    "/{dataset_id}/versions/{version_id}/pii/scan",
    response_model=PIIScanResultResponse,
    summary="Run automated PII detection scan for a DatasetVersion",
    description=(
        "Inspects column names and sampled values using Microsoft Presidio Analyzer. "
        "Detects emails, phone numbers, IP addresses, credit cards, SSNs, personal names, "
        "and locations. Masks all sensitive values before database storage and returns sanitized findings."
    ),
)
def run_pii_scan(
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = Query(
        False,
        description="If True, forces re-analysis even if a cached PII scan already exists",
    ),
    db: Session = Depends(get_db),
):
    """Execute PII scan and persist findings."""
    try:
        scan_result = generate_pii_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
            force_recompute=force_recompute,
        )
        return scan_result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Underlying dataset file could not be found: {e}",
        )
    except Exception as e:
        logger.error(f"Error scanning PII for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute PII scan: {str(e)}",
        )


@router.get(
    "/{dataset_id}/versions/{version_id}/pii",
    response_model=PIIScanResultResponse,
    summary="Get cached PII scan result for a DatasetVersion",
    description="Retrieves the latest PII scan result. If not yet scanned, automatically triggers the initial scan.",
)
def get_pii_scan(
    dataset_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
):
    """Retrieve PII scan result for a dataset version."""
    try:
        # Check dataset and version exist first
        stmt = (
            select(DatasetVersion)
            .join(Dataset)
            .where(
                DatasetVersion.id == version_id,
                Dataset.id == dataset_id,
            )
        )
        version = db.scalar(stmt)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DatasetVersion with id='{version_id}' not found for dataset='{dataset_id}'.",
            )

        scan_result = get_pii_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
        )
        if not scan_result:
            # Auto-run initial scan if none exists
            scan_result = generate_pii_for_version(
                db=db,
                dataset_id=dataset_id,
                version_id=version_id,
                force_recompute=False,
            )
        return scan_result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Underlying dataset file could not be found: {e}",
        )
    except Exception as e:
        logger.error(f"Error retrieving PII for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve PII scan: {str(e)}",
        )


@router.get(
    "/{dataset_id}/versions/{version_id}/pii/details",
    response_model=PIIDetailsResponse,
    summary="Get detailed PII findings with optional filters",
    description="Returns individual PII findings with filtering by entity_type, risk_level, and column_name.",
)
def get_pii_details(
    dataset_id: UUID,
    version_id: UUID,
    entity_type: Optional[str] = Query(None, description="Filter by Presidio entity type (e.g., EMAIL_ADDRESS)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level ('HIGH', 'MEDIUM', 'LOW')"),
    column_name: Optional[str] = Query(None, description="Filter by column name"),
    db: Session = Depends(get_db),
):
    """Retrieve detailed PII findings with query filters."""
    try:
        # Check dataset and version exist
        stmt_v = (
            select(DatasetVersion)
            .join(Dataset)
            .where(
                DatasetVersion.id == version_id,
                Dataset.id == dataset_id,
            )
        )
        version = db.scalar(stmt_v)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DatasetVersion with id='{version_id}' not found for dataset='{dataset_id}'.",
            )

        scan_result = get_pii_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
        )
        if not scan_result:
            scan_result = generate_pii_for_version(
                db=db,
                dataset_id=dataset_id,
                version_id=version_id,
                force_recompute=False,
            )

        # Apply database query filters
        stmt_findings = select(PIIFinding).where(PIIFinding.scan_id == scan_result.id)

        filters_applied = {}
        if entity_type:
            stmt_findings = stmt_findings.where(PIIFinding.entity_type == entity_type.upper())
            filters_applied["entity_type"] = entity_type.upper()
        if risk_level:
            stmt_findings = stmt_findings.where(PIIFinding.risk_level == risk_level.upper())
            filters_applied["risk_level"] = risk_level.upper()
        if column_name:
            stmt_findings = stmt_findings.where(PIIFinding.column_name.ilike(f"%{column_name.strip()}%"))
            filters_applied["column_name"] = column_name.strip()

        findings = db.scalars(stmt_findings).all()

        summary_resp = PIIScanSummaryResponse.model_validate(scan_result)
        findings_resp = [PIIFindingResponse.model_validate(f) for f in findings]

        return PIIDetailsResponse(
            scan=summary_resp,
            findings=findings_resp,
            total_findings=scan_result.total_findings,
            filtered_count=len(findings_resp),
            filters_applied=filters_applied,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Underlying dataset file could not be found: {e}",
        )
    except Exception as e:
        logger.error(f"Error retrieving PII details for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve PII details: {str(e)}",
        )
