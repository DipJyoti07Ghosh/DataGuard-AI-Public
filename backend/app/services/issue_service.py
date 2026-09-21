"""
DataGuard AI — Phase 9 Dataset Health, Issue Prioritization & Remediation Engine

Synthesizes upstream signals from:
- Phase 5: Data Quality validation rules (QualityValidationResult, QualityExpectationResult)
- Phase 6: Presidio PII & sensitive data detection (PIIScanResult, PIIFinding)
- Phase 7: ML column classification and risk scoring (ColumnRiskPrediction)
- Phase 8: Statistical and ML anomaly detection (AnomalyDetectionResult, AnomalyFinding)

Produces:
- Deterministic 0-100 Dataset Health Score and Qualitative Grades (EXCELLENT, GOOD, etc.)
- 4-Way Health Breakdown: Quality, Risk, Anomaly, Privacy
- Deduplicated Logical Data Quality Issues with preserved upstream severity
- Deterministic 0-100 Priority Scoring based on Severity, Affected Data, Data Sensitivity, Confidence, and Cross-Signal Evidence
- Safe, non-destructive, explainable remediation recommendations
- Zero Raw PII exposure guaranteed across all payloads
"""

import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from app.models.dataset import DatasetVersion
from app.models.profiling import ProfilingResult
from app.models.quality import QualityValidationResult, QualityExpectationResult
from app.models.pii import PIIScanResult, PIIFinding
from app.models.risk import ColumnRiskPrediction
from app.models.anomaly import AnomalyDetectionResult, AnomalyFinding
from app.models.issues import DatasetHealthResult, DataQualityIssue

from app.services.profiling_service import generate_profile_for_version
from app.services.quality_service import generate_quality_for_version
from app.services.pii_service import generate_pii_for_version
from app.services.ml_feature_service import generate_risk_predictions_for_version
from app.services.anomaly_service import analyze_dataset_anomalies_for_version

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transparent Phase 9 Heuristics & Weights
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Transparent Phase 9 Heuristics & Weights
# ---------------------------------------------------------------------------

# Privacy Exposure Severity Weights (Phase 6 bounded exposure calculation)
PRIVACY_SEVERITY_WEIGHTS = {
    "CRITICAL": 100.0,
    "HIGH": 70.0,
    "MEDIUM": 40.0,
    "LOW": 15.0,
    "NONE": 0.0,
}

# Issue Prioritization Severity Weights (0.30 component of Priority Score)
# Note: INFO is an internal/UI category; LOW/MEDIUM/HIGH/CRITICAL are strictly 25/50/75/100.
PRIORITY_SEVERITY_WEIGHTS = {
    "CRITICAL": 100.0,
    "HIGH": 75.0,
    "MEDIUM": 50.0,
    "LOW": 25.0,
    "INFO": 5.0,
}

# Explicitly documented data_sensitivity heuristic based on domain & PII context
# (Never claimed as measured enterprise business criticality)
DOMAIN_SENSITIVITY_MAP = {
    "Financial Data": 90.0,
    "Health / Medical": 90.0,
    "Identifier": 75.0,
    "Security / Auth": 85.0,
    "Contact Information": 60.0,
    "Personal Demographics": 60.0,
    "Location / Geospatial": 45.0,
    "Temporal / Date": 25.0,
    "Categorical / Status": 20.0,
    "Numerical / Measurement": 20.0,
    "Text / Description": 20.0,
    "Technical / System": 20.0,
}

# Cross-signal score mapping based on count of distinct upstream phases
# (Quality, PII, ML Risk, Anomaly)
CROSS_SIGNAL_SCORE_MAP = {
    0: 0.0,
    1: 25.0,
    2: 50.0,
    3: 75.0,
}  # 4 or more -> 100.0


def clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamps a floating point value within specified bounds."""
    return max(min_val, min(max_val, float(value)))


def calculate_health_grade(score: float) -> str:
    """
    Assigns qualitative health grade based on approved exact deterministic boundaries:
    90.0–100.0 : EXCELLENT
    75.0–<90.0 : GOOD
    60.0–<75.0 : NEEDS ATTENTION
    40.0–<60.0 : POOR
    0.0–<40.0  : CRITICAL
    """
    if score >= 90.0:
        return "EXCELLENT"
    elif score >= 75.0:
        return "GOOD"
    elif score >= 60.0:
        return "NEEDS ATTENTION"
    elif score >= 40.0:
        return "POOR"
    else:
        return "CRITICAL"


def calculate_affected_data_score(affected_percentage: float) -> float:
    """
    Deterministic bucketed affected data percentage scoring:
    0%      -> 0.0
    < 1%    -> 20.0
    1–5%    -> 40.0
    5–15%   -> 60.0
    15–30%  -> 80.0
    > 30%   -> 100.0
    """
    pct = float(affected_percentage)
    if pct <= 0.0:
        return 0.0
    elif pct < 1.0:
        return 20.0
    elif pct <= 5.0:
        return 40.0
    elif pct <= 15.0:
        return 60.0
    elif pct <= 30.0:
        return 80.0
    else:
        return 100.0


def calculate_anomaly_confidence_heuristic(detector_count: int) -> float:
    """
    Deterministic confidence heuristic based on multi-detector consensus:
    - 1 detector   -> 40.0
    - 2 detectors  -> 70.0
    - 3+ detectors -> 95.0
    
    Note: Agreement strengthens evidence but does NOT represent a calibrated probability
    that the data is definitely incorrect.
    """
    if detector_count >= 3:
        return 95.0
    elif detector_count == 2:
        return 70.0
    else:
        return 40.0


def calculate_cross_signal_score(signal_count: int) -> float:
    """
    Calculates cross-signal heuristic score based on count of distinct upstream phases
    (Phase 5 Quality, Phase 6 PII, Phase 7 ML Risk, Phase 8 Anomaly):
    - 0 independent signals = 0.0
    - 1 signal              = 25.0
    - 2 signals             = 50.0
    - 3 signals             = 75.0
    - 4+ signals            = 100.0
    """
    if signal_count >= 4:
        return 100.0
    return CROSS_SIGNAL_SCORE_MAP.get(signal_count, 0.0)


def calculate_priority_score(
    severity: str,
    affected_percentage: float,
    data_sensitivity: float,
    confidence_heuristic: float,
    cross_signal_count: int,
) -> Tuple[float, float, float, float, float]:
    """
    Computes deterministic 0-100 priority score:
    priority = 0.30*severity + 0.25*affected_data + 0.20*data_sensitivity + 0.15*confidence + 0.10*cross_signal
    
    All inputs and scores are deterministic heuristics, NOT calibrated probabilities.
    Returns (priority_score, sev_score, aff_score, conf_score, cross_score).
    """
    sev_score = PRIORITY_SEVERITY_WEIGHTS.get(severity.upper(), 25.0)
    aff_score = calculate_affected_data_score(affected_percentage)
    sens_score = clamp(data_sensitivity, 0.0, 100.0)
    conf_score = clamp(confidence_heuristic, 0.0, 100.0)
    cross_score = calculate_cross_signal_score(cross_signal_count)

    raw_priority = (
        0.30 * sev_score
        + 0.25 * aff_score
        + 0.20 * sens_score
        + 0.15 * conf_score
        + 0.10 * cross_score
    )
    final_priority = round(clamp(raw_priority, 0.0, 100.0), 1)
    return final_priority, sev_score, aff_score, conf_score, cross_score


# ---------------------------------------------------------------------------
# Deterministic Remediation Recommendation Generator
# ---------------------------------------------------------------------------

def generate_remediation_recommendation(
    issue_type: str,
    column_name: Optional[str],
    details: Dict[str, Any],
    has_multiple_signals: bool = False,
) -> Dict[str, Any]:
    """
    Generates non-destructive, safe remediation recommendations.
    Never recommends blind deletion or destructive mutation of source data.
    """
    target = f"column '{column_name}'" if column_name else "the dataset"

    if issue_type == "MISSING_VALUES":
        return {
            "summary": f"Review missing value distribution and ingestion pipelines for {target}.",
            "investigation_steps": [
                f"Inspect upstream ETL extracts to determine why values in {target} are null or omitted.",
                "Verify whether nullability is expected by business domain logic (e.g. optional fields).",
                "Check for systemic patterns in missingness (e.g. missingness correlated with specific dates or categories).",
            ],
            "preventive_measures": [
                "Implement schema validation checks at ingestion boundaries to reject or flag incomplete records.",
                "Apply domain-appropriate default values or imputation only after validating root cause.",
            ],
            "caution_note": "Do not delete records with missing values without verifying whether missingness carries semantic meaning.",
        }

    elif issue_type == "DUPLICATES":
        return {
            "summary": "Investigate duplicate records and verify natural entity keys.",
            "investigation_steps": [
                "Identify primary unique identifier or composite business keys that should define uniqueness.",
                "Determine whether duplicate rows represent identical duplicate submissions or repeated state updates.",
                "Check ingestion pipeline logs for retry mechanisms or parallel batch duplication.",
            ],
            "preventive_measures": [
                "Enforce unique database constraints or deduplication stages in the upstream data pipeline.",
                "Establish deterministic deduplication rules (e.g. retain latest timestamp).",
            ],
            "caution_note": "Never perform automated row deletion without confirming the precise deduplication criteria and key definitions.",
        }

    elif issue_type == "ANOMALY" or issue_type == "OUTLIER":
        methods = details.get("detected_methods", [])
        methods_str = ", ".join(methods) if methods else "statistical methods"
        return {
            "summary": f"Review unusual statistical observations identified in {target} by {methods_str}.",
            "investigation_steps": [
                f"Verify whether extreme values in {target} represent measurement unit discrepancies or data entry errors.",
                "Evaluate if extreme values reflect legitimate heavy-tailed domain phenomena (e.g. high-value transactions).",
                "Cross-reference anomalous records with related columns to check contextual consistency.",
            ],
            "preventive_measures": [
                "Configure automated range checks or soft boundary warnings in upstream validation suites.",
                "Consider robust statistical modeling or transformations (e.g. log scaling) for downstream analysis.",
            ],
            "caution_note": "Statistical anomalies provide evidence of unusualness, not definitive proof of error. Avoid automatic pruning of outliers.",
        }

    elif issue_type == "RARE_CATEGORY":
        return {
            "summary": f"Review low-frequency categorical values detected in {target}.",
            "investigation_steps": [
                f"Check rare category candidates in {target} for typographical errors, casing mismatches, or legacy codes.",
                "Determine whether rare values represent newly introduced valid operational categories.",
                "Assess whether rare categories represent legitimate niche segments.",
            ],
            "preventive_measures": [
                "Enforce enum or controlled vocabulary validation at data entry interfaces.",
                "Implement standardization and canonical mapping tables in ETL processes.",
            ],
            "caution_note": "Do not automatically recode or drop rare categories; legitimate tail events must be preserved.",
        }

    elif issue_type == "PII_EXPOSURE":
        entities = details.get("pii_entities", [])
        entities_str = ", ".join(entities) if entities else "sensitive entities"
        return {
            "summary": f"Review privacy governance and access controls for detected {entities_str} in {target}.",
            "investigation_steps": [
                f"Confirm the business justification and compliance requirements for storing {entities_str}.",
                "Inspect user access permissions, export policies, and audit logging for this dataset.",
                "Determine if the column should be anonymized, pseudonymized, or tokenized before downstream consumption.",
            ],
            "preventive_measures": [
                "Implement automated Presidio PII redaction or hashing at ingestion time.",
                "Apply column-level encryption or role-based access control (RBAC) in production storage.",
            ],
            "caution_note": "Ensure compliance with applicable privacy regulations (e.g. GDPR, CCPA, HIPAA). Never expose raw PII values.",
        }

    elif issue_type == "HIGH_RISK_COLUMN":
        domain = details.get("domain", "Sensitive Domain")
        return {
            "summary": f"Validate domain risk classification and security policies for {target} ({domain}).",
            "investigation_steps": [
                f"Review downstream usage of {target} across analytics, reporting, and model training workflows.",
                "Confirm that sensitivity classification matches data catalog governance standards.",
                "Verify that appropriate data retention and protection policies are active.",
            ],
            "preventive_measures": [
                "Tag the column in the data catalog with appropriate governance and compliance metadata.",
                "Restrict broad read permissions to authorized personnel.",
            ],
            "caution_note": "High sensitivity is an exposure indicator, not a data defect. Ensure authorized usage.",
        }

    elif issue_type == "TYPE_INCONSISTENCY":
        return {
            "summary": f"Review data type consistency and parsing rules for {target}.",
            "investigation_steps": [
                f"Inspect non-conforming values in {target} that prevented clean type inference.",
                "Check for corrupted formatting, mixed date formats, or unexpected string tokens in numeric columns.",
            ],
            "preventive_measures": [
                "Enforce strict schema typing at ingestion.",
                "Implement sanitization filters in data pipelines.",
            ],
            "caution_note": "Coercing types destructively may cause silent nullification of valid data. Verify casting rules first.",
        }

    else:
        # Default / Generic
        return {
            "summary": f"Review data quality and integrity findings for {target}.",
            "investigation_steps": [
                "Inspect the underlying records and upstream generation process.",
                "Compare findings with historical versions to determine if this represents drift.",
            ],
            "preventive_measures": [
                "Add targeted Great Expectations quality rules to monitor this condition continuously.",
            ],
            "caution_note": "Investigate root cause thoroughly before applying any remediation.",
        }


# ---------------------------------------------------------------------------
# Core Synthesis & Health Calculation Engine
# ---------------------------------------------------------------------------

def calculate_privacy_health(
    pii_result: Optional[PIIScanResult],
    total_columns: int,
) -> Tuple[float, Dict[str, Any]]:
    """
    Computes Privacy Health (0-100) using bounded exposure from Phase 6.
    Does NOT treat PII presence as a data quality failure.
    
    Formula:
    If no PII findings -> 100.0
    Otherwise:
      exposure = min(100.0, 0.60 * max_severity_weight + 40.0 * (cols_with_pii / total_cols))
      privacy_health = clamp(100.0 - exposure, 0.0, 100.0)
    """
    if not pii_result or not pii_result.findings or pii_result.total_findings == 0:
        return 100.0, {"exposure": 0.0, "pii_columns": 0, "max_severity": "NONE"}

    col_findings: Dict[str, List[PIIFinding]] = {}
    for f in pii_result.findings:
        col_findings.setdefault(f.column_name, []).append(f)

    cols_with_pii = len(col_findings)
    total_cols = max(1, total_columns)
    col_ratio = cols_with_pii / total_cols

    # Determine highest severity using approved Phase 9 privacy severity weights
    highest_weight = 0.0
    highest_sev = "NONE"
    for f in pii_result.findings:
        sev = (f.risk_level or "LOW").upper()
        weight = PRIVACY_SEVERITY_WEIGHTS.get(sev, 15.0)
        if weight > highest_weight:
            highest_weight = weight
            highest_sev = sev

    exposure = min(100.0, 0.60 * highest_weight + 40.0 * col_ratio)
    privacy_health = round(clamp(100.0 - exposure, 0.0, 100.0), 1)

    metadata = {
        "exposure": round(exposure, 1),
        "pii_columns": cols_with_pii,
        "max_severity": highest_sev,
        "total_findings": pii_result.total_findings,
    }
    return privacy_health, metadata


def synthesize_dataset_health_and_issues(
    version: DatasetVersion,
    db: Session,
) -> DatasetHealthResult:
    """
    Synthesizes upstream Phase 5, 6, 7, and 8 results to generate:
    - Holistic Dataset Health Score & Grade
    - 4-Way Health Breakdown (Quality, Risk, Anomaly, Privacy)
    - Deduplicated Data Quality Issues with deterministic priority ranking
    - Safe non-destructive remediation recommendations
    """
    total_columns = version.column_count or len(version.column_names or [])
    total_rows = version.row_count or 0

    # 1. Fetch or Auto-compute Upstream Signals
    quality_res = version.quality_result
    if not quality_res:
        logger.info(f"Phase 5 Quality result missing for version {version.id} — computing...")
        generate_quality_for_version(db=db, dataset_id=version.dataset_id, version_id=version.id, force_recompute=False)
        quality_res = db.scalar(select(QualityValidationResult).where(QualityValidationResult.dataset_version_id == version.id))

    pii_res = version.pii_result
    if not pii_res:
        logger.info(f"Phase 6 PII result missing for version {version.id} — computing...")
        generate_pii_for_version(db=db, dataset_id=version.dataset_id, version_id=version.id, force_recompute=False)
        pii_res = db.scalar(select(PIIScanResult).where(PIIScanResult.dataset_version_id == version.id))

    risk_preds = version.risk_predictions
    if not risk_preds:
        logger.info(f"Phase 7 ML Risk predictions missing for version {version.id} — computing...")
        generate_risk_predictions_for_version(db=db, dataset_id=version.dataset_id, version_id=version.id, force_recompute=False)
        risk_preds = db.scalars(select(ColumnRiskPrediction).where(ColumnRiskPrediction.dataset_version_id == version.id)).all()

    anomaly_res = version.anomaly_result
    if not anomaly_res:
        logger.info(f"Phase 8 Anomaly result missing for version {version.id} — computing...")
        anomaly_res = analyze_dataset_anomalies_for_version(db=db, dataset_id=version.dataset_id, version_id=version.id, force_recompute=False)

    # 2. Compute 4-Way Health Breakdown Components
    # Component A: Quality Health (Phase 5)
    quality_health = round(clamp(quality_res.overall_score if quality_res else 100.0), 1)

    # Component B: Risk Health (Phase 7: clamp(100.0 - mean(risk_score), 0.0, 100.0))
    if risk_preds and len(risk_preds) > 0:
        mean_risk = sum(p.risk_score for p in risk_preds) / len(risk_preds)
        risk_health = round(clamp(100.0 - mean_risk, 0.0, 100.0), 1)
    else:
        risk_health = 100.0

    # Component C: Anomaly Health (Phase 8: clamp(100.0 - dataset_anomaly_score, 0.0, 100.0))
    if anomaly_res:
        anomaly_health = round(clamp(100.0 - anomaly_res.dataset_anomaly_score, 0.0, 100.0), 1)
    else:
        anomaly_health = 100.0

    # Component D: Privacy Health (Phase 6 bounded exposure)
    privacy_health, privacy_meta = calculate_privacy_health(pii_res, total_columns)

    # 3. Overall Dataset Health Score (0-100)
    health_score = round(
        clamp(
            0.60 * quality_health
            + 0.15 * risk_health
            + 0.15 * anomaly_health
            + 0.10 * privacy_health,
            0.0,
            100.0,
        ),
        1,
    )
    health_grade = calculate_health_grade(health_score)

    # 4. Map upstream column contexts for cross-signal & sensitivity lookups
    column_context: Dict[str, Dict[str, Any]] = {}
    for col in (version.column_names or []):
        column_context[col] = {
            "domain": "General / Other",
            "risk_score": 0.0,
            "risk_level": "LOW",
            "pii_entities": [],
            "pii_findings_count": 0,
            "quality_failures": [],
            "anomaly_findings": [],
            "signals": set(),
        }

    # Populate Phase 7 Risk context
    if risk_preds:
        for p in risk_preds:
            if p.column_name in column_context:
                column_context[p.column_name]["domain"] = p.predicted_domain
                column_context[p.column_name]["risk_score"] = p.risk_score
                column_context[p.column_name]["risk_level"] = p.risk_level
                if p.risk_score >= 60.0 or p.risk_level in ["HIGH", "CRITICAL"]:
                    column_context[p.column_name]["signals"].add("RISK")

    # Populate Phase 6 PII context (Zero raw PII stored!)
    if pii_res and pii_res.findings:
        for f in pii_res.findings:
            if f.column_name in column_context:
                if f.entity_type not in column_context[f.column_name]["pii_entities"]:
                    column_context[f.column_name]["pii_entities"].append(f.entity_type)
                column_context[f.column_name]["pii_findings_count"] += 1
                column_context[f.column_name]["signals"].add("PII")

    # Populate Phase 5 Quality context
    if quality_res and quality_res.expectations:
        for exp in quality_res.expectations:
            if not exp.success:
                col = exp.column_name
                if col and col in column_context:
                    column_context[col]["quality_failures"].append(exp)
                    column_context[col]["signals"].add("QUALITY")

    # Populate Phase 8 Anomaly context
    if anomaly_res and anomaly_res.findings:
        for af in anomaly_res.findings:
            if af.column_name in column_context:
                column_context[af.column_name]["anomaly_findings"].append(af)
                column_context[af.column_name]["signals"].add("ANOMALY")

    # 5. Extract & Deduplicate Logical Issues
    generated_issues: List[DataQualityIssue] = []
    affected_columns_set = set()

    # --- Group A: Phase 5 Quality Rule Failures ---
    if quality_res and quality_res.expectations:
        # Handle dataset-wide duplicates expectation
        dup_exp = next(
            (e for e in quality_res.expectations if "duplicate" in (e.expectation_type or "").lower() and not e.success),
            None,
        )
        if dup_exp:
            det = dup_exp.details or {}
            dup_count = det.get("duplicate_count", 0)
            dup_pct = det.get("duplicate_percentage", 0.0)
            sev = "HIGH" if dup_pct >= 5.0 else "MEDIUM"
            p_score, s_sc, a_sc, c_sc, e_sc = calculate_priority_score(
                severity=sev,
                affected_percentage=dup_pct,
                data_sensitivity=20.0,
                confidence_heuristic=95.0,
                cross_signal_count=1,
            )
            rec = generate_remediation_recommendation("DUPLICATES", None, {"dup_count": dup_count})
            issue = DataQualityIssue(
                dataset_version_id=version.id,
                column_name=None,
                issue_type="DUPLICATES",
                source="QUALITY",
                severity=sev,
                priority_score=p_score,
                title="Duplicate Records Detected",
                description=f"{dup_count} duplicate rows ({dup_pct:.2f}% of dataset) detected across records.",
                affected_rows=int(dup_count),
                affected_percentage=float(dup_pct),
                sensitivity_score=20.0,
                confidence_score=95.0,
                evidence_score=e_sc,
                risk_context={"scope": "dataset_wide"},
                evidence={"rule_name": dup_exp.expectation_type, "category": dup_exp.category, "observed": dup_exp.observed_value, "details": det},
                recommendation=rec,
            )
            generated_issues.append(issue)

        # Handle column-specific quality failures (Deduplicate per column & issue_type)
        col_quality_groups: Dict[Tuple[str, str], List[QualityExpectationResult]] = {}
        for exp in quality_res.expectations:
            if not exp.success and exp.column_name:
                col = exp.column_name
                affected_columns_set.add(col)
                # Map rule to logical issue type
                exp_type_lower = (exp.expectation_type or "").lower()
                if "null" in exp_type_lower or "missing" in exp_type_lower:
                    itype = "MISSING_VALUES"
                elif "type" in exp_type_lower:
                    itype = "TYPE_INCONSISTENCY"
                else:
                    itype = "QUALITY_RULE_VIOLATION"
                col_quality_groups.setdefault((col, itype), []).append(exp)

        for (col, itype), exps in col_quality_groups.items():
            ctx = column_context.get(col, {})
            domain = ctx.get("domain", "General / Other")
            data_sens = DOMAIN_SENSITIVITY_MAP.get(domain, 20.0)
            if ctx.get("pii_entities"):
                data_sens = max(data_sens, 75.0)

            # Determine affected rows / percentage from details
            max_aff_pct = 0.0
            max_aff_rows = 0
            for e in exps:
                det = e.details or {}
                pct = det.get("missing_percentage", det.get("unexpected_percent", 0.0))
                cnt = det.get("missing_count", det.get("unexpected_count", 0))
                if pct > max_aff_pct:
                    max_aff_pct = float(pct)
                if cnt > max_aff_rows:
                    max_aff_rows = int(cnt)

            # Severity mapping from quality failure magnitude
            if max_aff_pct >= 20.0:
                sev = "HIGH"
            elif max_aff_pct >= 5.0:
                sev = "MEDIUM"
            else:
                sev = "LOW"

            cross_signals = len(ctx.get("signals", set()))
            p_score, s_sc, a_sc, c_sc, e_sc = calculate_priority_score(
                severity=sev,
                affected_percentage=max_aff_pct,
                data_sensitivity=data_sens,
                confidence_heuristic=95.0,  # Formal quality rule has high confidence
                cross_signal_count=cross_signals,
            )

            title = f"High Missing Values in '{col}'" if itype == "MISSING_VALUES" else f"Quality Rule Violation in '{col}'"
            desc = (
                f"Column '{col}' has {max_aff_pct:.1f}% missing values ({max_aff_rows} rows)."
                if itype == "MISSING_VALUES"
                else f"Column '{col}' failed {len(exps)} quality validation rule(s)."
            )
            rec = generate_remediation_recommendation(
                itype, col, {"missing_pct": max_aff_pct, "failed_rules": [e.expectation_type for e in exps]}, cross_signals > 1
            )

            issue = DataQualityIssue(
                dataset_version_id=version.id,
                column_name=col,
                issue_type=itype,
                source="QUALITY",
                severity=sev,
                priority_score=p_score,
                title=title,
                description=desc,
                affected_rows=int(max_aff_rows),
                affected_percentage=float(max_aff_pct),
                sensitivity_score=data_sens,
                confidence_score=95.0,
                evidence_score=e_sc,
                risk_context={
                    "domain": domain,
                    "risk_score": ctx.get("risk_score", 0.0),
                    "pii_entities": ctx.get("pii_entities", []),
                },
                evidence={
                    "failed_rules": [e.expectation_type for e in exps],
                    "categories": list(set(e.category for e in exps)),
                    "observed": [e.observed_value for e in exps],
                    "details": [e.details for e in exps],
                },
                recommendation=rec,
            )
            generated_issues.append(issue)

    # --- Group B: Phase 6 Presidio PII Exposures (Deduplicated per column) ---
    if pii_res and pii_res.findings:
        col_pii: Dict[str, List[PIIFinding]] = {}
        for f in pii_res.findings:
            col_pii.setdefault(f.column_name, []).append(f)
            affected_columns_set.add(f.column_name)

        for col, f_list in col_pii.items():
            ctx = column_context.get(col, {})
            domain = ctx.get("domain", "General / Other")
            data_sens = DOMAIN_SENSITIVITY_MAP.get(domain, 60.0)
            data_sens = max(data_sens, 75.0)

            # Determine highest risk level among PII findings
            highest_sev = "LOW"
            highest_weight = 15.0
            entity_types = []
            max_conf = 0.80
            for f in f_list:
                if f.entity_type not in entity_types:
                    entity_types.append(f.entity_type)
                f_sev = (f.risk_level or "LOW").upper()
                w = PRIVACY_SEVERITY_WEIGHTS.get(f_sev, 15.0)
                if w > highest_weight:
                    highest_weight = w
                    highest_sev = f_sev
                if f.confidence and f.confidence > max_conf:
                    max_conf = f.confidence

            # Estimated affected percentage
            aff_count = len(f_list)
            aff_pct = (aff_count / max(1, total_rows)) * 100.0 if total_rows > 0 else 10.0
            aff_pct = min(100.0, aff_pct)

            cross_signals = len(ctx.get("signals", set()))
            conf_heuristic = round(max_conf * 100.0, 1)
            p_score, s_sc, a_sc, c_sc, e_sc = calculate_priority_score(
                severity=highest_sev,
                affected_percentage=aff_pct,
                data_sensitivity=data_sens,
                confidence_heuristic=conf_heuristic,
                cross_signal_count=cross_signals,
            )

            entities_label = ", ".join(entity_types)
            rec = generate_remediation_recommendation(
                "PII_EXPOSURE", col, {"pii_entities": entity_types, "count": len(f_list)}, cross_signals > 1
            )

            issue = DataQualityIssue(
                dataset_version_id=version.id,
                column_name=col,
                issue_type="PII_EXPOSURE",
                source="PII",
                severity=highest_sev,
                priority_score=p_score,
                title=f"Sensitive PII Detected in '{col}' ({entities_label})",
                description=f"Column '{col}' contains {len(f_list)} detected PII entity match(es) ({entities_label}).",
                affected_rows=int(aff_count),
                affected_percentage=float(round(aff_pct, 2)),
                sensitivity_score=data_sens,
                confidence_score=conf_heuristic,
                evidence_score=e_sc,
                risk_context={
                    "domain": domain,
                    "risk_score": ctx.get("risk_score", 0.0),
                    "pii_entities": entity_types,
                },
                evidence={
                    "pii_entities": entity_types,
                    "finding_count": len(f_list),
                    "max_confidence": max_conf,
                    "severities": [f.risk_level for f in f_list],
                },
                recommendation=rec,
            )
            generated_issues.append(issue)

    # --- Group C: Phase 8 Anomaly Findings (Deduplicated per column) ---
    if anomaly_res and anomaly_res.findings:
        for af in anomaly_res.findings:
            col = af.column_name
            affected_columns_set.add(col)
            ctx = column_context.get(col, {})
            domain = ctx.get("domain", "General / Other")
            data_sens = DOMAIN_SENSITIVITY_MAP.get(domain, 20.0)
            if ctx.get("pii_entities"):
                data_sens = max(data_sens, 75.0)

            # Preserve upstream severity and score
            sev = (af.severity or "LOW").upper()
            aff_count = af.anomaly_count or 0
            aff_pct = af.anomaly_rate or 0.0

            # Confidence heuristic: multiple agreeing detectors -> higher evidence strength
            # (Heuristic agreement, not calibrated proof)
            ev = af.evidence or {}
            methods = ev.get("detected_methods", [af.detection_method])
            num_methods = len(methods)
            conf_heuristic = calculate_anomaly_confidence_heuristic(num_methods)

            cross_signals = len(ctx.get("signals", set()))
            p_score, s_sc, a_sc, c_sc, e_sc = calculate_priority_score(
                severity=sev,
                affected_percentage=aff_pct,
                data_sensitivity=data_sens,
                confidence_heuristic=conf_heuristic,
                cross_signal_count=cross_signals,
            )

            itype = "RARE_CATEGORY" if af.detection_method == "CATEGORICAL_FREQUENCY" else "ANOMALY"
            title = (
                f"Rare Category Distribution in '{col}'"
                if itype == "RARE_CATEGORY"
                else f"Statistical Anomalies in '{col}' ({', '.join(methods)})"
            )
            desc = (
                f"Column '{col}' contains {aff_count} rare category observations ({aff_pct:.2f}% of column)."
                if itype == "RARE_CATEGORY"
                else f"Column '{col}' contains {aff_count} outlier observations ({aff_pct:.2f}% of column) detected via {', '.join(methods)}."
            )
            rec = generate_remediation_recommendation(
                itype, col, {"detected_methods": methods, "count": aff_count}, cross_signals > 1
            )

            issue = DataQualityIssue(
                dataset_version_id=version.id,
                column_name=col,
                issue_type=itype,
                source="ANOMALY",
                severity=sev,
                priority_score=p_score,
                title=title,
                description=desc,
                affected_rows=int(aff_count),
                affected_percentage=float(round(aff_pct, 2)),
                sensitivity_score=data_sens,
                confidence_score=conf_heuristic,
                evidence_score=e_sc,
                risk_context={
                    "domain": domain,
                    "risk_score": ctx.get("risk_score", 0.0),
                    "pii_entities": ctx.get("pii_entities", []),
                },
                evidence={
                    "detected_methods": methods,
                    "primary_method": af.detection_method,
                    "anomaly_score": af.score,
                    "statistical_summary": af.statistical_summary,
                    "detector_evidence": ev,
                    "explanation": af.explanation,
                },
                recommendation=rec,
            )
            generated_issues.append(issue)

    # --- Group D: Phase 7 High-Risk Standalone Columns ---
    # If a column is CRITICAL / HIGH risk from Phase 7 (score >= 70.0) but has no PII or Quality issue flagged,
    # generate a HIGH_RISK_COLUMN issue for awareness.
    if risk_preds:
        for p in risk_preds:
            col = p.column_name
            if p.risk_score >= 70.0 and p.risk_level in ["HIGH", "CRITICAL"]:
                # Check if already covered by PII issue
                has_pii_issue = any(i.column_name == col and i.issue_type == "PII_EXPOSURE" for i in generated_issues)
                if not has_pii_issue:
                    affected_columns_set.add(col)
                    ctx = column_context.get(col, {})
                    domain = p.predicted_domain or "Sensitive Domain"
                    data_sens = DOMAIN_SENSITIVITY_MAP.get(domain, 75.0)
                    cross_signals = len(ctx.get("signals", set()))

                    p_score, s_sc, a_sc, c_sc, e_sc = calculate_priority_score(
                        severity=p.risk_level,
                        affected_percentage=100.0,
                        data_sensitivity=data_sens,
                        confidence_heuristic=round(p.model_confidence * 100.0, 1) if p.model_confidence else 75.0,
                        cross_signal_count=cross_signals,
                    )
                    rec = generate_remediation_recommendation("HIGH_RISK_COLUMN", col, {"domain": domain}, cross_signals > 1)
                    issue = DataQualityIssue(
                        dataset_version_id=version.id,
                        column_name=col,
                        issue_type="HIGH_RISK_COLUMN",
                        source="RISK",
                        severity=p.risk_level,
                        priority_score=p_score,
                        title=f"Elevated Data Risk in '{col}' ({domain})",
                        description=f"Column '{col}' is classified as {domain} with an elevated risk score of {p.risk_score:.1f}/100.",
                        affected_rows=total_rows,
                        affected_percentage=100.0,
                        sensitivity_score=data_sens,
                        confidence_score=round(p.model_confidence * 100.0, 1) if p.model_confidence else 75.0,
                        evidence_score=e_sc,
                        risk_context={
                            "domain": domain,
                            "risk_score": p.risk_score,
                            "risk_level": p.risk_level,
                            "model_confidence": p.model_confidence,
                        },
                        evidence={
                            "risk_score": p.risk_score,
                            "risk_level": p.risk_level,
                            "risk_drivers": p.risk_drivers,
                            "domain_probabilities": p.domain_probabilities,
                        },
                        recommendation=rec,
                    )
                    generated_issues.append(issue)

    # 6. Sort issues by Priority Score descending
    generated_issues.sort(key=lambda x: (x.priority_score, x.severity), reverse=True)

    # Count issues by severity
    crit_count = sum(1 for i in generated_issues if i.severity == "CRITICAL")
    high_count = sum(1 for i in generated_issues if i.severity == "HIGH")
    med_count = sum(1 for i in generated_issues if i.severity == "MEDIUM")
    low_count = sum(1 for i in generated_issues if i.severity == "LOW")

    # 7. Construct Column Health Matrix
    column_health_matrix: List[Dict[str, Any]] = []
    dtypes_map = version.column_dtypes or {}
    for col in (version.column_names or []):
        ctx = column_context.get(col, {})
        col_issues = [i for i in generated_issues if i.column_name == col]
        highest_p = max([i.priority_score for i in col_issues], default=0.0)
        af_list = ctx.get("anomaly_findings", [])
        anom_detected = len(af_list) > 0
        anom_sev = af_list[0].severity if anom_detected else "NONE"
        anom_sc = af_list[0].score if anom_detected else 0.0

        item = {
            "column_name": col,
            "data_type": dtypes_map.get(col, "unknown"),
            "quality_status": "VIOLATION" if len(ctx.get("quality_failures", [])) > 0 else "CLEAN",
            "quality_issues_count": len(ctx.get("quality_failures", [])),
            "pii_detected": len(ctx.get("pii_entities", [])) > 0,
            "pii_entities": ctx.get("pii_entities", []),
            "risk_level": ctx.get("risk_level", "LOW"),
            "risk_score": ctx.get("risk_score", 0.0),
            "domain": ctx.get("domain", "General / Other"),
            "anomaly_detected": anom_detected,
            "anomaly_severity": anom_sev,
            "anomaly_score": anom_sc,
            "issue_count": len(col_issues),
            "highest_priority": highest_p,
            "cross_signal_count": len(ctx.get("signals", set())),
        }
        column_health_matrix.append(item)

    # Sort column health matrix by highest priority desc, cross signals desc
    column_health_matrix.sort(key=lambda x: (x["highest_priority"], x["cross_signal_count"]), reverse=True)

    # 8. Create and Persist DatasetHealthResult & DataQualityIssues
    summary_data = {
        "total_columns_evaluated": total_columns,
        "columns_affected_count": len(affected_columns_set),
        "columns_clean_count": max(0, total_columns - len(affected_columns_set)),
        "privacy_metadata": privacy_meta,
        "top_drivers": [i.title for i in generated_issues[:5]],
        "column_health_matrix": column_health_matrix,
    }

    health_result = DatasetHealthResult(
        dataset_version_id=version.id,
        health_score=health_score,
        health_grade=health_grade,
        quality_health=quality_health,
        risk_health=risk_health,
        anomaly_health=anomaly_health,
        privacy_health=privacy_health,
        total_issues=len(generated_issues),
        critical_issues=crit_count,
        high_issues=high_count,
        medium_issues=med_count,
        low_issues=low_count,
        summary=summary_data,
    )

    db.add(health_result)
    db.flush()  # Populate health_result.id

    for issue in generated_issues:
        issue.dataset_health_result_id = health_result.id
    try:
        db.commit()
        db.refresh(health_result)
        logger.info(
            f"Phase 9 Health & Prioritization complete for Version {version.id}: "
            f"Score={health_score:.1f} ({health_grade}), Issues={len(generated_issues)}"
        )
        return health_result
    except IntegrityError:
        db.rollback()
        logger.info(f"Concurrent health analysis write detected for version {version.id}; fetching existing record.")
        existing = db.scalar(
            select(DatasetHealthResult).where(DatasetHealthResult.dataset_version_id == version.id)
        )
        if existing:
            return existing
        raise


def analyze_and_save_dataset_health(
    version: DatasetVersion,
    db: Session,
    force: bool = False,
) -> DatasetHealthResult:
    """
    Entrypoint to analyze dataset health and prioritized issues.
    Honors caching unless force=True.
    """
    if not force and version.health_result:
        logger.info(f"Returning cached DatasetHealthResult for version {version.id}")
        return version.health_result

    if force and version.health_result:
        logger.info(f"force_recompute=True: Purging existing health result for version {version.id}")
        db.execute(
            delete(DatasetHealthResult).where(DatasetHealthResult.dataset_version_id == version.id)
        )
        db.commit()

    return synthesize_dataset_health_and_issues(version, db)
