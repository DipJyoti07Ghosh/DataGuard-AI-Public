"""
DataGuard AI — Anomaly & Outlier Detection Engine

Implements statistical (IQR, Z-Score), machine learning (Isolation Forest),
and categorical frequency anomaly detection across dataset columns.
Provides multi-method consensus aggregation, deterministic severity scoring,
privacy safeguards, and PostgreSQL persistence.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetVersion
from app.models.profiling import ProfilingResult
from app.models.quality import QualityValidationResult
from app.models.pii import PIIScanResult
from app.models.risk import ColumnRiskPrediction
from app.models.anomaly import AnomalyDetectionResult, AnomalyFinding
from app.config import settings
from app.services.ingestion import parse_csv, parse_excel
from app.services.profiling_service import generate_profile_for_version
from app.services.quality_service import generate_quality_for_version
from app.services.pii_service import generate_pii_for_version
from app.services.ml_feature_service import generate_risk_predictions_for_version

logger = logging.getLogger("dataguard.services.anomaly")

# Configurable constants
MIN_SAMPLES_FOR_IFOREST = 20
IFOREST_SAMPLING_THRESHOLD = 50000
IFOREST_SAMPLE_SIZE = 50000
RANDOM_STATE = 42
Z_SCORE_THRESHOLD = 3.0
RARE_CATEGORY_THRESHOLD = 0.01  # 1% frequency threshold


def detect_iqr_outliers(series: pd.Series, col_name: str) -> Dict[str, Any]:
    """
    Computes Interquartile Range (IQR) outliers for a numeric pandas Series.
    Lower bound = Q1 - 1.5 * IQR
    Upper bound = Q3 + 1.5 * IQR
    Handles zero-IQR case without false-positive mass flagging.
    """
    clean_series = pd.to_numeric(series.dropna(), errors="coerce").dropna()
    total_valid = len(clean_series)

    if total_valid < 4:
        return {
            "method": "IQR",
            "executed": False,
            "detected": False,
            "reason": "Insufficient numeric observations (N < 4)",
            "q1": None,
            "q3": None,
            "iqr": None,
            "lower_bound": None,
            "upper_bound": None,
            "anomaly_count": 0,
            "anomaly_rate": 0.0,
            "lower_outliers": 0,
            "upper_outliers": 0,
        }

    q1 = float(np.percentile(clean_series, 25))
    q3 = float(np.percentile(clean_series, 75))
    iqr = round(q3 - q1, 6)

    if iqr == 0.0:
        # Flat distribution or heavy mode at quartile.
        # Fall back to 3-std bounds around median to avoid collapsing bounds to a single point.
        med = float(np.median(clean_series))
        std = float(np.std(clean_series))
        if std > 1e-6:
            lower_bound = round(med - 3.0 * std, 4)
            upper_bound = round(med + 3.0 * std, 4)
            lower_mask = clean_series < lower_bound
            upper_mask = clean_series > upper_bound
            lower_count = int(lower_mask.sum())
            upper_count = int(upper_mask.sum())
            anomaly_count = lower_count + upper_count
            anomaly_rate = round((anomaly_count / total_valid) * 100.0, 2)
            detected = anomaly_count > 0
            return {
                "method": "IQR",
                "executed": True,
                "detected": detected,
                "zero_iqr_fallback": True,
                "q1": round(q1, 4),
                "q3": round(q3, 4),
                "iqr": 0.0,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "anomaly_count": anomaly_count,
                "anomaly_rate": anomaly_rate,
                "lower_outliers": lower_count,
                "upper_outliers": upper_count,
            }
        else:
            return {
                "method": "IQR",
                "executed": True,
                "detected": False,
                "zero_iqr_fallback": False,
                "q1": round(q1, 4),
                "q3": round(q3, 4),
                "iqr": 0.0,
                "lower_bound": round(q1, 4),
                "upper_bound": round(q3, 4),
                "anomaly_count": 0,
                "anomaly_rate": 0.0,
                "lower_outliers": 0,
                "upper_outliers": 0,
            }

    lower_bound = round(q1 - 1.5 * iqr, 4)
    upper_bound = round(q3 + 1.5 * iqr, 4)

    lower_mask = clean_series < lower_bound
    upper_mask = clean_series > upper_bound

    lower_count = int(lower_mask.sum())
    upper_count = int(upper_mask.sum())
    anomaly_count = lower_count + upper_count
    anomaly_rate = round((anomaly_count / total_valid) * 100.0, 2)
    detected = anomaly_count > 0

    return {
        "method": "IQR",
        "executed": True,
        "detected": detected,
        "zero_iqr_fallback": False,
        "q1": round(q1, 4),
        "q3": round(q3, 4),
        "iqr": round(iqr, 4),
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "anomaly_count": anomaly_count,
        "anomaly_rate": anomaly_rate,
        "lower_outliers": lower_count,
        "upper_outliers": upper_count,
    }


def detect_zscore_outliers(
    series: pd.Series,
    col_name: str,
    threshold: float = Z_SCORE_THRESHOLD,
) -> Dict[str, Any]:
    """
    Computes Standard Score (Z-Score) outliers for a numeric pandas Series.
    z = (x - mean) / std
    Handles zero standard deviation, all-null series, and small samples safely.
    """
    clean_series = pd.to_numeric(series.dropna(), errors="coerce").dropna()
    total_valid = len(clean_series)

    if total_valid < 5:
        return {
            "method": "Z_SCORE",
            "executed": False,
            "detected": False,
            "reason": "Insufficient observations (N < 5)",
            "mean": None,
            "std": None,
            "threshold": threshold,
            "max_abs_zscore": 0.0,
            "anomaly_count": 0,
            "anomaly_rate": 0.0,
        }

    mean_val = float(clean_series.mean())
    std_val = float(clean_series.std(ddof=1))

    if std_val < 1e-6 or np.isnan(std_val):
        return {
            "method": "Z_SCORE",
            "executed": True,
            "detected": False,
            "reason": "Zero or near-zero variance",
            "mean": round(mean_val, 4),
            "std": 0.0,
            "threshold": threshold,
            "max_abs_zscore": 0.0,
            "anomaly_count": 0,
            "anomaly_rate": 0.0,
        }

    z_scores = np.abs((clean_series - mean_val) / std_val)
    max_z = round(float(z_scores.max()), 4) if len(z_scores) > 0 else 0.0

    outlier_mask = z_scores > threshold
    anomaly_count = int(outlier_mask.sum())
    anomaly_rate = round((anomaly_count / total_valid) * 100.0, 2)
    detected = anomaly_count > 0

    return {
        "method": "Z_SCORE",
        "executed": True,
        "detected": detected,
        "mean": round(mean_val, 4),
        "std": round(std_val, 4),
        "threshold": threshold,
        "max_abs_zscore": max_z,
        "anomaly_count": anomaly_count,
        "anomaly_rate": anomaly_rate,
    }


def detect_isolation_forest(
    series: pd.Series,
    col_name: str,
    random_state: int = RANDOM_STATE,
) -> Dict[str, Any]:
    """
    Runs scikit-learn IsolationForest for unsupervised numerical outlier isolation.
    Enforces minimum observation thresholds, variance checks, and deterministic subsampling.
    """
    clean_series = pd.to_numeric(series.dropna(), errors="coerce").dropna()
    total_valid = len(clean_series)

    if total_valid < MIN_SAMPLES_FOR_IFOREST:
        return {
            "method": "ISOLATION_FOREST",
            "executed": False,
            "detected": False,
            "reason": f"Insufficient observations for Isolation Forest (N={total_valid} < {MIN_SAMPLES_FOR_IFOREST})",
            "total_rows": total_valid,
            "rows_analyzed": total_valid,
            "sampling_used": False,
            "sampling_strategy": "NONE",
            "anomaly_count": 0,
            "anomaly_rate": 0.0,
        }

    # Variance and cardinality check
    unique_vals = clean_series.nunique()
    if unique_vals < 5 or float(clean_series.std()) < 1e-6:
        return {
            "method": "ISOLATION_FOREST",
            "executed": False,
            "detected": False,
            "reason": f"Low variance or low cardinality (unique values = {unique_vals})",
            "total_rows": total_valid,
            "rows_analyzed": total_valid,
            "sampling_used": False,
            "sampling_strategy": "NONE",
            "anomaly_count": 0,
            "anomaly_rate": 0.0,
        }

    # Subsampling for very large datasets
    sampling_used = total_valid > IFOREST_SAMPLING_THRESHOLD
    if sampling_used:
        sampled_series = clean_series.sample(
            n=IFOREST_SAMPLE_SIZE,
            random_state=random_state,
        )
        rows_analyzed = IFOREST_SAMPLE_SIZE
        sampling_strategy = f"REPRODUCIBLE_RANDOM_SUBSET ({IFOREST_SAMPLE_SIZE:,} rows)"
    else:
        sampled_series = clean_series
        rows_analyzed = total_valid
        sampling_strategy = "FULL_DATASET"

    try:
        X = sampled_series.values.reshape(-1, 1)
        iso = IsolationForest(
            n_estimators=100,
            contamination="auto",
            random_state=random_state,
            n_jobs=1,
        )
        preds = iso.fit_predict(X)
        # IsolationForest returns -1 for anomalies, 1 for inliers
        anomaly_mask = preds == -1
        sample_anomaly_count = int(np.sum(anomaly_mask))
        sample_anomaly_rate = round((sample_anomaly_count / rows_analyzed) * 100.0, 2)

        # Scale anomaly count estimate to full valid dataset if sampled
        if sampling_used:
            estimated_full_count = int(round(total_valid * (sample_anomaly_count / rows_analyzed)))
        else:
            estimated_full_count = sample_anomaly_count

        detected = sample_anomaly_count > 0

        # Extract score statistics
        decision_scores = iso.decision_function(X)
        min_score = round(float(np.min(decision_scores)), 4)
        mean_score = round(float(np.mean(decision_scores)), 4)

        return {
            "method": "ISOLATION_FOREST",
            "executed": True,
            "detected": detected,
            "total_rows": total_valid,
            "rows_analyzed": rows_analyzed,
            "sampling_used": sampling_used,
            "sampling_strategy": sampling_strategy,
            "anomaly_count": estimated_full_count,
            "anomaly_rate": sample_anomaly_rate,
            "min_decision_score": min_score,
            "mean_decision_score": mean_score,
            "contamination": "auto",
        }
    except Exception as e:
        logger.warning(f"Isolation Forest execution failed for column '{col_name}': {e}")
        return {
            "method": "ISOLATION_FOREST",
            "executed": False,
            "detected": False,
            "reason": f"Execution error: {str(e)}",
            "total_rows": total_valid,
            "rows_analyzed": rows_analyzed,
            "sampling_used": sampling_used,
            "sampling_strategy": sampling_strategy,
            "anomaly_count": 0,
            "anomaly_rate": 0.0,
        }


def detect_categorical_anomalies(
    series: pd.Series,
    col_name: str,
    predicted_domain: str = "Categorical",
    uniqueness_pct: float = 0.0,
) -> Dict[str, Any]:
    """
    Identifies rare category frequency anomalies (< 1% frequency) in categorical/text columns.
    Suppresses false-positive explosion on high-cardinality identifiers or quasi-identifiers.
    NEVER returns or stores raw sensitive category values.
    """
    clean_series = series.dropna().astype(str)
    total_valid = len(clean_series)

    if total_valid < 30:
        return {
            "method": "CATEGORICAL_FREQUENCY",
            "executed": False,
            "detected": False,
            "reason": "Insufficient categorical observations (N < 30)",
            "unique_categories_count": clean_series.nunique() if total_valid > 0 else 0,
            "rare_category_count": 0,
            "rare_observation_count": 0,
            "rare_category_rate": 0.0,
            "dominant_category_rate": 0.0,
        }

    unique_count = clean_series.nunique()
    effective_uniqueness = (unique_count / total_valid) * 100.0 if total_valid > 0 else 0.0

    # Identifier / Quasi-Identifier suppression:
    # If uniqueness >= 75% or domain is Identifier/Technical/System, do not treat unique IDs as rare anomalies
    if (
        effective_uniqueness >= 75.0
        or uniqueness_pct >= 75.0
        or predicted_domain in ("Identifier", "Technical / System")
    ):
        return {
            "method": "CATEGORICAL_FREQUENCY",
            "executed": True,
            "detected": False,
            "is_identifier_like": True,
            "reason": "High-cardinality / identifier-like column; frequency anomalies suppressed",
            "unique_categories_count": unique_count,
            "rare_category_count": 0,
            "rare_observation_count": 0,
            "rare_category_rate": 0.0,
            "dominant_category_rate": round(100.0 / max(unique_count, 1), 2),
        }

    # Frequency distribution calculation
    value_counts = clean_series.value_counts()
    freq_rates = value_counts / total_valid

    # Rare categories are those with frequency < 1% (and count at least 1)
    rare_mask = freq_rates < RARE_CATEGORY_THRESHOLD
    rare_cat_count = int(rare_mask.sum())
    rare_obs_count = int(value_counts[rare_mask].sum())
    rare_rate = round((rare_obs_count / total_valid) * 100.0, 2)
    dominant_rate = round(float(freq_rates.max()) * 100.0, 2) if len(freq_rates) > 0 else 0.0

    # To be marked as an actionable frequency anomaly, there must be a non-trivial rare subset
    # without the column being entirely uniform
    detected = rare_cat_count > 0 and rare_rate <= 30.0

    return {
        "method": "CATEGORICAL_FREQUENCY",
        "executed": True,
        "detected": detected,
        "is_identifier_like": False,
        "unique_categories_count": unique_count,
        "rare_category_count": rare_cat_count,
        "rare_observation_count": rare_obs_count,
        "rare_category_rate": rare_rate,
        "dominant_category_rate": dominant_rate,
    }


def aggregate_anomaly_evidence(
    col_name: str,
    dtype: str,
    iqr_res: Dict[str, Any],
    zscore_res: Dict[str, Any],
    iforest_res: Dict[str, Any],
    cat_res: Dict[str, Any],
    phase7_prediction: Optional[ColumnRiskPrediction] = None,
    phase6_has_pii: bool = False,
) -> Tuple[str, int, float, str, float, Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Combines individual detector outputs into multi-method consensus,
    calculates deterministic severity (LOW/MEDIUM/HIGH/CRITICAL) and score (0–100),
    and generates structured explainability.
    """
    # 1. Tally method detections
    detected_methods = []
    anomaly_counts = []
    anomaly_rates = []

    if iqr_res.get("detected"):
        detected_methods.append("IQR")
        anomaly_counts.append(iqr_res.get("anomaly_count", 0))
        anomaly_rates.append(iqr_res.get("anomaly_rate", 0.0))

    if zscore_res.get("detected"):
        detected_methods.append("Z_SCORE")
        anomaly_counts.append(zscore_res.get("anomaly_count", 0))
        anomaly_rates.append(zscore_res.get("anomaly_rate", 0.0))

    if iforest_res.get("detected"):
        detected_methods.append("ISOLATION_FOREST")
        anomaly_counts.append(iforest_res.get("anomaly_count", 0))
        anomaly_rates.append(iforest_res.get("anomaly_rate", 0.0))

    if cat_res.get("detected"):
        detected_methods.append("CATEGORICAL_FREQUENCY")
        anomaly_counts.append(cat_res.get("rare_observation_count", 0))
        anomaly_rates.append(cat_res.get("rare_category_rate", 0.0))

    methods_agree_count = len(detected_methods)

    # Determine primary method label
    if methods_agree_count >= 2:
        primary_method = "MULTI_METHOD_CONSENSUS"
    elif methods_agree_count == 1:
        primary_method = detected_methods[0]
    else:
        primary_method = "NONE"

    # Effective anomaly count & rate (robust median of active detector estimates)
    effective_count = int(np.median(anomaly_counts)) if anomaly_counts else 0
    effective_rate = round(float(np.median(anomaly_rates)), 2) if anomaly_rates else 0.0

    # 2. Deterministic Severity Scoring (0.0 to 100.0)
    # Severity is decoupled from Phase 7 column risk score
    score = 0.0
    drivers = []
    caveats = [
        "Anomaly detection indicates statistical or distributional deviation; it is evidence for review, not proof of data defect."
    ]
    protective_factors = []

    if methods_agree_count == 0:
        severity = "LOW"
        score = 0.0
        protective_factors.append("No statistical or frequency anomalies detected across active detectors.")
    else:
        # Base from anomaly concentration (up to 45 pts)
        base_rate_pts = min(45.0, effective_rate * 3.0)
        score += base_rate_pts
        drivers.append(f"Anomalous distribution concentration: {effective_rate}% of rows flagged ({effective_count} observations)")

        # Agreement boost (up to 30 pts)
        if methods_agree_count >= 3:
            score += 30.0
            drivers.append(f"Strong multi-detector agreement: 3 independent methods confirmed outliers ({', '.join(detected_methods)})")
        elif methods_agree_count == 2:
            score += 15.0
            drivers.append(f"Multi-detector consensus: 2 independent methods confirmed outliers ({', '.join(detected_methods)})")
        else:
            drivers.append(f"Single detector flag: {detected_methods[0]}")

        # Statistical extremeness bonus (up to 15 pts)
        if zscore_res.get("detected"):
            max_z = zscore_res.get("max_abs_zscore", 0.0)
            if max_z >= 6.0:
                score += 15.0
                drivers.append(f"Extreme statistical z-score excursion: max |z| = {max_z:.1f} standard deviations")
            elif max_z >= 4.0:
                score += 8.0
                drivers.append(f"Elevated z-score excursion: max |z| = {max_z:.1f} standard deviations")

        if iqr_res.get("detected"):
            iqr_val = iqr_res.get("iqr", 0.0)
            if iqr_val > 0:
                drivers.append(f"Values outside IQR bounds [{iqr_res.get('lower_bound')}, {iqr_res.get('upper_bound')}]")

        # Contextual domain sensitivity (up to 10 pts priority context)
        phase7_domain = phase7_prediction.predicted_domain if phase7_prediction else "Unknown"
        phase7_risk_level = phase7_prediction.risk_level if phase7_prediction else "LOW"

        if phase6_has_pii or phase7_risk_level in ("CRITICAL", "HIGH"):
            score += 10.0
            drivers.append(f"Anomalies detected in sensitive column (Phase 7: {phase7_domain}, Risk: {phase7_risk_level})")

        score = round(max(0.0, min(100.0, score)), 1)

        if score >= 80.0:
            severity = "CRITICAL"
        elif score >= 60.0:
            severity = "HIGH"
        elif score >= 35.0:
            severity = "MEDIUM"
        else:
            severity = "LOW"

    # Evidence dictionary
    evidence = {
        "methods_evaluated": ["IQR", "Z_SCORE", "ISOLATION_FOREST", "CATEGORICAL_FREQUENCY"],
        "detected_methods": detected_methods,
        "methods_agree_count": methods_agree_count,
        "iqr": iqr_res,
        "zscore": zscore_res,
        "isolation_forest": iforest_res,
        "categorical_frequency": cat_res,
    }

    # Statistical summary (Zero Raw PII)
    statistical_summary = {
        "dtype": dtype,
        "iqr_bounds": {
            "lower": iqr_res.get("lower_bound"),
            "upper": iqr_res.get("upper_bound"),
            "q1": iqr_res.get("q1"),
            "q3": iqr_res.get("q3"),
            "iqr": iqr_res.get("iqr"),
        } if iqr_res.get("executed") else None,
        "zscore_moments": {
            "mean": zscore_res.get("mean"),
            "std": zscore_res.get("std"),
            "max_abs_zscore": zscore_res.get("max_abs_zscore"),
        } if zscore_res.get("executed") else None,
        "categorical_metrics": {
            "unique_categories": cat_res.get("unique_categories_count"),
            "rare_category_count": cat_res.get("rare_category_count"),
            "rare_observation_rate": cat_res.get("rare_category_rate"),
            "dominant_category_rate": cat_res.get("dominant_category_rate"),
        } if cat_res.get("executed") else None,
    }

    # Explanation dictionary
    explanation = {
        "summary": (
            f"Anomalies detected by {', '.join(detected_methods)} ({effective_rate}% of observations)"
            if detected_methods
            else "Clean distribution; no statistical or frequency anomalies detected."
        ),
        "drivers": drivers,
        "caveats": caveats,
        "protective_factors": protective_factors,
        "phase7_context": {
            "predicted_domain": phase7_prediction.predicted_domain if phase7_prediction else "Unknown",
            "risk_level": phase7_prediction.risk_level if phase7_prediction else "LOW",
            "risk_score": phase7_prediction.risk_score if phase7_prediction else 0.0,
        } if phase7_prediction else None,
    }

    return (
        primary_method,
        effective_count,
        effective_rate,
        severity,
        score,
        statistical_summary,
        evidence,
        explanation,
    )


def ensure_phase8_prerequisites(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
) -> Tuple[Optional[ProfilingResult], Optional[QualityValidationResult], Optional[PIIScanResult], List[ColumnRiskPrediction]]:
    """
    Ensures that profiling (Phase 4), quality (Phase 5), PII (Phase 6), and ML risk (Phase 7)
    records are available to enrich contextual metadata.
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

    # 4. Risk Predictions (Phase 7)
    stmt_risk = select(ColumnRiskPrediction).where(ColumnRiskPrediction.dataset_version_id == version_id)
    risk_preds = db.scalars(stmt_risk).all()
    if not risk_preds:
        logger.info("Phase 7 ML Risk missing — executing auto-risk classification...")
        risk_preds = generate_risk_predictions_for_version(db=db, dataset_id=dataset_id, version_id=version_id, force_recompute=False)

    return prof, qual, pii, risk_preds


def analyze_dataset_anomalies_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = False,
) -> AnomalyDetectionResult:
    """
    Executes end-to-end anomaly detection on the physical dataset associated with a DatasetVersion.
    Runs IQR, Z-score, Isolation Forest, and Categorical frequency analysis across all columns.
    Persists AnomalyDetectionResult and AnomalyFindings to PostgreSQL.
    """
    # 1. Fetch Version and Dataset
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
        raise ValueError(f"DatasetVersion with id='{version_id}' not found for dataset='{dataset_id}'.")

    # 2. Check for cached result
    stmt_existing = (
        select(AnomalyDetectionResult)
        .where(AnomalyDetectionResult.dataset_version_id == version.id)
    )
    existing_result = db.scalar(stmt_existing)

    if existing_result and not force_recompute:
        logger.info(
            f"Returning cached AnomalyDetectionResult for '{version.dataset.name}' V{version.version_number}"
        )
        return existing_result

    # 3. Load dataset DataFrame
    upload_dir = Path(settings.upload_path)
    file_path = upload_dir / version.stored_filename
    if not file_path.exists():
        raise FileNotFoundError(
            f"Stored file '{version.stored_filename}' for version V{version.version_number} not found on disk."
        )

    file_content = file_path.read_bytes()
    if version.file_type == "csv":
        df, _, _ = parse_csv(file_content)
    elif version.file_type == "xlsx":
        df, _ = parse_excel(file_content)
    else:
        raise ValueError(f"Unsupported file type '{version.file_type}' for anomaly detection.")

    # 4. Ensure Prerequisites (Phase 4, 5, 6, 7)
    prof, qual, pii, risk_preds = ensure_phase8_prerequisites(db=db, dataset_id=dataset_id, version_id=version_id)

    # Map Phase 7 predictions and Phase 6 PII findings by column name
    risk_by_col = {rp.column_name: rp for rp in risk_preds}
    pii_cols = {f.column_name for f in (pii.findings if pii else [])}
    col_profiles = prof.column_profiles if prof else {}

    # 5. Clear old results if recomputing
    if existing_result:
        db.execute(
            delete(AnomalyDetectionResult).where(AnomalyDetectionResult.dataset_version_id == version.id)
        )
        db.flush()

    total_cols = len(df.columns)
    columns_with_anomalies = 0
    total_anomalies_count = 0
    crit_count = 0
    high_count = 0
    med_count = 0
    low_count = 0

    method_breakdown = {
        "IQR": 0,
        "Z_SCORE": 0,
        "ISOLATION_FOREST": 0,
        "CATEGORICAL_FREQUENCY": 0,
        "MULTI_METHOD_CONSENSUS": 0,
    }

    findings_list = []
    finding_scores = []

    # 6. Execute detectors column by column
    for col_name in df.columns:
        series = df[col_name]
        c_prof = col_profiles.get(col_name, {})
        p7_pred = risk_by_col.get(col_name)
        has_pii = col_name in pii_cols
        uniqueness_pct = float(c_prof.get("unique_percentage", 0.0) or 0.0)

        dtype_str = str(series.dtype).lower()
        is_numeric = np.issubdtype(series.dtype, np.number)

        # Detectors
        if is_numeric:
            iqr_res = detect_iqr_outliers(series, col_name)
            zscore_res = detect_zscore_outliers(series, col_name)
            iforest_res = detect_isolation_forest(series, col_name)
            cat_res = {
                "method": "CATEGORICAL_FREQUENCY",
                "executed": False,
                "detected": False,
                "reason": "Numeric column — categorical analysis skipped",
            }
        else:
            iqr_res = {"method": "IQR", "executed": False, "detected": False, "reason": "Non-numeric column"}
            zscore_res = {"method": "Z_SCORE", "executed": False, "detected": False, "reason": "Non-numeric column"}
            iforest_res = {"method": "ISOLATION_FOREST", "executed": False, "detected": False, "reason": "Non-numeric column"}
            predicted_dom = p7_pred.predicted_domain if p7_pred else "Categorical"
            cat_res = detect_categorical_anomalies(
                series=series,
                col_name=col_name,
                predicted_domain=predicted_dom,
                uniqueness_pct=uniqueness_pct,
            )

        (
            primary_method,
            anom_count,
            anom_rate,
            severity,
            score,
            stat_summary,
            evidence,
            explanation,
        ) = aggregate_anomaly_evidence(
            col_name=col_name,
            dtype=dtype_str,
            iqr_res=iqr_res,
            zscore_res=zscore_res,
            iforest_res=iforest_res,
            cat_res=cat_res,
            phase7_prediction=p7_pred,
            phase6_has_pii=has_pii,
        )

        has_anomalies = evidence.get("methods_agree_count", 0) > 0
        if has_anomalies:
            columns_with_anomalies += 1
            total_anomalies_count += anom_count

            # Track method usage
            for dm in evidence.get("detected_methods", []):
                method_breakdown[dm] = method_breakdown.get(dm, 0) + 1
            if primary_method == "MULTI_METHOD_CONSENSUS":
                method_breakdown["MULTI_METHOD_CONSENSUS"] = method_breakdown.get("MULTI_METHOD_CONSENSUS", 0) + 1

        if severity == "CRITICAL":
            crit_count += 1
        elif severity == "HIGH":
            high_count += 1
        elif severity == "MEDIUM":
            med_count += 1
        else:
            low_count += 1

        finding_scores.append(score)

        finding_entity = AnomalyFinding(
            column_name=col_name,
            detection_method=primary_method,
            anomaly_count=anom_count,
            anomaly_rate=anom_rate,
            severity=severity,
            score=score,
            statistical_summary=stat_summary,
            evidence=evidence,
            explanation=explanation,
        )
        findings_list.append(finding_entity)

    # 7. Dataset-level composite anomaly severity index
    if total_cols > 0:
        top_3 = sorted(finding_scores, reverse=True)[:3]
        top_3_mean = sum(top_3) / len(top_3) if top_3 else 0.0
        overall_mean = sum(finding_scores) / total_cols
        dataset_anomaly_score = round(0.7 * top_3_mean + 0.3 * overall_mean, 1)
    else:
        dataset_anomaly_score = 0.0

    summary_metadata = {
        "total_rows": len(df),
        "total_columns": total_cols,
        "method_breakdown": method_breakdown,
        "sampling_info": {
            "sampling_threshold": IFOREST_SAMPLING_THRESHOLD,
            "sampling_used": len(df) > IFOREST_SAMPLING_THRESHOLD,
        },
    }

    result_entity = AnomalyDetectionResult(
        dataset_version_id=version.id,
        analyzed_at=datetime.now(timezone.utc),
        total_columns_analyzed=total_cols,
        columns_with_anomalies=columns_with_anomalies,
        total_anomalies=total_anomalies_count,
        critical_count=crit_count,
        high_count=high_count,
        medium_count=med_count,
        low_count=low_count,
        dataset_anomaly_score=dataset_anomaly_score,
        summary=summary_metadata,
        findings=findings_list,
    )

    db.add(result_entity)
    try:
        db.commit()
        db.refresh(result_entity)
        logger.info(
            f"Saved AnomalyDetectionResult (id={result_entity.id}, score={dataset_anomaly_score}, anomalies={total_anomalies_count}) for '{version.dataset.name}' V{version.version_number}"
        )
        return result_entity
    except IntegrityError:
        db.rollback()
        logger.info(f"Concurrent anomaly detection write detected for version {version.id}; fetching existing record.")
        stmt_existing = (
            select(AnomalyDetectionResult)
            .where(AnomalyDetectionResult.dataset_version_id == version.id)
        )
        existing_result = db.scalar(stmt_existing)
        if existing_result:
            return existing_result
        raise


def get_anomaly_detection_result_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
) -> Optional[AnomalyDetectionResult]:
    """
    Retrieves the persisted AnomalyDetectionResult for a DatasetVersion.
    """
    stmt = (
        select(AnomalyDetectionResult)
        .join(DatasetVersion)
        .join(Dataset)
        .where(
            DatasetVersion.id == version_id,
            Dataset.id == dataset_id,
        )
    )
    return db.scalar(stmt)
