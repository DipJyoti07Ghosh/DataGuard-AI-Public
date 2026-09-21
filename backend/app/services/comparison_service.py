"""
DataGuard AI — Phase 10 Dataset Version Comparison & Drift Engine

Computes deterministic, explainable differences between two versions of the same dataset:
- Schema changes (added, removed, type changed, unchanged)
- Missingness shifts (percentage-point changes)
- Uniqueness and cardinality shifts
- Real 2-sample Kolmogorov-Smirnov (KS) test for continuous numerical distributions
- Population Stability Index (PSI) with Laplace smoothing for categorical distributions
- Consumes stored Phase 5 Quality, Phase 6 PII, Phase 7 ML Risk, Phase 8 Anomalies, and Phase 9 Health results
- Synthesizes an explainable overall drift status (NO_DRIFT, LOW_DRIFT, MEDIUM_DRIFT, HIGH_DRIFT)
"""

import math
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.dataset import Dataset, DatasetVersion
from app.models.profiling import ProfilingResult
from app.models.quality import QualityValidationResult
from app.models.risk import ColumnRiskPrediction
from app.models.anomaly import AnomalyDetectionResult, AnomalyFinding
from app.models.pii import PIIScanResult, PIIFinding
from app.models.comparison import DatasetComparison, ColumnDriftResult
from app.services.ingestion import parse_csv, parse_excel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: Safe physical dataframe loader
# ---------------------------------------------------------------------------
def _load_version_dataframe(version: DatasetVersion) -> Optional[pd.DataFrame]:
    """
    Attempt to load physical dataset file from disk safely.
    Returns DataFrame if file exists and is readable, else None.
    """
    if not version or not getattr(version, "stored_filename", None):
        return None

    upload_dir = settings.upload_path
    path = upload_dir / version.stored_filename

    if not path.exists() or not path.is_file():
        # Fallback to direct path check if stored_filename is absolute
        direct_path = Path(version.stored_filename)
        if direct_path.exists() and direct_path.is_file():
            path = direct_path
        else:
            return None

    try:
        file_content = path.read_bytes()
        ext = path.suffix.lower()
        if ext == ".csv":
            df, _, _ = parse_csv(file_content)
            return df
        elif ext in [".xlsx", ".xls"]:
            df, _ = parse_excel(file_content)
            return df
    except Exception as e:
        logger.warning(f"Could not load physical file for version {version.id}: {e}")
        return None

    return None


# ---------------------------------------------------------------------------
# Helper: Clean numbers for JSON serialization
# ---------------------------------------------------------------------------
def _clean_num(val: Any) -> Optional[float]:
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return None
    try:
        return round(float(val), 4)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core Comparison & Drift Function
# ---------------------------------------------------------------------------
def compare_dataset_versions(
    dataset_id: UUID,
    baseline_version_id: UUID,
    current_version_id: UUID,
    db: Session,
    force_recompute: bool = False,
) -> DatasetComparison:
    """
    Compare two snapshot versions of the same dataset.
    If comparison already exists and force_recompute=False, returns cached result.
    Otherwise computes fresh drift analysis and persists.
    """
    # 1. Validation: Versions must belong to the same dataset and be distinct
    if baseline_version_id == current_version_id:
        raise ValueError("Cannot compare a dataset version with itself. Select two different versions.")

    dataset = db.execute(select(Dataset).where(Dataset.id == dataset_id)).scalar_one_or_none()
    if not dataset:
        raise ValueError(f"Dataset with ID '{dataset_id}' not found")

    baseline_version = db.execute(
        select(DatasetVersion).where(
            DatasetVersion.id == baseline_version_id,
            DatasetVersion.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()
    if not baseline_version:
        raise ValueError(f"Baseline version '{baseline_version_id}' not found for dataset '{dataset_id}'")

    current_version = db.execute(
        select(DatasetVersion).where(
            DatasetVersion.id == current_version_id,
            DatasetVersion.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()
    if not current_version:
        raise ValueError(f"Current version '{current_version_id}' not found for dataset '{dataset_id}'")

    # 2. Check for cached comparison
    existing_comp = db.execute(
        select(DatasetComparison).where(
            and_(
                DatasetComparison.dataset_id == dataset_id,
                DatasetComparison.baseline_version_id == baseline_version_id,
                DatasetComparison.current_version_id == current_version_id,
            )
        )
    ).scalar_one_or_none()

    if existing_comp and not force_recompute:
        logger.info(f"Returning cached comparison {existing_comp.id} for dataset {dataset_id}")
        return existing_comp

    # 3. Retrieve stored profiling results (Phase 4)
    base_prof = db.execute(
        select(ProfilingResult).where(ProfilingResult.dataset_version_id == baseline_version_id)
    ).scalar_one_or_none()
    curr_prof = db.execute(
        select(ProfilingResult).where(ProfilingResult.dataset_version_id == current_version_id)
    ).scalar_one_or_none()

    base_profiles = (base_prof.column_profiles if base_prof else {}) or {}
    curr_profiles = (curr_prof.column_profiles if curr_prof else {}) or {}

    # 4. Retrieve Phase 5 Quality results
    base_qual = db.execute(
        select(QualityValidationResult).where(QualityValidationResult.dataset_version_id == baseline_version_id)
    ).scalar_one_or_none()
    curr_qual = db.execute(
        select(QualityValidationResult).where(QualityValidationResult.dataset_version_id == current_version_id)
    ).scalar_one_or_none()

    # 5. Retrieve Phase 6 PII results
    base_pii = db.execute(
        select(PIIScanResult).where(PIIScanResult.dataset_version_id == baseline_version_id)
    ).scalar_one_or_none()
    curr_pii = db.execute(
        select(PIIScanResult).where(PIIScanResult.dataset_version_id == current_version_id)
    ).scalar_one_or_none()

    # 6. Retrieve Phase 7 ML Risk results
    base_risks = {
        r.column_name: r
        for r in db.execute(
            select(ColumnRiskPrediction).where(ColumnRiskPrediction.dataset_version_id == baseline_version_id)
        ).scalars().all()
    }
    curr_risks = {
        r.column_name: r
        for r in db.execute(
            select(ColumnRiskPrediction).where(ColumnRiskPrediction.dataset_version_id == current_version_id)
        ).scalars().all()
    }

    # 7. Retrieve Phase 8 Anomaly results
    base_anom = db.execute(
        select(AnomalyDetectionResult).where(AnomalyDetectionResult.dataset_version_id == baseline_version_id)
    ).scalar_one_or_none()
    curr_anom = db.execute(
        select(AnomalyDetectionResult).where(AnomalyDetectionResult.dataset_version_id == current_version_id)
    ).scalar_one_or_none()

    base_anom_findings = {
        f.column_name: f
        for f in (base_anom.findings if base_anom else [])
    }
    curr_anom_findings = {
        f.column_name: f
        for f in (curr_anom.findings if curr_anom else [])
    }

    # 8. Load physical DataFrames if available for exact KS / PSI testing
    df_base = _load_version_dataframe(baseline_version)
    df_curr = _load_version_dataframe(current_version)

    # 9. Analyze Schema Evolution
    base_cols = set(base_profiles.keys()) if base_profiles else set(df_base.columns if df_base is not None else [])
    curr_cols = set(curr_profiles.keys()) if curr_profiles else set(df_curr.columns if df_curr is not None else [])
    all_cols = sorted(list(base_cols | curr_cols))

    added_cols = [c for c in all_cols if c in curr_cols and c not in base_cols]
    removed_cols = [c for c in all_cols if c in base_cols and c not in curr_cols]
    type_changed_cols = []
    unchanged_cols = []

    for c in all_cols:
        if c in base_cols and c in curr_cols:
            b_type = (base_profiles.get(c) or {}).get("dtype", "")
            c_type = (curr_profiles.get(c) or {}).get("dtype", "")
            if b_type and c_type and b_type != c_type:
                type_changed_cols.append({
                    "column_name": c,
                    "baseline_type": b_type,
                    "current_type": c_type,
                })
            else:
                unchanged_cols.append(c)

    schema_drift_summary = {
        "total_changes": len(added_cols) + len(removed_cols) + len(type_changed_cols),
        "added_columns": added_cols,
        "removed_columns": removed_cols,
        "type_changed_columns": type_changed_cols,
        "unchanged_columns": unchanged_cols,
    }

    # 10. Analyze Column-Level Drift & Evidence
    column_drift_records = []
    drift_drivers = []
    num_drifted_cols = []
    cat_drifted_cols = []
    ks_executed_count = 0
    psi_executed_count = 0
    missingness_increased_cols = []
    max_pp_missing_increase = 0.0
    uniqueness_shifted_cols = []
    max_pp_unique_shift = 0.0

    for col in all_cols:
        b_prof = base_profiles.get(col, {})
        c_prof = curr_profiles.get(col, {})

        # Schema status
        if col in added_cols:
            schema_status = "ADDED"
            b_type = None
            c_type = c_prof.get("dtype") or (str(df_curr[col].dtype) if df_curr is not None and col in df_curr.columns else None)
        elif col in removed_cols:
            schema_status = "REMOVED"
            b_type = b_prof.get("dtype") or (str(df_base[col].dtype) if df_base is not None and col in df_base.columns else None)
            c_type = None
        elif any(tc["column_name"] == col for tc in type_changed_cols):
            schema_status = "TYPE_CHANGED"
            b_type = b_prof.get("dtype")
            c_type = c_prof.get("dtype")
        else:
            schema_status = "UNCHANGED"
            b_type = b_prof.get("dtype") or c_prof.get("dtype")
            c_type = c_prof.get("dtype") or b_type

        type_category = c_prof.get("type_category") or b_prof.get("type_category") or "text"

        evidence_list = []
        col_drift_status = "NO_DRIFT"

        # A. Missingness Comparison
        b_miss_pct = b_prof.get("missing_percentage", 0.0) if col in base_cols else 0.0
        c_miss_pct = c_prof.get("missing_percentage", 0.0) if col in curr_cols else 0.0
        miss_delta_pp = round(c_miss_pct - b_miss_pct, 2)

        if col in base_cols and col in curr_cols:
            if miss_delta_pp >= 15.0:
                miss_class = "HIGH_DRIFT"
                evidence_list.append(f"Missingness spiked by +{miss_delta_pp} percentage points ({b_miss_pct}% → {c_miss_pct}%)")
                missingness_increased_cols.append(col)
                if miss_delta_pp > max_pp_missing_increase:
                    max_pp_missing_increase = miss_delta_pp
            elif miss_delta_pp >= 5.0:
                miss_class = "MEDIUM_DRIFT"
                evidence_list.append(f"Missingness increased by +{miss_delta_pp} percentage points ({b_miss_pct}% → {c_miss_pct}%)")
                missingness_increased_cols.append(col)
                if miss_delta_pp > max_pp_missing_increase:
                    max_pp_missing_increase = miss_delta_pp
            elif miss_delta_pp >= 1.0:
                miss_class = "LOW_DRIFT"
                missingness_increased_cols.append(col)
            else:
                miss_class = "NO_DRIFT"
        else:
            miss_class = "NOT_APPLICABLE"

        missingness_comparison = {
            "baseline_count": b_prof.get("missing_count", 0),
            "current_count": c_prof.get("missing_count", 0),
            "baseline_pct": b_miss_pct,
            "current_pct": c_miss_pct,
            "percentage_point_change": miss_delta_pp,
            "classification": miss_class,
        }

        # B. Uniqueness Comparison
        b_uniq_pct = b_prof.get("unique_percentage", 0.0) if col in base_cols else 0.0
        c_uniq_pct = c_prof.get("unique_percentage", 0.0) if col in curr_cols else 0.0
        uniq_delta_pp = round(c_uniq_pct - b_uniq_pct, 2)
        abs_uniq_delta = abs(uniq_delta_pp)

        if col in base_cols and col in curr_cols:
            if abs_uniq_delta >= 20.0:
                uniq_class = "MEDIUM_DRIFT"
                evidence_list.append(f"Uniqueness shifted by {uniq_delta_pp:+} percentage points ({b_uniq_pct}% → {c_uniq_pct}%)")
                uniqueness_shifted_cols.append(col)
                if abs_uniq_delta > max_pp_unique_shift:
                    max_pp_unique_shift = abs_uniq_delta
            elif abs_uniq_delta >= 5.0:
                uniq_class = "LOW_DRIFT"
                uniqueness_shifted_cols.append(col)
                if abs_uniq_delta > max_pp_unique_shift:
                    max_pp_unique_shift = abs_uniq_delta
            else:
                uniq_class = "NO_DRIFT"
        else:
            uniq_class = "NOT_APPLICABLE"

        uniqueness_comparison = {
            "baseline_count": b_prof.get("unique_count", 0),
            "current_count": c_prof.get("unique_count", 0),
            "baseline_pct": b_uniq_pct,
            "current_pct": c_uniq_pct,
            "percentage_point_change": uniq_delta_pp,
            "classification": uniq_class,
        }

        # C. Statistical & Distribution Drift
        statistical_comparison = {}
        if col in base_cols and col in curr_cols:
            is_numeric = type_category == "numeric"
            
            if is_numeric:
                # Continuous numerical drift
                s_base = df_base[col].dropna() if df_base is not None and col in df_base.columns else None
                s_curr = df_curr[col].dropna() if df_curr is not None and col in df_curr.columns else None

                if s_base is not None and s_curr is not None and len(s_base) >= 5 and len(s_curr) >= 5:
                    # Execute real 2-sample Kolmogorov-Smirnov test
                    try:
                        ks_res = stats.ks_2samp(s_base, s_curr)
                        ks_stat = _clean_num(ks_res.statistic)
                        p_val = _clean_num(ks_res.pvalue)
                        w_dist = _clean_num(stats.wasserstein_distance(s_base, s_curr))
                        ks_executed_count += 1

                        if ks_stat is not None and p_val is not None:
                            if ks_stat >= 0.35 and p_val < 0.01:
                                ks_class = "HIGH_DRIFT"
                                evidence_list.append(f"Kolmogorov-Smirnov test indicates significant numerical distribution drift (KS={ks_stat:.3f}, p={p_val:.4f})")
                                num_drifted_cols.append(col)
                            elif ks_stat >= 0.20 and p_val < 0.05:
                                ks_class = "MEDIUM_DRIFT"
                                evidence_list.append(f"Kolmogorov-Smirnov test indicates moderate distribution drift (KS={ks_stat:.3f}, p={p_val:.4f})")
                                num_drifted_cols.append(col)
                            elif ks_stat >= 0.10 and p_val < 0.05:
                                ks_class = "LOW_DRIFT"
                            else:
                                ks_class = "NO_DRIFT"
                        else:
                            ks_class = "NO_DRIFT"

                        statistical_comparison = {
                            "test_type": "KOLMOGOROV_SMIRNOV",
                            "status": "EXECUTED",
                            "sampling_used": False,
                            "baseline_rows_evaluated": len(s_base),
                            "current_rows_evaluated": len(s_curr),
                            "statistic": ks_stat,
                            "p_value": p_val,
                            "wasserstein_distance": w_dist,
                            "classification": ks_class,
                            "mean_shift": {
                                "baseline": _clean_num(b_prof.get("mean")),
                                "current": _clean_num(c_prof.get("mean")),
                                "delta": _clean_num((c_prof.get("mean") or 0) - (b_prof.get("mean") or 0)),
                            },
                            "std_shift": {
                                "baseline": _clean_num(b_prof.get("std")),
                                "current": _clean_num(c_prof.get("std")),
                                "delta": _clean_num((c_prof.get("std") or 0) - (b_prof.get("std") or 0)),
                            },
                        }
                    except Exception as e:
                        logger.warning(f"KS test failed for col '{col}': {e}")
                        statistical_comparison = {
                            "test_type": "KOLMOGOROV_SMIRNOV",
                            "status": "UNAVAILABLE",
                            "reason": f"Calculation error: {e}",
                        }
                else:
                    # Physical series unavailable -> metric comparison only (do NOT fake KS)
                    statistical_comparison = {
                        "test_type": "KOLMOGOROV_SMIRNOV",
                        "status": "UNAVAILABLE",
                        "reason": "Raw series data not available on disk",
                        "mean_shift": {
                            "baseline": _clean_num(b_prof.get("mean")),
                            "current": _clean_num(c_prof.get("mean")),
                            "delta": _clean_num((c_prof.get("mean") or 0) - (b_prof.get("mean") or 0)) if b_prof.get("mean") is not None and c_prof.get("mean") is not None else None,
                        },
                        "std_shift": {
                            "baseline": _clean_num(b_prof.get("std")),
                            "current": _clean_num(c_prof.get("std")),
                            "delta": _clean_num((c_prof.get("std") or 0) - (b_prof.get("std") or 0)) if b_prof.get("std") is not None and c_prof.get("std") is not None else None,
                        },
                    }
            else:
                # Categorical PSI Calculation
                s_base = df_base[col].dropna() if df_base is not None and col in df_base.columns else None
                s_curr = df_curr[col].dropna() if df_curr is not None and col in df_curr.columns else None

                if s_base is not None and s_curr is not None and len(s_base) > 0 and len(s_curr) > 0:
                    try:
                        base_counts = s_base.astype(str).value_counts()
                        curr_counts = s_curr.astype(str).value_counts()
                        all_cats = list(set(base_counts.index) | set(curr_counts.index))
                        k = len(all_cats)
                        eps = 1e-4

                        b_total = len(s_base) + k * eps
                        c_total = len(s_curr) + k * eps

                        psi_val = 0.0
                        for cat in all_cats:
                            p_i = (base_counts.get(cat, 0) + eps) / b_total
                            q_i = (curr_counts.get(cat, 0) + eps) / c_total
                            psi_val += (q_i - p_i) * math.log(q_i / p_i)

                        psi_clean = _clean_num(psi_val)
                        psi_executed_count += 1

                        if psi_clean is not None:
                            if psi_clean >= 0.25:
                                psi_class = "HIGH_DRIFT"
                                evidence_list.append(f"Population Stability Index indicates high categorical distribution drift (PSI={psi_clean:.3f})")
                                cat_drifted_cols.append(col)
                            elif psi_clean >= 0.10:
                                psi_class = "MEDIUM_DRIFT"
                                evidence_list.append(f"Population Stability Index indicates moderate categorical distribution drift (PSI={psi_clean:.3f})")
                                cat_drifted_cols.append(col)
                            else:
                                psi_class = "NO_DRIFT"
                        else:
                            psi_class = "NO_DRIFT"

                        statistical_comparison = {
                            "test_type": "POPULATION_STABILITY_INDEX",
                            "status": "EXECUTED",
                            "sampling_used": False,
                            "baseline_rows_evaluated": len(s_base),
                            "current_rows_evaluated": len(s_curr),
                            "statistic": psi_clean,
                            "classification": psi_class,
                            "unique_categories_count": k,
                        }
                    except Exception as e:
                        logger.warning(f"PSI calculation failed for col '{col}': {e}")
                        statistical_comparison = {
                            "test_type": "POPULATION_STABILITY_INDEX",
                            "status": "INSUFFICIENT_DATA",
                            "reason": f"Calculation error: {e}",
                        }
                else:
                    statistical_comparison = {
                        "test_type": "POPULATION_STABILITY_INDEX",
                        "status": "INSUFFICIENT_DATA",
                        "reason": "Historical category distribution is not available",
                    }

        # D. Phase 5 Quality Impact for this column
        b_failed_rules = [
            r for r in (base_qual.expectations if base_qual and getattr(base_qual, "expectations", None) else [])
            if not getattr(r, "success", True) and getattr(r, "column_name", None) == col
        ]
        c_failed_rules = [
            r for r in (curr_qual.expectations if curr_qual and getattr(curr_qual, "expectations", None) else [])
            if not getattr(r, "success", True) and getattr(r, "column_name", None) == col
        ]

        b_desc_set = [getattr(r, "failure_message", None) or getattr(r, "expectation_type", "Rule Failure") for r in b_failed_rules]
        c_desc_set = [getattr(r, "failure_message", None) or getattr(r, "expectation_type", "Rule Failure") for r in c_failed_rules]

        quality_impact = {
            "baseline_violations_count": len(b_failed_rules),
            "current_violations_count": len(c_failed_rules),
            "new_violations": [r for r in c_desc_set if r not in b_desc_set],
            "resolved_violations": [r for r in b_desc_set if r not in c_desc_set],
        }
        if len(c_failed_rules) > len(b_failed_rules):
            evidence_list.append(f"Quality checks: {len(c_failed_rules) - len(b_failed_rules)} new rule failure(s) detected")

        # E. Phase 7 ML Risk Impact for this column
        b_risk = base_risks.get(col)
        c_risk = curr_risks.get(col)
        b_r_score = b_risk.risk_score if b_risk else 0.0
        c_r_score = c_risk.risk_score if c_risk else 0.0
        b_r_level = (b_risk.risk_level if b_risk else "LOW").upper()
        c_r_level = (c_risk.risk_level if c_risk else "LOW").upper()
        b_domain = b_risk.predicted_domain if b_risk else None
        c_domain = c_risk.predicted_domain if c_risk else None
        r_delta = round(c_r_score - b_r_score, 2)

        risk_impact = {
            "baseline_risk_score": b_r_score,
            "current_risk_score": c_r_score,
            "baseline_risk_level": b_r_level,
            "current_risk_level": c_r_level,
            "baseline_domain": b_domain,
            "current_domain": c_domain,
            "risk_delta": r_delta,
            "domain_shifted": (b_domain is not None and c_domain is not None and b_domain != c_domain),
        }

        # ML Risk drift conditions
        if col in base_cols and col in curr_cols:
            if (b_r_level in ["LOW", "MEDIUM"] and c_r_level in ["HIGH", "CRITICAL"]) or r_delta >= 20.0:
                evidence_list.append(f"ML Column Risk elevated ({b_r_level} → {c_r_level}, +{r_delta} pts)")
            elif b_domain != c_domain and b_domain is not None and c_domain is not None:
                evidence_list.append(f"ML Predicted Domain shifted from '{b_domain}' to '{c_domain}'")

        # F. Phase 8 Anomaly Impact for this column
        b_anom_f = base_anom_findings.get(col)
        c_anom_f = curr_anom_findings.get(col)
        b_anom_sev = (b_anom_f.severity if b_anom_f else "CLEAN").upper()
        c_anom_sev = (c_anom_f.severity if c_anom_f else "CLEAN").upper()
        b_anom_rate = b_anom_f.anomaly_rate if b_anom_f else 0.0
        c_anom_rate = c_anom_f.anomaly_rate if c_anom_f else 0.0

        anomaly_impact = {
            "baseline_severity": b_anom_sev,
            "current_severity": c_anom_sev,
            "baseline_rate": b_anom_rate,
            "current_rate": c_anom_rate,
        }

        if col in base_cols and col in curr_cols:
            if b_anom_sev in ["CLEAN", "LOW", "MEDIUM"] and c_anom_sev in ["HIGH", "CRITICAL"]:
                evidence_list.append(f"Anomaly detector flagged elevated severity ({b_anom_sev} → {c_anom_sev})")

        # G. Phase 6 PII Impact for this column
        b_pii_ents = [f.entity_type for f in (base_pii.findings if base_pii else []) if f.column_name == col]
        c_pii_ents = [f.entity_type for f in (curr_pii.findings if curr_pii else []) if f.column_name == col]
        new_pii = [e for e in c_pii_ents if e not in b_pii_ents]
        rem_pii = [e for e in b_pii_ents if e not in c_pii_ents]

        privacy_impact = {
            "baseline_entities": b_pii_ents,
            "current_entities": c_pii_ents,
            "newly_detected_entities": new_pii,
            "removed_entities": rem_pii,
        }

        if new_pii:
            evidence_list.append(f"New PII entity types detected: {', '.join(new_pii)}")

        # Determine individual column drift status
        if schema_status in ["REMOVED", "TYPE_CHANGED"]:
            col_drift_status = "HIGH_DRIFT"
            evidence_list.insert(0, f"Schema change: Column was {schema_status.replace('_', ' ').lower()}")
        elif schema_status == "ADDED":
            col_drift_status = "MEDIUM_DRIFT"
            evidence_list.insert(0, "Schema change: New column added to current version")
        elif (
            statistical_comparison.get("classification") == "HIGH_DRIFT"
            or miss_class == "HIGH_DRIFT"
            or (b_r_level in ["LOW", "MEDIUM"] and c_r_level in ["HIGH", "CRITICAL"])
            or r_delta >= 20.0
            or (b_anom_sev in ["CLEAN", "LOW", "MEDIUM"] and c_anom_sev in ["HIGH", "CRITICAL"])
            or len(new_pii) > 0
        ):
            col_drift_status = "HIGH_DRIFT"
        elif (
            statistical_comparison.get("classification") == "MEDIUM_DRIFT"
            or miss_class == "MEDIUM_DRIFT"
            or uniq_class == "MEDIUM_DRIFT"
            or (b_domain != c_domain and b_domain is not None and c_domain is not None)
            or (b_r_level == "LOW" and c_r_level == "MEDIUM")
            or (10.0 <= r_delta < 20.0)
            or (b_anom_sev == "LOW" and c_anom_sev == "MEDIUM")
        ):
            col_drift_status = "MEDIUM_DRIFT"
        elif (
            statistical_comparison.get("classification") == "LOW_DRIFT"
            or miss_class == "LOW_DRIFT"
            or uniq_class == "LOW_DRIFT"
        ):
            col_drift_status = "LOW_DRIFT"
        else:
            col_drift_status = "NO_DRIFT"

        column_drift_records.append({
            "column_name": col,
            "schema_status": schema_status,
            "baseline_type": b_type,
            "current_type": c_type,
            "type_category": type_category,
            "drift_status": col_drift_status,
            "missingness_comparison": missingness_comparison,
            "uniqueness_comparison": uniqueness_comparison,
            "statistical_comparison": statistical_comparison,
            "quality_impact": quality_impact,
            "risk_impact": risk_impact,
            "anomaly_impact": anomaly_impact,
            "privacy_impact": privacy_impact,
            "drift_evidence": evidence_list,
        })

    # 11. Subsystem Deltas & Overall Summaries
    # Quality Summary Delta
    b_q_score = base_qual.overall_score if base_qual else None
    c_q_score = curr_qual.overall_score if curr_qual else None
    q_delta = round(c_q_score - b_q_score, 2) if (b_q_score is not None and c_q_score is not None) else None

    if q_delta is not None:
        if q_delta <= -15.0:
            q_status = "HIGH_DRIFT"
            drift_drivers.append(f"Quality Score degraded by {q_delta} points ({b_q_score} → {c_q_score})")
        elif -15.0 < q_delta <= -5.0:
            q_status = "MEDIUM_DRIFT"
            drift_drivers.append(f"Quality Score dropped by {q_delta} points ({b_q_score} → {c_q_score})")
        elif -5.0 < q_delta < -1.0:
            q_status = "LOW_DRIFT"
        elif q_delta >= 5.0:
            q_status = "NO_DRIFT (IMPROVED)"
        else:
            q_status = "NO_DRIFT"
    else:
        q_status = "NOT_EVALUATED"

    quality_drift_summary = {
        "status": q_status,
        "baseline_score": b_q_score,
        "current_score": c_q_score,
        "score_delta": q_delta,
        "new_violations_count": sum(len(c["quality_impact"].get("new_violations", [])) for c in column_drift_records),
        "resolved_violations_count": sum(len(c["quality_impact"].get("resolved_violations", [])) for c in column_drift_records),
    }

    # ML Risk Summary Delta
    b_r_idx = _clean_num(np.mean([r.risk_score for r in base_risks.values()])) if base_risks else None
    c_r_idx = _clean_num(np.mean([r.risk_score for r in curr_risks.values()])) if curr_risks else None
    r_idx_delta = round(c_r_idx - b_r_idx, 2) if (b_r_idx is not None and c_r_idx is not None) else None
    newly_elevated_risks = [
        c["column_name"] for c in column_drift_records
        if (c["risk_impact"].get("baseline_risk_level") in ["LOW", "MEDIUM"] and c["risk_impact"].get("current_risk_level") in ["HIGH", "CRITICAL"])
        or c["risk_impact"].get("risk_delta", 0) >= 20.0
    ]
    domain_shifts = [
        c["column_name"] for c in column_drift_records
        if c["risk_impact"].get("domain_shifted")
    ]

    risk_drift_summary = {
        "status": "EVALUATED" if (b_r_idx is not None or c_r_idx is not None) else "NOT_EVALUATED",
        "baseline_risk_index": b_r_idx,
        "current_risk_index": c_r_idx,
        "risk_delta": r_idx_delta,
        "newly_elevated_risk_columns": newly_elevated_risks,
        "domain_changed_columns": domain_shifts,
    }

    # Anomaly Summary Delta
    b_a_score = base_anom.dataset_anomaly_score if base_anom else None
    c_a_score = curr_anom.dataset_anomaly_score if curr_anom else None
    a_delta = round(c_a_score - b_a_score, 2) if (b_a_score is not None and c_a_score is not None) else None
    newly_anom = [
        c["column_name"] for c in column_drift_records
        if c["anomaly_impact"].get("baseline_severity") in ["CLEAN", "LOW", "MEDIUM"]
        and c["anomaly_impact"].get("current_severity") in ["HIGH", "CRITICAL"]
    ]

    anomaly_drift_summary = {
        "status": "EVALUATED" if (b_a_score is not None or c_a_score is not None) else "NOT_EVALUATED",
        "baseline_anomaly_score": b_a_score,
        "current_anomaly_score": c_a_score,
        "anomaly_delta": a_delta,
        "newly_anomalous_columns": newly_anom,
    }

    # Privacy Summary Delta
    new_pii_cols = [
        c["column_name"] for c in column_drift_records
        if len(c["privacy_impact"].get("newly_detected_entities", [])) > 0
    ]
    rem_pii_cols = [
        c["column_name"] for c in column_drift_records
        if len(c["privacy_impact"].get("removed_entities", [])) > 0
    ]

    privacy_drift_summary = {
        "status": "EVALUATED" if (base_pii or curr_pii) else "NOT_EVALUATED",
        "newly_exposed_pii_columns": new_pii_cols,
        "removed_pii_columns": rem_pii_cols,
    }

    # Summaries
    numerical_drift_summary = {
        "columns_evaluated": sum(1 for c in column_drift_records if c["type_category"] == "numeric"),
        "drifted_columns": num_drifted_cols,
        "ks_executed_count": ks_executed_count,
    }
    categorical_drift_summary = {
        "columns_evaluated": sum(1 for c in column_drift_records if c["type_category"] in ["categorical", "boolean", "text"]),
        "drifted_columns": cat_drifted_cols,
        "psi_executed_count": psi_executed_count,
    }
    missingness_drift_summary = {
        "columns_with_increased_missingness": missingness_increased_cols,
        "max_pp_increase": max_pp_missing_increase,
    }
    uniqueness_drift_summary = {
        "columns_with_uniqueness_shifts": uniqueness_shifted_cols,
        "max_pp_shift": max_pp_unique_shift,
    }

    # Collect Schema Drift Drivers
    if removed_cols:
        drift_drivers.append(f"Schema Break: {len(removed_cols)} column(s) removed ({', '.join(removed_cols)})")
    if type_changed_cols:
        drift_drivers.append(f"Schema Break: {len(type_changed_cols)} column(s) changed data types")
    if added_cols:
        drift_drivers.append(f"Schema Extension: {len(added_cols)} new column(s) added ({', '.join(added_cols)})")
    if num_drifted_cols:
        drift_drivers.append(f"Numerical Drift: {len(num_drifted_cols)} column(s) diverged statistically via KS test ({', '.join(num_drifted_cols)})")
    if cat_drifted_cols:
        drift_drivers.append(f"Categorical Drift: {len(cat_drifted_cols)} column(s) shifted distribution via PSI ({', '.join(cat_drifted_cols)})")
    if new_pii_cols:
        drift_drivers.append(f"Privacy Exposure: New sensitive PII detected in {len(new_pii_cols)} column(s) ({', '.join(new_pii_cols)})")
    if newly_elevated_risks:
        drift_drivers.append(f"ML Risk: {len(newly_elevated_risks)} column(s) newly elevated to High/Critical risk")
    if newly_anom:
        drift_drivers.append(f"Anomalies: {len(newly_anom)} column(s) developed High/Critical outlier concentrations")

    # 12. Synthesize Overall Drift Status (Exact Finalized Rules)
    has_high_drift = (
        len(removed_cols) > 0
        or len(type_changed_cols) > 0
        or any(c["statistical_comparison"].get("classification") == "HIGH_DRIFT" for c in column_drift_records)
        or any(c["missingness_comparison"].get("classification") == "HIGH_DRIFT" for c in column_drift_records)
        or (q_delta is not None and q_delta <= -15.0)
        or len(newly_elevated_risks) > 0
        or (a_delta is not None and a_delta >= 15.0)
        or len(newly_anom) > 0
        or len(new_pii_cols) > 0
    )

    has_medium_drift = (
        len(added_cols) > 0
        or any(c["statistical_comparison"].get("classification") == "MEDIUM_DRIFT" for c in column_drift_records)
        or any(c["missingness_comparison"].get("classification") == "MEDIUM_DRIFT" for c in column_drift_records)
        or any(c["uniqueness_comparison"].get("classification") == "MEDIUM_DRIFT" for c in column_drift_records)
        or (q_delta is not None and -15.0 < q_delta <= -5.0)
        or len(domain_shifts) > 0
        or (a_delta is not None and 10.0 <= a_delta < 15.0)
        or any(c["risk_impact"].get("baseline_risk_level") == "LOW" and c["risk_impact"].get("current_risk_level") == "MEDIUM" for c in column_drift_records)
        or any(10.0 <= c["risk_impact"].get("risk_delta", 0) < 20.0 for c in column_drift_records)
        or any(c["anomaly_impact"].get("baseline_severity") in ["CLEAN", "LOW"] and c["anomaly_impact"].get("current_severity") == "MEDIUM" for c in column_drift_records)
    )

    has_low_drift = (
        any(c["statistical_comparison"].get("classification") == "LOW_DRIFT" for c in column_drift_records)
        or any(c["missingness_comparison"].get("classification") == "LOW_DRIFT" for c in column_drift_records)
        or any(c["uniqueness_comparison"].get("classification") == "LOW_DRIFT" for c in column_drift_records)
        or (q_delta is not None and -5.0 < q_delta < -1.0)
    )

    if has_high_drift:
        overall_drift_status = "HIGH_DRIFT"
    elif has_medium_drift:
        overall_drift_status = "MEDIUM_DRIFT"
    elif has_low_drift:
        overall_drift_status = "LOW_DRIFT"
    else:
        overall_drift_status = "NO_DRIFT"
        if not drift_drivers:
            drift_drivers.append("No significant schema, statistical, or quality drift detected between versions.")
            drift_drivers.append("All schemas, numerical distributions, categorical frequencies, and quality metrics remained stable.")

    # 13. Persist Comparison Record
    now_utc = datetime.now(timezone.utc)

    if existing_comp:
        # Update existing record
        existing_comp.status = "COMPLETED"
        existing_comp.overall_drift_status = overall_drift_status
        existing_comp.schema_drift_summary = schema_drift_summary
        existing_comp.numerical_drift_summary = numerical_drift_summary
        existing_comp.categorical_drift_summary = categorical_drift_summary
        existing_comp.missingness_drift_summary = missingness_drift_summary
        existing_comp.uniqueness_drift_summary = uniqueness_drift_summary
        existing_comp.quality_drift_summary = quality_drift_summary
        existing_comp.risk_drift_summary = risk_drift_summary
        existing_comp.anomaly_drift_summary = anomaly_drift_summary
        existing_comp.privacy_drift_summary = privacy_drift_summary
        existing_comp.drift_drivers = drift_drivers
        existing_comp.compared_at = now_utc

        # Replace child column drift results
        for old_cdr in existing_comp.column_drifts:
            db.delete(old_cdr)
        db.flush()

        comp_record = existing_comp
    else:
        comp_record = DatasetComparison(
            dataset_id=dataset_id,
            baseline_version_id=baseline_version_id,
            current_version_id=current_version_id,
            status="COMPLETED",
            overall_drift_status=overall_drift_status,
            schema_drift_summary=schema_drift_summary,
            numerical_drift_summary=numerical_drift_summary,
            categorical_drift_summary=categorical_drift_summary,
            missingness_drift_summary=missingness_drift_summary,
            uniqueness_drift_summary=uniqueness_drift_summary,
            quality_drift_summary=quality_drift_summary,
            risk_drift_summary=risk_drift_summary,
            anomaly_drift_summary=anomaly_drift_summary,
            privacy_drift_summary=privacy_drift_summary,
            drift_drivers=drift_drivers,
            created_at=now_utc,
            compared_at=now_utc,
        )
        db.add(comp_record)
        db.flush()

    for col_data in column_drift_records:
        cdr = ColumnDriftResult(
            comparison_id=comp_record.id,
            column_name=col_data["column_name"],
            schema_status=col_data["schema_status"],
            baseline_type=col_data["baseline_type"],
            current_type=col_data["current_type"],
            type_category=col_data["type_category"],
            drift_status=col_data["drift_status"],
            missingness_comparison=col_data["missingness_comparison"],
            uniqueness_comparison=col_data["uniqueness_comparison"],
            statistical_comparison=col_data["statistical_comparison"],
            quality_impact=col_data["quality_impact"],
            risk_impact=col_data["risk_impact"],
            anomaly_impact=col_data["anomaly_impact"],
            privacy_impact=col_data["privacy_impact"],
            drift_evidence=col_data["drift_evidence"],
        )
        db.add(cdr)

    db.commit()
    db.refresh(comp_record)
    logger.info(f"Phase 10 Comparison complete for dataset {dataset_id} (V{baseline_version.version_number} → V{current_version.version_number}): Status={overall_drift_status}")

    return comp_record
