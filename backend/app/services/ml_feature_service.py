"""
DataGuard AI — ML Feature Service & Multi-Factor Risk Scoring Engine

Orchestrates:
1. Feature vector extraction across Profiling, Quality, and PII baselines
2. ML supervised domain inference via scikit-learn pipeline
3. Composite 0–100 risk scoring with transparent factor decomposition
4. Human-readable explainability generation (Risk Factors vs Protective Factors)
5. PostgreSQL persistence for ColumnRiskPrediction entities
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetVersion
from app.models.profiling import ProfilingResult
from app.models.quality import QualityValidationResult, QualityExpectationResult
from app.models.pii import PIIScanResult, PIIFinding
from app.models.risk import ColumnRiskPrediction
from app.ml.feature_extractor import extract_column_feature_dict
from app.ml.predictor import get_ml_predictor
from app.ml.model import MODEL_VERSION
from app.services.profiling_service import generate_profile_for_version
from app.services.quality_service import generate_quality_for_version
from app.services.pii_service import generate_pii_for_version

logger = logging.getLogger("dataguard.services.risk")

# ---------------------------------------------------------------------------
# Domain Sensitivity Constants
# ---------------------------------------------------------------------------
DOMAIN_BASE_SENSITIVITY: Dict[str, float] = {
    "Financial": 30.0,
    "Personal Information": 26.0,
    "Contact Information": 24.0,
    "Identifier": 22.0,
    "Technical / System": 16.0,
    "Demographic": 14.0,
    "Location": 12.0,
    "Text": 10.0,
    "Categorical": 5.0,
    "Numerical / Measurement": 4.0,
    "Temporal": 2.0,
    "Other": 3.0,
}

HIGH_SEVERITY_PII = {
    "CREDIT_CARD",
    "US_SSN",
    "IBAN_CODE",
    "CRYPTO",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "US_BANK_NUMBER",
    "MEDICAL_LICENSE",
}

MEDIUM_SEVERITY_PII = {
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "PERSON",
    "IP_ADDRESS",
    "LOCATION",
    "PASSPORT",
}


def calculate_column_risk(
    predicted_domain: str,
    model_confidence: float,
    col_feature_dict: Dict[str, Any],
    pii_findings_for_col: List[Dict[str, Any]],
    quality_failures_for_col: List[Dict[str, Any]],
) -> Tuple[float, str, Dict[str, Any]]:
    """
    Computes a transparent, multi-factor risk score (0.0 to 100.0), risk level category,
    and structured explainability breakdown (risk factors & protective factors).
    """
    risk_factors = []
    protective_factors = []

    # -----------------------------------------------------------------------
    # 1. PII Sensitivity Contribution (up to 45 pts)
    # -----------------------------------------------------------------------
    s_pii = 0.0
    if pii_findings_for_col:
        # Find highest severity finding
        has_high_pii = any(f.get("entity_type", "").upper() in HIGH_SEVERITY_PII for f in pii_findings_for_col)
        has_med_pii = any(f.get("entity_type", "").upper() in MEDIUM_SEVERITY_PII for f in pii_findings_for_col)

        if has_high_pii:
            base_pii_weight = 45.0
        elif has_med_pii:
            base_pii_weight = 30.0
        else:
            base_pii_weight = 15.0

        max_conf = max([float(f.get("confidence", 0.0) or 0.0) for f in pii_findings_for_col], default=0.5)
        max_rate = max([float(f.get("detection_rate", 0.0) or 0.0) for f in pii_findings_for_col], default=0.5)

        s_pii = round(base_pii_weight * (0.6 * max_conf + 0.4 * max(max_rate, 0.4)), 1)
        
        # Explainability
        for f in pii_findings_for_col:
            ent = f.get("entity_type", "PII")
            conf_pct = int(float(f.get("confidence", 0.0) or 0.0) * 100)
            src = f.get("detection_source", "sample")
            risk_factors.append(f"PII detected: {ent} ({conf_pct}% confidence, source: {src})")
    else:
        protective_factors.append("No sensitive PII entities detected in column name or sample values")

    # -----------------------------------------------------------------------
    # 2. Domain Sensitivity Contribution (up to 30 pts)
    # -----------------------------------------------------------------------
    base_domain_sens = DOMAIN_BASE_SENSITIVITY.get(predicted_domain, 5.0)
    conf_factor = 0.5 + (0.5 * model_confidence)
    s_domain = round(base_domain_sens * conf_factor, 1)

    conf_pct = int(model_confidence * 100)
    if base_domain_sens >= 20.0:
        risk_factors.append(
            f"Classified as sensitive domain '{predicted_domain}' with {conf_pct}% model confidence"
        )
    elif base_domain_sens <= 5.0:
        protective_factors.append(
            f"Classified as low-risk domain '{predicted_domain}' ({conf_pct}% model confidence)"
        )
    else:
        risk_factors.append(
            f"Classified as '{predicted_domain}' ({conf_pct}% model confidence)"
        )

    # -----------------------------------------------------------------------
    # 3. Uniqueness & Quasi-Identifier Contribution (up to 15 pts)
    # -----------------------------------------------------------------------
    unique_pct = col_feature_dict.get("unique_pct", 0.0)
    s_unique = 0.0

    if unique_pct >= 90.0:
        if predicted_domain in ("Identifier", "Contact Information", "Personal Information", "Technical / System"):
            s_unique = round(15.0 * (unique_pct / 100.0), 1)
            risk_factors.append(
                f"High cardinality ({unique_pct:.1f}% uniqueness) indicates direct individual record identification"
            )
        else:
            s_unique = round(8.0 * (unique_pct / 100.0), 1)
            risk_factors.append(f"High uniqueness ratio ({unique_pct:.1f}%)")
    elif unique_pct >= 50.0:
        s_unique = round(5.0 * (unique_pct / 100.0), 1)
    else:
        protective_factors.append(f"Low individual distinctness ratio ({unique_pct:.1f}% uniqueness)")

    # -----------------------------------------------------------------------
    # 4. Data Quality Risk Contribution (up to 10 pts)
    # -----------------------------------------------------------------------
    qual_count = len(quality_failures_for_col)
    missing_pct = col_feature_dict.get("missing_pct", 0.0)

    quality_pts = (qual_count * 3.5) + (3.0 if missing_pct > 15.0 else 0.0)
    s_quality = round(min(10.0, quality_pts), 1)

    if qual_count > 0:
        risk_factors.append(f"{qual_count} Great Expectations data quality rule failures on this column")
    else:
        protective_factors.append("Zero Great Expectations data quality rule failures")

    if missing_pct > 10.0:
        risk_factors.append(f"Elevated missingness rate ({missing_pct:.1f}% null values)")
    elif missing_pct < 1.0:
        protective_factors.append("Complete column with minimal missing data (<1%)")

    # -----------------------------------------------------------------------
    # Total Composite Score (0.0 to 100.0)
    # -----------------------------------------------------------------------
    raw_score = s_pii + s_domain + s_unique + s_quality
    clamped_score = round(max(0.0, min(100.0, raw_score)), 1)

    if clamped_score >= 80.0:
        risk_level = "CRITICAL"
    elif clamped_score >= 60.0:
        risk_level = "HIGH"
    elif clamped_score >= 35.0:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    explanation = {
        "risk_factors": risk_factors,
        "protective_factors": protective_factors,
        "score_components": {
            "pii_contribution": s_pii,
            "domain_contribution": s_domain,
            "uniqueness_contribution": s_unique,
            "quality_contribution": s_quality,
            "total_score": clamped_score,
        },
    }

    return clamped_score, risk_level, explanation


def ensure_prerequisites(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
) -> Tuple[ProfilingResult, QualityValidationResult, PIIScanResult]:
    """
    Ensures Phase 4 Profiling, Phase 5 Quality, and Phase 6 PII results exist in PostgreSQL.
    If any prerequisite is missing, automatically generates it cleanly.
    """
    # 1. Profiling
    stmt_p = select(ProfilingResult).where(ProfilingResult.dataset_version_id == version_id)
    prof = db.scalar(stmt_p)
    if not prof:
        logger.info("Phase 4 Profiling missing — executing auto-profiling...")
        generate_profile_for_version(db=db, dataset_id=dataset_id, version_id=version_id, force_recompute=False)
        prof = db.scalar(stmt_p)

    # 2. Quality
    stmt_q = select(QualityValidationResult).where(QualityValidationResult.dataset_version_id == version_id)
    qual = db.scalar(stmt_q)
    if not qual:
        logger.info("Phase 5 Quality missing — executing auto-quality evaluation...")
        generate_quality_for_version(db=db, dataset_id=dataset_id, version_id=version_id, force_recompute=False)
        qual = db.scalar(stmt_q)

    # 3. PII
    stmt_pii = select(PIIScanResult).where(PIIScanResult.dataset_version_id == version_id)
    pii = db.scalar(stmt_pii)
    if not pii:
        logger.info("Phase 6 PII Scan missing — executing auto-PII detection...")
        generate_pii_for_version(db=db, dataset_id=dataset_id, version_id=version_id, force_recompute=False)
        pii = db.scalar(stmt_pii)

    return prof, qual, pii


def generate_risk_predictions_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = False,
) -> List[ColumnRiskPrediction]:
    """
    Performs ML column classification and risk scoring for all columns in a DatasetVersion.
    Saves predictions to PostgreSQL and returns the prediction records.
    """
    # 1. Fetch Dataset & Version
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
        raise ValueError(
            f"DatasetVersion with id='{version_id}' not found for dataset='{dataset_id}'."
        )

    # 2. Check for cached predictions
    stmt_existing = (
        select(ColumnRiskPrediction)
        .where(ColumnRiskPrediction.dataset_version_id == version.id)
        .order_by(ColumnRiskPrediction.risk_score.desc(), ColumnRiskPrediction.column_name.asc())
    )
    existing_preds = db.scalars(stmt_existing).all()

    if existing_preds and not force_recompute:
        logger.info(
            f"Returning {len(existing_preds)} cached ColumnRiskPredictions for '{version.dataset.name}' V{version.version_number}"
        )
        return existing_preds

    # 3. Ensure all Phase 4, 5, 6 prerequisites are present
    prof, qual, pii = ensure_prerequisites(db=db, dataset_id=dataset_id, version_id=version_id)

    # Extract metadata structures
    col_profiles = prof.column_profiles if prof else {}
    quality_expectations = qual.expectations if qual else []
    pii_findings = pii.findings if pii else []

    # Map expectations and findings by column name
    findings_by_col: Dict[str, List[Dict[str, Any]]] = {}
    for f in pii_findings:
        findings_by_col.setdefault(f.column_name, []).append({
            "entity_type": f.entity_type,
            "confidence": f.confidence,
            "detection_rate": f.detection_rate,
            "detection_source": f.detection_source,
            "risk_level": f.risk_level,
        })

    failures_by_col: Dict[str, List[Dict[str, Any]]] = {}
    for exp in quality_expectations:
        if exp.column_name and not exp.success:
            failures_by_col.setdefault(exp.column_name, []).append({
                "expectation_type": exp.expectation_type,
                "category": exp.category,
                "failure_message": exp.failure_message,
            })

    # 4. Get ML Predictor
    predictor = get_ml_predictor()

    # 5. Build feature vectors and predict
    column_names = version.column_names or list(col_profiles.keys())
    new_prediction_entities = []

    # Clear old predictions if recomputing
    if existing_preds:
        db.execute(
            delete(ColumnRiskPrediction).where(ColumnRiskPrediction.dataset_version_id == version.id)
        )
        db.flush()

    for col_name in column_names:
        c_prof = col_profiles.get(col_name, {})
        c_pii = findings_by_col.get(col_name, [])
        c_qual = failures_by_col.get(col_name, [])

        feat_dict = extract_column_feature_dict(
            col_name=col_name,
            col_profile=c_prof,
            pii_findings=c_pii,
            quality_expectations=c_qual,
            row_count=version.row_count or 100,
        )

        pred_result = predictor.predict_column(feat_dict)
        predicted_domain = pred_result["predicted_domain"]
        model_confidence = pred_result["model_confidence"]

        risk_score, risk_level, explanation = calculate_column_risk(
            predicted_domain=predicted_domain,
            model_confidence=model_confidence,
            col_feature_dict=feat_dict,
            pii_findings_for_col=c_pii,
            quality_failures_for_col=c_qual,
        )

        has_pii_flag = len(c_pii) > 0
        max_pii_conf = max([float(f["confidence"]) for f in c_pii], default=0.0)
        max_pii_rate = max([float(f["detection_rate"]) for f in c_pii], default=0.0)

        pred_entity = ColumnRiskPrediction(
            dataset_version_id=version.id,
            column_name=col_name,
            predicted_domain=predicted_domain,
            model_confidence=model_confidence,
            risk_score=risk_score,
            risk_level=risk_level,
            pii_signal=has_pii_flag,
            pii_confidence=max_pii_conf,
            pii_detection_rate=max_pii_rate,
            quality_failure_count=len(c_qual),
            feature_snapshot=feat_dict,
            explanation=explanation,
            model_version=pred_result.get("model_version", MODEL_VERSION),
            predicted_at=datetime.now(timezone.utc),
        )
        db.add(pred_entity)
        new_prediction_entities.append(pred_entity)

    try:
        db.commit()
        for entity in new_prediction_entities:
            db.refresh(entity)
        logger.info(
            f"Generated & saved {len(new_prediction_entities)} ColumnRiskPredictions for '{version.dataset.name}' V{version.version_number}"
        )
        return new_prediction_entities
    except IntegrityError:
        db.rollback()
        logger.info(f"Concurrent risk prediction write detected for version {version.id}; fetching existing records.")
        stmt_existing = (
            select(ColumnRiskPrediction)
            .where(ColumnRiskPrediction.dataset_version_id == version.id)
            .order_by(ColumnRiskPrediction.risk_score.desc(), ColumnRiskPrediction.column_name.asc())
        )
        existing_preds = db.scalars(stmt_existing).all()
        if existing_preds:
            return existing_preds
        raise


def get_risk_predictions_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
) -> List[ColumnRiskPrediction]:
    """
    Retrieve existing risk predictions for a DatasetVersion.
    """
    stmt = (
        select(ColumnRiskPrediction)
        .join(DatasetVersion)
        .join(Dataset)
        .where(
            DatasetVersion.id == version_id,
            Dataset.id == dataset_id,
        )
        .order_by(ColumnRiskPrediction.risk_score.desc(), ColumnRiskPrediction.column_name.asc())
    )
    return db.scalars(stmt).all()
