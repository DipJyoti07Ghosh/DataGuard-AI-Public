"""
DataGuard AI — Anomaly & Outlier Detection API Endpoints

Provides REST endpoints to:
1. Trigger statistical and ML-based anomaly detection across dataset columns
2. Retrieve cached dataset-level anomaly summaries and column scorecards
3. Query filtered anomaly findings with severity, method, and column name filters

Ownership enforced: only the dataset's owner can trigger or read anomaly detection.
"""

import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth.dependencies import get_current_user, assert_dataset_owner
from app.auth.models import User
from app.database import get_db
from app.models.dataset import Dataset, DatasetVersion
from app.models.anomaly import AnomalyDetectionResult, AnomalyFinding
from app.auth.dependencies import get_current_user, assert_dataset_owner
from app.auth.models import User
from app.schemas.anomaly import (
    AnomalyFindingResponse,
    DatasetAnomalySummaryResponse,
    AnomalyDetailsResponse,
)
from app.services.anomaly_service import (
    analyze_dataset_anomalies_for_version,
    get_anomaly_detection_result_for_version,
)

logger = logging.getLogger("dataguard.api.anomaly")

router = APIRouter(prefix="", tags=["Anomaly Detection"])


def _build_dataset_anomaly_response(
    version: DatasetVersion,
    result: AnomalyDetectionResult,
) -> DatasetAnomalySummaryResponse:
    """Helper to convert database AnomalyDetectionResult into DatasetAnomalySummaryResponse."""
    score = result.dataset_anomaly_score
    if score >= 80.0 or result.critical_count > 0:
        overall_sev = "CRITICAL"
    elif score >= 60.0 or result.high_count > 0:
        overall_sev = "HIGH"
    elif score >= 35.0 or result.medium_count > 0:
        overall_sev = "MEDIUM"
    else:
        overall_sev = "LOW"

    method_breakdown = result.summary.get("method_breakdown", {}) if result.summary else {}

    findings_resp = [AnomalyFindingResponse.model_validate(f) for f in result.findings]

    return DatasetAnomalySummaryResponse(
        dataset_id=version.dataset_id,
        dataset_version_id=version.id,
        version_number=version.version_number,
        dataset_name=version.dataset.name if version.dataset else "Dataset",
        total_columns_analyzed=result.total_columns_analyzed,
        columns_with_anomalies=result.columns_with_anomalies,
        total_anomalies=result.total_anomalies,
        critical_count=result.critical_count,
        high_count=result.high_count,
        medium_count=result.medium_count,
        low_count=result.low_count,
        dataset_anomaly_score=result.dataset_anomaly_score,
        overall_severity=overall_sev,
        method_breakdown=method_breakdown,
        summary=result.summary or {},
        analyzed_at=result.analyzed_at,
        findings=findings_resp,
    )


@router.post(
    "/{dataset_id}/versions/{version_id}/anomalies/detect",
    response_model=DatasetAnomalySummaryResponse,
    summary="Trigger anomaly and outlier detection",
    description=(
        "Executes IQR, Z-Score, Isolation Forest, and Categorical frequency outlier "
        "detection across all columns in the specified DatasetVersion."
    ),
)
def detect_anomalies(
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = Query(
        False,
        description="If True, forces re-computation of anomalies even if cached results exist",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run anomaly detection and persist findings."""
    try:
        assert_dataset_owner(db, dataset_id, current_user)

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

        result = analyze_dataset_anomalies_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
            force_recompute=force_recompute,
        )
        return _build_dataset_anomaly_response(version, result)
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
        logger.error(f"Error executing anomaly detection for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute anomaly detection: {str(e)}",
        )


@router.get(
    "/{dataset_id}/versions/{version_id}/anomalies",
    response_model=DatasetAnomalySummaryResponse,
    summary="Get anomaly detection scorecard",
    description="Retrieves cached anomaly summary. If not yet evaluated, automatically runs initial detection.",
)
def get_anomalies(
    dataset_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve anomaly scorecard for a dataset version."""
    try:
        assert_dataset_owner(db, dataset_id, current_user)

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

        result = get_anomaly_detection_result_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
        )
        if not result:
            result = analyze_dataset_anomalies_for_version(
                db=db,
                dataset_id=dataset_id,
                version_id=version_id,
                force_recompute=False,
            )

        return _build_dataset_anomaly_response(version, result)
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
        logger.error(f"Error retrieving anomalies for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve anomaly scorecard: {str(e)}",
        )


@router.get(
    "/{dataset_id}/versions/{version_id}/anomalies/details",
    response_model=AnomalyDetailsResponse,
    summary="Get filtered anomaly findings",
    description="Returns detailed column anomaly findings with query filtering by severity, method, and column_name.",
)
def get_anomaly_details(
    dataset_id: UUID,
    version_id: UUID,
    severity: Optional[str] = Query(None, description="Filter by severity ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')"),
    method: Optional[str] = Query(None, description="Filter by detection method ('IQR', 'Z_SCORE', 'ISOLATION_FOREST', 'CATEGORICAL_FREQUENCY', 'MULTI_METHOD_CONSENSUS')"),
    column_name: Optional[str] = Query(None, description="Filter by column name pattern"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve filtered column anomaly findings."""
    try:
        assert_dataset_owner(db, dataset_id, current_user)

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

        result = get_anomaly_detection_result_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
        )
        if not result:
            result = analyze_dataset_anomalies_for_version(
                db=db,
                dataset_id=dataset_id,
                version_id=version_id,
                force_recompute=False,
            )

        summary_resp = _build_dataset_anomaly_response(version, result)

        # Apply database query filters
        stmt_findings = select(AnomalyFinding).where(AnomalyFinding.detection_result_id == result.id)

        filters_applied = {}
        if severity:
            stmt_findings = stmt_findings.where(AnomalyFinding.severity == severity.upper())
            filters_applied["severity"] = severity.upper()
        if method:
            stmt_findings = stmt_findings.where(AnomalyFinding.detection_method.ilike(f"%{method.strip()}%"))
            filters_applied["method"] = method.strip()
        if column_name:
            stmt_findings = stmt_findings.where(AnomalyFinding.column_name.ilike(f"%{column_name.strip()}%"))
            filters_applied["column_name"] = column_name.strip()

        filtered_findings = db.scalars(stmt_findings.order_by(AnomalyFinding.score.desc(), AnomalyFinding.column_name.asc())).all()
        findings_resp = [AnomalyFindingResponse.model_validate(f) for f in filtered_findings]

        return AnomalyDetailsResponse(
            summary=summary_resp.model_dump(exclude={"findings"}),
            findings=findings_resp,
            total_findings=len(result.findings),
            filtered_count=len(findings_resp),
            filters_applied=filters_applied,
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
        logger.error(f"Error retrieving anomaly details for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve anomaly details: {str(e)}",
        )