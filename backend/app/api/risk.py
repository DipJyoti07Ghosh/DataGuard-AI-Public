"""
DataGuard AI — ML Column Classification & Risk Scoring API Endpoints

Provides REST endpoints to:
1. Trigger ML column domain classification and multi-factor risk scoring
2. Retrieve cached column risk scorecards and dataset risk summaries
3. Query granular predictions with risk level, domain, and column name filters
"""

import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.dataset import Dataset, DatasetVersion
from app.models.risk import ColumnRiskPrediction

from app.auth.dependencies import get_current_user, assert_dataset_owner
from app.auth.models import User

from app.schemas.risk import (
    ColumnRiskPredictionResponse,
    DatasetRiskSummaryResponse,
    RiskDetailsResponse,
)
from app.services.ml_feature_service import (
    generate_risk_predictions_for_version,
    get_risk_predictions_for_version,
)
from app.ml.model import MODEL_VERSION

logger = logging.getLogger("dataguard.api.risk")

router = APIRouter(prefix="", tags=["ML Column Risk"])


def _build_dataset_risk_summary(
    version: DatasetVersion,
    predictions: list[ColumnRiskPrediction],
) -> DatasetRiskSummaryResponse:
    """Helper to aggregate column risk predictions into a dataset-level summary."""
    total_cols = len(predictions)
    if total_cols == 0:
        return DatasetRiskSummaryResponse(
            dataset_id=version.dataset_id,
            dataset_version_id=version.id,
            version_number=version.version_number,
            dataset_name=version.dataset.name if version.dataset else "Dataset",
            total_columns=0,
            dataset_risk_index=0.0,
            overall_risk_level="LOW",
            risk_breakdown={"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            domain_breakdown={},
            mean_model_confidence=0.0,
            model_version=MODEL_VERSION,
            predicted_at=version.uploaded_at,
            predictions=[],
        )

    risk_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    domain_counts = {}
    total_score = 0.0
    total_conf = 0.0

    # Sort scores descending
    scores = [p.risk_score for p in predictions]
    for p in predictions:
        r_level = p.risk_level.upper()
        risk_counts[r_level] = risk_counts.get(r_level, 0) + 1
        domain_counts[p.predicted_domain] = domain_counts.get(p.predicted_domain, 0) + 1
        total_score += p.risk_score
        total_conf += p.model_confidence

    # Dataset Risk Index is weighted towards top risky columns
    top_3_scores = sorted(scores, reverse=True)[:3]
    top_3_mean = sum(top_3_scores) / len(top_3_scores) if top_3_scores else 0.0
    overall_mean = total_score / total_cols
    dataset_risk_index = round(0.7 * top_3_mean + 0.3 * overall_mean, 1)

    if dataset_risk_index >= 80.0 or risk_counts.get("CRITICAL", 0) > 0:
        overall_risk = "CRITICAL"
    elif dataset_risk_index >= 60.0 or risk_counts.get("HIGH", 0) > 0:
        overall_risk = "HIGH"
    elif dataset_risk_index >= 35.0 or risk_counts.get("MEDIUM", 0) > 0:
        overall_risk = "MEDIUM"
    else:
        overall_risk = "LOW"

    mean_conf = round(total_conf / total_cols, 4)
    pred_responses = [ColumnRiskPredictionResponse.model_validate(p) for p in predictions]
    predicted_timestamp = predictions[0].predicted_at if predictions else version.uploaded_at
    model_ver = predictions[0].model_version if predictions else MODEL_VERSION

    return DatasetRiskSummaryResponse(
        dataset_id=version.dataset_id,
        dataset_version_id=version.id,
        version_number=version.version_number,
        dataset_name=version.dataset.name if version.dataset else "Dataset",
        total_columns=total_cols,
        dataset_risk_index=dataset_risk_index,
        overall_risk_level=overall_risk,
        risk_breakdown=risk_counts,
        domain_breakdown=domain_counts,
        mean_model_confidence=mean_conf,
        model_version=model_ver,
        predicted_at=predicted_timestamp,
        predictions=pred_responses,
    )


@router.post(
    "/{dataset_id}/versions/{version_id}/risk/predict",
    response_model=DatasetRiskSummaryResponse,
    summary="Run ML column classification and risk scoring",
    description=(
        "Executes supervised scikit-learn domain classification and multi-factor "
        "risk scoring across all columns of the specified DatasetVersion snapshot."
    ),
)
def predict_column_risk(
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compute and persist ML column risk predictions."""
    try:
        # Fetch version
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

        predictions = generate_risk_predictions_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
            force_recompute=force_recompute,
        )
        return _build_dataset_risk_summary(version, predictions)
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
        logger.error(f"Error predicting risk for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate ML risk predictions: {str(e)}",
        )


@router.get(
    "/{dataset_id}/versions/{version_id}/risk",
    response_model=DatasetRiskSummaryResponse,
    summary="Get ML column classification and risk scorecard",
    description="Retrieves cached column risk predictions. If not yet generated, automatically runs initial prediction.",
)
def get_column_risk(
    dataset_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
):
    """Retrieve column risk assessment for a dataset version."""
    try:
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

        predictions = get_risk_predictions_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
        )
        if not predictions:
            predictions = generate_risk_predictions_for_version(
                db=db,
                dataset_id=dataset_id,
                version_id=version_id,
                force_recompute=False,
            )

        return _build_dataset_risk_summary(version, predictions)
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
        logger.error(f"Error retrieving risk for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve ML risk predictions: {str(e)}",
        )


@router.get(
    "/{dataset_id}/versions/{version_id}/risk/details",
    response_model=RiskDetailsResponse,
    summary="Get filtered column risk predictions",
    description="Returns detailed column risk findings with filtering by risk_level, domain, and column_name.",
)
def get_column_risk_details(
    dataset_id: UUID,
    version_id: UUID,
    risk_level: Optional[str] = Query(None, description="Filter by risk level ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')"),
    domain: Optional[str] = Query(None, description="Filter by predicted domain (e.g., Financial)"),
    column_name: Optional[str] = Query(None, description="Filter by column name pattern"),
    db: Session = Depends(get_db),
):
    """Retrieve detailed column risk predictions with query filters."""
    try:
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

        predictions = get_risk_predictions_for_version(
            db=db,
            dataset_id=dataset_id,
            version_id=version_id,
        )
        if not predictions:
            predictions = generate_risk_predictions_for_version(
                db=db,
                dataset_id=dataset_id,
                version_id=version_id,
                force_recompute=False,
            )

        summary_resp = _build_dataset_risk_summary(version, predictions)

        # Apply database query filters
        stmt_preds = select(ColumnRiskPrediction).where(ColumnRiskPrediction.dataset_version_id == version.id)

        filters_applied = {}
        if risk_level:
            stmt_preds = stmt_preds.where(ColumnRiskPrediction.risk_level == risk_level.upper())
            filters_applied["risk_level"] = risk_level.upper()
        if domain:
            stmt_preds = stmt_preds.where(ColumnRiskPrediction.predicted_domain.ilike(f"%{domain.strip()}%"))
            filters_applied["domain"] = domain.strip()
        if column_name:
            stmt_preds = stmt_preds.where(ColumnRiskPrediction.column_name.ilike(f"%{column_name.strip()}%"))
            filters_applied["column_name"] = column_name.strip()

        filtered_preds = db.scalars(stmt_preds.order_by(ColumnRiskPrediction.risk_score.desc())).all()
        pred_responses = [ColumnRiskPredictionResponse.model_validate(p) for p in filtered_preds]

        return RiskDetailsResponse(
            summary=summary_resp.model_dump(exclude={"predictions"}),
            predictions=pred_responses,
            total_columns=len(predictions),
            filtered_count=len(pred_responses),
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
        logger.error(f"Error retrieving risk details for version {version_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve risk details: {str(e)}",
        )
