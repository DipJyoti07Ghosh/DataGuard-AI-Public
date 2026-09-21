"""
DataGuard AI — Phase 13 Dashboard Aggregation Service

Read-only presentation aggregation service over Phase 4-10 stored results.
Never re-analyzes, modifies, or recalculates upstream analytics.
Strictly redacts all raw PII and dataset cell contents.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.dataset import Dataset, DatasetVersion
from app.models.profiling import ProfilingResult
from app.models.quality import QualityValidationResult, QualityExpectationResult
from app.models.pii import PIIScanResult, PIIFinding

from app.models.risk import ColumnRiskPrediction
from app.models.anomaly import AnomalyDetectionResult, AnomalyFinding
from app.models.issues import DatasetHealthResult, DataQualityIssue

from app.models.comparison import DatasetComparison, ColumnDriftResult
from app.schemas.dashboard import (
    DashboardResponse,
    DashboardDatasetInfo,
    DashboardVersionInfo,
    DashboardVersionOption,
    DashboardHealthSummary,
    DashboardQualitySummary,
    QualityFailedRule,
    DashboardRiskSummary,
    ColumnRiskItem,
    DashboardPrivacySummary,
    PIICategoryItem,
    PIIColumnItem,
    DashboardAnomalySummary,
    AnomalyColumnItem,
    DashboardIssuesSummary,
    DashboardIssueItem,
    DashboardProfilingSummary,
    ColumnMissingnessItem,
    DashboardDriftSummary,
    ColumnDriftItem,
    DashboardTrendsSummary,
    DashboardVersionTrendItem,
    AttentionColumn,
    DashboardInsight,
)

logger = logging.getLogger(__name__)


def get_dataset_version_dashboard(
    dataset_id: uuid.UUID,
    version_id: Optional[uuid.UUID],
    db: Session,
) -> Optional[DashboardResponse]:
    """
    Fetch and aggregate stored analysis results for a specific dataset version snapshot.
    Returns None if the dataset or version does not exist.
    """
    # 1. Verify Dataset
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        logger.warning(f"Dataset {dataset_id} not found for dashboard.")
        return None

    # 2. Fetch all versions ordered by version_number asc
    versions = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.asc())
        .all()
    )
    if not versions:
        logger.warning(f"No versions found for dataset {dataset_id}.")
        return None

    version_options = [
        DashboardVersionOption(
            id=str(v.id),
            version_number=v.version_number,
            created_at=getattr(v, "uploaded_at", getattr(v, "created_at", None)),
        )
        for v in versions
    ]


    # Map version ID to version number for quick lookup
    version_num_map = {str(v.id): v.version_number for v in versions}

    # 3. Select active version
    active_version = None
    if version_id:
        for v in versions:
            if str(v.id) == str(version_id):
                active_version = v
                break
    if not active_version:
        # Default to latest version
        active_version = versions[-1]

    active_vid = active_version.id

    # -----------------------------------------------------------------------
    # Phase 9: Dataset Health
    # -----------------------------------------------------------------------
    health_row = (
        db.query(DatasetHealthResult)
        .filter(DatasetHealthResult.dataset_version_id == active_vid)
        .first()
    )
    if health_row:
        health_summary = DashboardHealthSummary(
            available=True,
            dataset_health_score=round(float(health_row.health_score), 1),
            grade=health_row.health_grade,
            quality_health=round(float(health_row.quality_health), 1),
            risk_health=round(float(health_row.risk_health), 1),
            anomaly_health=round(float(health_row.anomaly_health), 1),
            privacy_health=round(float(health_row.privacy_health), 1),
            computed_at=health_row.calculated_at,
        )
    else:
        health_summary = DashboardHealthSummary(available=False)

    # -----------------------------------------------------------------------
    # Phase 5: Data Quality
    # -----------------------------------------------------------------------
    quality_row = (
        db.query(QualityValidationResult)
        .filter(QualityValidationResult.dataset_version_id == active_vid)
        .first()
    )
    if quality_row:
        total_eval = quality_row.total_expectations or 0
        status_eval = "NOT_EVALUATED" if total_eval == 0 else "EVALUATED"
        grade_eval = "UNKNOWN" if total_eval == 0 else (
            "EXCELLENT" if quality_row.overall_score >= 90 else
            "GOOD" if quality_row.overall_score >= 75 else
            "NEEDS ATTENTION" if quality_row.overall_score >= 50 else "POOR"
        )

        failed_rules_list = []
        if quality_row.expectations:
            for exp in quality_row.expectations:
                if not exp.success:
                    obs = exp.observed_value or exp.failure_message
                    details_str = str(obs) if obs is not None else None
                    failed_rules_list.append(
                        QualityFailedRule(
                            rule_name=exp.expectation_type,
                            column_name=exp.column_name,
                            severity="HIGH" if "not_be_null" in exp.expectation_type or "unique" in exp.expectation_type else "MEDIUM",
                            status="Failed",
                            details=details_str,
                        )
                    )


        categories_data = {}
        if quality_row.summary and isinstance(quality_row.summary, dict):
            categories_data = quality_row.summary.get("categories", {})

        quality_summary = DashboardQualitySummary(
            available=True,
            quality_score=round(float(quality_row.overall_score), 1),
            grade=grade_eval,
            status=status_eval,
            total_rules_evaluated=total_eval,
            passed_rules=quality_row.passed_expectations or 0,
            failed_rules=quality_row.failed_expectations or 0,
            categories=categories_data,
            failed_expectations=failed_rules_list,
            computed_at=quality_row.evaluated_at,
        )
    else:
        quality_summary = DashboardQualitySummary(available=False)

    # -----------------------------------------------------------------------
    # Phase 7: Column Risk
    # -----------------------------------------------------------------------
    risk_rows = (
        db.query(ColumnRiskPrediction)
        .filter(ColumnRiskPrediction.dataset_version_id == active_vid)
        .order_by(desc(ColumnRiskPrediction.risk_score))
        .all()
    )
    if risk_rows:
        high_c = sum(1 for r in risk_rows if (r.risk_level or "").upper() == "HIGH")
        med_c = sum(1 for r in risk_rows if (r.risk_level or "").upper() == "MEDIUM")
        low_c = sum(1 for r in risk_rows if (r.risk_level or "").upper() == "LOW")

        col_risks = [
            ColumnRiskItem(
                column_name=r.column_name,
                domain=r.predicted_domain,
                risk_level=(r.risk_level or "LOW").upper(),
                risk_score=round(float(r.risk_score), 1),
                confidence=round(float(r.model_confidence), 2) if r.model_confidence is not None else None,

            )
            for r in risk_rows
        ]

        risk_summary = DashboardRiskSummary(
            available=True,
            columns_analyzed=len(risk_rows),
            high_count=high_c,
            medium_count=med_c,
            low_count=low_c,
            distribution=[
                {"name": "HIGH", "count": high_c, "color": "#ef4444"},
                {"name": "MEDIUM", "count": med_c, "color": "#f59e0b"},
                {"name": "LOW", "count": low_c, "color": "#10b981"},
            ],
            column_risks=col_risks,
            computed_at=risk_rows[0].predicted_at if hasattr(risk_rows[0], "predicted_at") else None,
        )
    else:
        risk_summary = DashboardRiskSummary(available=False)

    # -----------------------------------------------------------------------
    # Phase 6: Privacy / PII Scan (Strictly no raw PII strings)
    # -----------------------------------------------------------------------
    pii_row = (
        db.query(PIIScanResult)
        .filter(PIIScanResult.dataset_version_id == active_vid)
        .first()
    )
    if pii_row:
        # Build detected categories aggregated by entity type
        findings_rows = (
            db.query(PIIFinding)
            .filter(PIIFinding.scan_id == pii_row.id)
            .all()
        )
        cat_counts: Dict[str, Dict[str, Any]] = {}
        col_map: Dict[str, Dict[str, Any]] = {}
        highest_sev = "LOW"

        for f in findings_rows:
            etype = f.entity_type
            f_count = f.detected_count or 1
            f_risk = (f.risk_level or "LOW").upper()

            if f_risk in ("CRITICAL", "HIGH"):
                highest_sev = "HIGH"
            elif f_risk == "MEDIUM" and highest_sev != "HIGH":
                highest_sev = "MEDIUM"

            if etype not in cat_counts:
                cat_counts[etype] = {"count": 0, "severity": f_risk, "confidence": f.confidence}
            cat_counts[etype]["count"] += f_count

            cname = f.column_name
            if cname not in col_map:
                col_map[cname] = {"entities": set(), "severity": f_risk, "findings_count": 0}
            col_map[cname]["entities"].add(etype)
            col_map[cname]["findings_count"] += f_count
            if f_risk == "HIGH" or (f_risk == "MEDIUM" and col_map[cname]["severity"] != "HIGH"):
                col_map[cname]["severity"] = f_risk

        detected_cats = [
            PIICategoryItem(
                category=k,
                count=v["count"],
                severity=v["severity"],
                confidence=round(float(v["confidence"]), 2) if v["confidence"] else None,
            )
            for k, v in cat_counts.items()
        ]

        col_privacy_list = [
            PIIColumnItem(
                column_name=cname,
                entity_types=list(cdata["entities"]),
                highest_severity=cdata["severity"],
                findings_count=cdata["findings_count"],
            )
            for cname, cdata in col_map.items()
        ]

        privacy_summary = DashboardPrivacySummary(
            available=True,
            pii_columns_count=pii_row.pii_columns_count or len(col_privacy_list),
            total_findings_count=pii_row.total_findings or sum(c.count for c in detected_cats),
            highest_severity=highest_sev if findings_rows else "LOW",
            detected_categories=detected_cats,
            columns=col_privacy_list,
            computed_at=pii_row.scanned_at,
        )
    else:
        privacy_summary = DashboardPrivacySummary(available=False)


    # -----------------------------------------------------------------------
    # Phase 8: Anomaly Detection (Strictly no raw anomalous values)
    # -----------------------------------------------------------------------
    anomaly_row = (
        db.query(AnomalyDetectionResult)
        .filter(AnomalyDetectionResult.dataset_version_id == active_vid)
        .first()
    )
    if anomaly_row:
        col_anomalies_rows = (
            db.query(AnomalyFinding)
            .filter(AnomalyFinding.detection_result_id == anomaly_row.id)
            .all()
        )
        anom_cols_list = []
        sev_dist: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        detector_dist: Dict[str, int] = {}

        for ca in col_anomalies_rows:
            if ca.anomaly_count and ca.anomaly_count > 0:
                sev = (ca.severity or "LOW").upper()
                if sev in ("CRITICAL", "HIGH"):
                    sev_dist["HIGH"] = sev_dist.get("HIGH", 0) + 1
                elif sev == "MEDIUM":
                    sev_dist["MEDIUM"] = sev_dist.get("MEDIUM", 0) + 1
                else:
                    sev_dist["LOW"] = sev_dist.get("LOW", 0) + 1

                det = ca.detection_method or "statistical"
                detector_dist[det] = detector_dist.get(det, 0) + 1

                anom_cols_list.append(
                    AnomalyColumnItem(
                        column_name=ca.column_name,
                        detector_method=ca.detection_method or "Statistical",
                        severity=sev,
                        anomaly_rate=round(float(ca.anomaly_rate or 0.0), 2),
                        anomaly_count=ca.anomaly_count or 0,
                    )
                )

        # Sort anomalous columns by anomaly_rate desc
        anom_cols_list.sort(key=lambda x: x.anomaly_rate, reverse=True)

        detector_methods_list = [
            {"method": k, "count": v} for k, v in detector_dist.items()
        ]

        anomaly_summary = DashboardAnomalySummary(
            available=True,
            anomalous_columns_count=anomaly_row.columns_with_anomalies or len(anom_cols_list),
            total_anomalies_count=anomaly_row.total_anomalies or sum(c.anomaly_count for c in anom_cols_list),
            dataset_anomaly_score=round(float(anomaly_row.dataset_anomaly_score or 0.0), 1),
            detector_methods=detector_methods_list,
            severity_distribution=sev_dist,
            anomalous_columns=anom_cols_list,
            computed_at=anomaly_row.analyzed_at,
        )
    else:
        anomaly_summary = DashboardAnomalySummary(available=False)


    # -----------------------------------------------------------------------
    # Phase 9: Prioritized Issues
    # -----------------------------------------------------------------------
    issue_rows = (
        db.query(DataQualityIssue)
        .filter(DataQualityIssue.dataset_version_id == active_vid)
        .order_by(desc(DataQualityIssue.priority_score))
        .all()
    )
    if issue_rows:
        high_p = sum(1 for i in issue_rows if (i.severity or "").upper() in ("HIGH", "CRITICAL"))
        med_p = sum(1 for i in issue_rows if (i.severity or "").upper() == "MEDIUM")
        low_p = sum(1 for i in issue_rows if (i.severity or "").upper() == "LOW")

        p_issues = [
            DashboardIssueItem(
                id=str(i.id),
                title=i.title,
                issue_type=i.issue_type,
                severity=(i.severity or "MEDIUM").upper(),
                priority_score=round(float(i.priority_score), 1),
                affected_columns=[i.column_name] if i.column_name else [],
                category=i.source,
                status="OPEN",
            )
            for i in issue_rows
        ]

        issues_summary = DashboardIssuesSummary(
            available=True,
            total_issues=len(issue_rows),
            high_priority_count=high_p,
            medium_priority_count=med_p,
            low_priority_count=low_p,
            prioritized_issues=p_issues,
            computed_at=getattr(issue_rows[0], "created_at", None),
        )

    else:
        issues_summary = DashboardIssuesSummary(available=False)

    # -----------------------------------------------------------------------
    # Phase 4: Profiling & Missingness
    # -----------------------------------------------------------------------
    profiling_row = (
        db.query(ProfilingResult)
        .filter(ProfilingResult.dataset_version_id == active_vid)
        .first()
    )
    if profiling_row:
        # Extract column profiles for missingness
        missing_list = []
        col_dists = {}
        if profiling_row.column_profiles and isinstance(profiling_row.column_profiles, dict):
            for col_name, cdata in profiling_row.column_profiles.items():
                if isinstance(cdata, dict):
                    dtype = cdata.get("inferred_type") or cdata.get("dtype") or "unknown"
                    m_count = cdata.get("missing_count", 0)
                    m_pct = cdata.get("missing_percentage", 0.0)
                    if m_count > 0 or m_pct > 0:
                        missing_list.append(
                            ColumnMissingnessItem(
                                column_name=col_name,
                                data_type=str(dtype),
                                missing_count=int(m_count),
                                missing_percentage=round(float(m_pct), 2),
                            )
                        )
                    # Histograms / distributions
                    if "histogram" in cdata and cdata["histogram"]:
                        col_dists[col_name] = cdata["histogram"]

        missing_list.sort(key=lambda x: x.missing_percentage, reverse=True)

        profiling_summary = DashboardProfilingSummary(
            available=True,
            row_count=profiling_row.row_count or 0,
            column_count=profiling_row.column_count or 0,
            numeric_columns_count=profiling_row.numeric_columns_count or 0,
            categorical_columns_count=profiling_row.categorical_columns_count or 0,
            total_missing_cells=profiling_row.missing_cells or 0,
            missing_percentage=round(float(profiling_row.missing_cells_percentage or 0.0), 2),
            duplicate_rows=profiling_row.duplicate_rows or 0,
            duplicate_percentage=round(float(profiling_row.duplicate_rows_percentage or 0.0), 2),
            top_missing_columns=missing_list[:10],
            column_distributions=col_dists,
            computed_at=profiling_row.created_at if hasattr(profiling_row, "created_at") else None,
        )
    else:
        profiling_summary = DashboardProfilingSummary(available=False)

    # -----------------------------------------------------------------------
    # Phase 10: Drift & Version Comparison
    # -----------------------------------------------------------------------
    comparison_row = (
        db.query(DatasetComparison)
        .filter(DatasetComparison.current_version_id == active_vid)
        .order_by(desc(DatasetComparison.created_at if hasattr(DatasetComparison, "created_at") else DatasetComparison.id))
        .first()
    )
    if comparison_row:
        drift_rows = (
            db.query(ColumnDriftResult)
            .filter(ColumnDriftResult.comparison_id == comparison_row.id)
            .all()
        )
        drift_items = []
        for cd in drift_rows:
            sev = (cd.drift_status or "NO_DRIFT").replace("_DRIFT", "")
            dtype = "Statistical" if cd.statistical_comparison else ("Missingness" if cd.missingness_comparison else "Schema")
            stat_comp = cd.statistical_comparison or {}
            drift_items.append(
                ColumnDriftItem(
                    column_name=cd.column_name,
                    drift_type=dtype,
                    severity=sev if sev else "LOW",
                    metric_name=stat_comp.get("test_name", "Distribution"),
                    drift_score=round(float(stat_comp["test_statistic"]), 4) if "test_statistic" in stat_comp else None,
                    p_value=round(float(stat_comp["p_value"]), 4) if "p_value" in stat_comp else None,
                )
            )

        b_num = version_num_map.get(str(comparison_row.baseline_version_id))
        c_num = version_num_map.get(str(comparison_row.current_version_id), active_version.version_number)


        drift_summary = DashboardDriftSummary(
            available=True,
            has_comparison=True,
            comparison_id=str(comparison_row.id),
            baseline_version_id=str(comparison_row.baseline_version_id),
            baseline_version_number=b_num,
            current_version_id=str(comparison_row.current_version_id),
            current_version_number=c_num,
            overall_drift_severity=comparison_row.overall_drift_status or "NO_DRIFT",
            drift_score=round(float(comparison_row.drift_score), 3) if hasattr(comparison_row, "drift_score") and comparison_row.drift_score is not None else None,
            drifted_columns_count=len([d for d in drift_items if d.severity.upper() in ("HIGH", "MEDIUM")]),
            column_drifts=drift_items,
            computed_at=comparison_row.compared_at if hasattr(comparison_row, "compared_at") else None,
        )
    else:
        drift_summary = DashboardDriftSummary(
            available=True,
            has_comparison=False,
        )

    # -----------------------------------------------------------------------
    # Historical Version Health Trends
    # -----------------------------------------------------------------------
    trend_items: List[DashboardVersionTrendItem] = []
    for v in versions:
        vh = (
            db.query(DatasetHealthResult)
            .filter(DatasetHealthResult.dataset_version_id == v.id)
            .first()
        )
        if vh:
            trend_items.append(
                DashboardVersionTrendItem(
                    version_id=str(v.id),
                    version_number=v.version_number,
                    created_at=getattr(v, "uploaded_at", getattr(v, "created_at", None)),
                    dataset_health=round(float(vh.health_score), 1),

                    quality_health=round(float(vh.quality_health), 1),
                    risk_health=round(float(vh.risk_health), 1),
                    privacy_health=round(float(vh.privacy_health), 1),
                    anomaly_health=round(float(vh.anomaly_health), 1),
                )
            )

    trends_summary = DashboardTrendsSummary(
        available=len(trend_items) > 0,
        has_sufficient_history=len(trend_items) >= 2,
        versions=trend_items,
    )

    # -----------------------------------------------------------------------
    # Cross-Signal Columns Requiring Attention
    # -----------------------------------------------------------------------
    # Map each column to its signals
    col_signal_map: Dict[str, Dict[str, Any]] = {}

    # Risk signals
    if risk_summary.available:
        for r in risk_summary.column_risks:
            if r.risk_level in ("HIGH", "MEDIUM"):
                if r.column_name not in col_signal_map:
                    col_signal_map[r.column_name] = {}
                col_signal_map[r.column_name]["risk_level"] = r.risk_level

    # Quality signals
    if quality_summary.available:
        for f in quality_summary.failed_expectations:
            if f.column_name:
                if f.column_name not in col_signal_map:
                    col_signal_map[f.column_name] = {}
                col_signal_map[f.column_name]["quality_status"] = "Failed"

    # Anomaly signals
    if anomaly_summary.available:
        for a in anomaly_summary.anomalous_columns:
            if a.severity in ("HIGH", "MEDIUM"):
                if a.column_name not in col_signal_map:
                    col_signal_map[a.column_name] = {}
                col_signal_map[a.column_name]["anomaly_severity"] = a.severity

    # Privacy signals
    if privacy_summary.available:
        for p in privacy_summary.columns:
            if p.column_name not in col_signal_map:
                col_signal_map[p.column_name] = {}
            col_signal_map[p.column_name]["pii_severity"] = p.highest_severity

    # Issue counts
    if issues_summary.available:
        for iss in issues_summary.prioritized_issues:
            for col in iss.affected_columns:
                if col:
                    if col not in col_signal_map:
                        col_signal_map[col] = {}
                    col_signal_map[col]["issue_count"] = col_signal_map[col].get("issue_count", 0) + 1

    attention_columns = []
    for col_name, signals in col_signal_map.items():
        attention_columns.append(
            AttentionColumn(
                column_name=col_name,
                risk_level=signals.get("risk_level"),
                quality_status=signals.get("quality_status"),
                anomaly_severity=signals.get("anomaly_severity"),
                pii_severity=signals.get("pii_severity"),
                issue_count=signals.get("issue_count", 0),
            )
        )

    # Sort attention columns by issue_count desc, then risk_level
    def _attn_sort_key(c: AttentionColumn):
        sev_score = 0
        if c.risk_level == "HIGH":
            sev_score += 4
        elif c.risk_level == "MEDIUM":
            sev_score += 2
        if c.quality_status == "Failed":
            sev_score += 3
        if c.pii_severity in ("CRITICAL", "HIGH"):
            sev_score += 4
        elif c.pii_severity == "MEDIUM":
            sev_score += 2
        if c.anomaly_severity == "HIGH":
            sev_score += 3
        elif c.anomaly_severity == "MEDIUM":
            sev_score += 1
        return (c.issue_count, sev_score)

    attention_columns.sort(key=_attn_sort_key, reverse=True)

    # -----------------------------------------------------------------------
    # Grounded Key Insights
    # -----------------------------------------------------------------------
    insights: List[DashboardInsight] = []

    if health_summary.available and health_summary.dataset_health_score is not None:
        insights.append(
            DashboardInsight(
                category="Health",
                severity="HIGH" if health_summary.grade in ("CRITICAL", "POOR") else "MEDIUM" if health_summary.grade == "NEEDS ATTENTION" else "LOW",
                message=f"Dataset Health evaluated at {health_summary.dataset_health_score}/100 with qualitative status '{health_summary.grade}'.",
            )
        )

    if risk_summary.available and risk_summary.high_count > 0:
        insights.append(
            DashboardInsight(
                category="Risk",
                severity="HIGH",
                message=f"{risk_summary.high_count} column(s) classified with HIGH risk sensitivity.",
            )
        )

    if quality_summary.available:
        if quality_summary.status == "NOT_EVALUATED":
            insights.append(
                DashboardInsight(
                    category="Quality",
                    severity="INFO",
                    message="Quality validation has no evaluated expectation rules for this dataset version.",
                )
            )
        elif quality_summary.failed_rules > 0:
            insights.append(
                DashboardInsight(
                    category="Quality",
                    severity="HIGH" if quality_summary.failed_rules > 2 else "MEDIUM",
                    message=f"{quality_summary.failed_rules} data quality expectation rule(s) failed during evaluation.",
                )
            )

    if privacy_summary.available and privacy_summary.pii_columns_count > 0:
        insights.append(
            DashboardInsight(
                category="Privacy",
                severity=privacy_summary.highest_severity or "MEDIUM",
                message=f"{privacy_summary.pii_columns_count} column(s) contain detected sensitive PII entities.",
            )
        )

    if anomaly_summary.available and anomaly_summary.anomalous_columns_count > 0:
        insights.append(
            DashboardInsight(
                category="Anomalies",
                severity="MEDIUM",
                message=f"{anomaly_summary.anomalous_columns_count} column(s) exhibit statistically unusual observations / potential outliers.",
            )
        )

    if drift_summary.available and drift_summary.has_comparison:
        if drift_summary.overall_drift_severity in ("HIGH", "CRITICAL", "MEDIUM", "MODERATE"):
            insights.append(
                DashboardInsight(
                    category="Drift",
                    severity="HIGH" if "HIGH" in drift_summary.overall_drift_severity.upper() else "MEDIUM",
                    message=f"Comparison V{drift_summary.baseline_version_number} → V{drift_summary.current_version_number} identified {drift_summary.overall_drift_severity} drift in {drift_summary.drifted_columns_count} column(s).",
                )
            )

    # Build response object
    dataset_info = DashboardDatasetInfo(
        id=str(dataset.id),
        name=dataset.name,
        description=dataset.description,
        created_at=dataset.created_at,
    )

    version_info = DashboardVersionInfo(
        id=str(active_version.id),
        dataset_id=str(dataset.id),
        version_number=active_version.version_number,
        file_name=getattr(active_version, "original_filename", None),

        file_size_bytes=active_version.file_size_bytes,
        row_count=active_version.row_count,
        column_count=active_version.column_count,
        created_at=getattr(active_version, "uploaded_at", getattr(active_version, "created_at", None)),

    )

    return DashboardResponse(
        dataset=dataset_info,
        version=version_info,
        all_versions=version_options,
        health=health_summary,
        quality=quality_summary,
        risk=risk_summary,
        privacy=privacy_summary,
        anomalies=anomaly_summary,
        issues=issues_summary,
        profiling=profiling_summary,
        drift=drift_summary,
        trends=trends_summary,
        attention_columns=attention_columns,
        insights=insights,
    )
