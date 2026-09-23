"""
DataGuard AI — Full Analytical Pipeline Orchestrator

Runs phases 4, 5, 7, 8, 9 in the background after upload.
Phase 6 (PII) is EXCLUDED — the user triggers it manually on the PII page.

No Ollama. No threading. Pure synchronous background task.
"""

import logging
from uuid import UUID

from app.database import SessionLocal
from app.models.dataset import DatasetVersion

logger = logging.getLogger("dataguard.services.pipeline")


def run_full_pipeline(dataset_id: UUID, version_id: UUID) -> None:
    """
    Execute the fast portion of the analytical pipeline.
    Phase 6 (PII) is intentionally excluded and runs on-demand.
    """
    db = SessionLocal()
    try:
        logger.info(f"[PIPELINE] Starting for dataset={dataset_id} version={version_id}")

        # Phase 4 — Profiling
        try:
            from app.services.profiling_service import generate_profile_for_version
            generate_profile_for_version(
                db=db, dataset_id=dataset_id, version_id=version_id,
                force_recompute=False,
            )
            logger.info("[PIPELINE] Phase 4 Profiling complete")
        except Exception as e:
            logger.error(f"[PIPELINE] Phase 4 Profiling failed: {e}", exc_info=True)

        # Phase 5 — Quality
        try:
            from app.services.quality_service import generate_quality_for_version
            generate_quality_for_version(
                db=db, dataset_id=dataset_id, version_id=version_id,
                force_recompute=False,
            )
            logger.info("[PIPELINE] Phase 5 Quality complete")
        except Exception as e:
            logger.error(f"[PIPELINE] Phase 5 Quality failed: {e}", exc_info=True)

        # Phase 6 (PII) — SKIPPED (lazy-loaded when user visits PII page)

        # Phase 7 — ML Risk
        try:
            from app.services.ml_feature_service import generate_risk_predictions_for_version
            generate_risk_predictions_for_version(
                db=db, dataset_id=dataset_id, version_id=version_id,
                force_recompute=False,
            )
            logger.info("[PIPELINE] Phase 7 ML Risk complete")
        except Exception as e:
            logger.error(f"[PIPELINE] Phase 7 ML Risk failed: {e}", exc_info=True)

        # Phase 8 — Anomaly Detection
        try:
            from app.services.anomaly_service import analyze_dataset_anomalies_for_version
            analyze_dataset_anomalies_for_version(
                db=db, dataset_id=dataset_id, version_id=version_id,
                force_recompute=False,
            )
            logger.info("[PIPELINE] Phase 8 Anomalies complete")
        except Exception as e:
            logger.error(f"[PIPELINE] Phase 8 Anomalies failed: {e}", exc_info=True)

        # Phase 9 — Health & Issues
        try:
            from app.services.issue_service import analyze_and_save_dataset_health
            version = db.query(DatasetVersion).filter(DatasetVersion.id == version_id).first()
            if version:
                analyze_and_save_dataset_health(version, db, force=False)
                logger.info("[PIPELINE] Phase 9 Health complete")
        except Exception as e:
            logger.error(f"[PIPELINE] Phase 9 Health failed: {e}", exc_info=True)

        logger.info(f"[PIPELINE] Finished for version={version_id}")
    finally:
        db.close()