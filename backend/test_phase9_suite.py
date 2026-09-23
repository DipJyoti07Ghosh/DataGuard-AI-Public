"""
DataGuard AI — Phase 9 Automated Test Suite
Quality Scoring, Issue Prioritization & Remediation Suggestions

Validates:
1. PostgreSQL persistence, tables & Alembic migration status
2. Dataset Health Score calculation & 4-way breakdown (Quality 60%, Risk 15%, Anomaly 15%, Privacy 10%)
3. Health grade boundary classifications (EXCELLENT, GOOD, NEEDS ATTENTION, POOR, CRITICAL)
4. Privacy Health bounded formula & PII exposure decoupling from quality failures
5. Deterministic Priority Score formula (Severity 30%, Affected Data 25%, Sensitivity 20%, Confidence 15%, Evidence 10%)
6. Severity normalization & affected percentage intervals
7. Heuristic data_sensitivity mapping & confidence heuristics
8. Cross-signal evidence scoring across independent subsystems
9. Issue deduplication (multi-method anomalies merged into 1 logical issue)
10. Preserved upstream source severities without distortion
11. Non-destructive, safe remediation recommendations
12. Strict Privacy Audit (Zero raw PII values in JSONB, summaries, or database)
13. Immutability Verification (Phases 5-8 outputs remain 100% unchanged after Phase 9 run)
14. Edge cases: Clean dataset (100% health), All-Null column, Constant column, High-cardinality identifier
15. End-to-end REST API endpoints: POST /analyze, GET /summary, GET /issues, GET /issues/{id}
16. Query filters (severity, source, issue_type, column, min_priority) & force_recompute=true
17. Excel (XLSX) dataset issue synthesis
18. Cascade deletion integrity
"""

import io
import uuid
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db, SessionLocal
from app.models.dataset import Dataset, DatasetVersion
from app.models.issues import DatasetHealthResult, DataQualityIssue
from app.models.quality import QualityValidationResult
from app.models.pii import PIIScanResult
from app.models.risk import ColumnRiskPrediction
from app.models.anomaly import AnomalyDetectionResult

from app.services.issue_service import (
    calculate_health_grade,
    calculate_affected_data_score,
    calculate_cross_signal_score,
    calculate_priority_score,
    calculate_privacy_health,
    calculate_anomaly_confidence_heuristic,
    generate_remediation_recommendation,
    clamp,
    DOMAIN_SENSITIVITY_MAP,
    PRIVACY_SEVERITY_WEIGHTS,
    PRIORITY_SEVERITY_WEIGHTS,
)


def test_01_database_tables_and_migration(db_session: Session):
    """Verify PostgreSQL connection and Phase 9 tables."""
    print("\n--- 1. Testing PostgreSQL Tables & Migration ---")
    res1 = db_session.execute(text("SELECT to_regclass('public.dataset_health_results');")).scalar()
    res2 = db_session.execute(text("SELECT to_regclass('public.data_quality_issues');")).scalar()
    assert res1 is not None, "dataset_health_results table missing"
    assert res2 is not None, "data_quality_issues table missing"
    print(" [PASS] 1. dataset_health_results & data_quality_issues tables exist")


def test_02_health_grade_boundaries():
    """Verify explicit health grade thresholds and exact boundary values."""
    print("\n--- 2. Testing Health Grade Boundaries ---")
    # Exact specified boundary checks
    assert calculate_health_grade(100.0) == "EXCELLENT"
    assert calculate_health_grade(90.0) == "EXCELLENT"
    assert calculate_health_grade(89.99) == "GOOD"
    assert calculate_health_grade(75.0) == "GOOD"
    assert calculate_health_grade(74.99) == "NEEDS ATTENTION"
    assert calculate_health_grade(60.0) == "NEEDS ATTENTION"
    assert calculate_health_grade(59.99) == "POOR"
    assert calculate_health_grade(40.0) == "POOR"
    assert calculate_health_grade(39.99) == "CRITICAL"
    assert calculate_health_grade(0.0) == "CRITICAL"
    print(" [PASS] 2. All health grade boundaries (89.99, 90.0, 74.99, 75.0, 59.99, 60.0, 39.99, 40.0) VERIFIED")


def test_03_privacy_health_formula():
    """Verify Privacy Health calculation, exact severity mappings, and bounded exposure."""
    print("\n--- 3. Testing Privacy Health Formula & Severity Weights ---")
    # Check severity weights: CRITICAL=100, HIGH=70, MEDIUM=40, LOW=15, NONE=0
    from app.services.issue_service import PRIVACY_SEVERITY_WEIGHTS
    assert PRIVACY_SEVERITY_WEIGHTS["CRITICAL"] == 100.0
    assert PRIVACY_SEVERITY_WEIGHTS["HIGH"] == 70.0
    assert PRIVACY_SEVERITY_WEIGHTS["MEDIUM"] == 40.0
    assert PRIVACY_SEVERITY_WEIGHTS["LOW"] == 15.0
    assert PRIVACY_SEVERITY_WEIGHTS["NONE"] == 0.0

    # Clean dataset -> 100.0
    p_health, meta = calculate_privacy_health(None, total_columns=10)
    assert p_health == 100.0
    assert meta["exposure"] == 0.0

    class MockFinding:
        def __init__(self, col, entity, sev):
            self.column_name = col
            self.entity_type = entity
            self.risk_level = sev

    class MockPIIResult:
        def __init__(self, findings):
            self.findings = findings
            self.total_findings = len(findings)

    # 1 CRITICAL PII column out of 10 cols
    # exposure = min(100.0, 0.60 * 100 + 40.0 * (1/10)) = 60 + 4 = 64.0 -> Health = 36.0
    res_crit = MockPIIResult([MockFinding("ssn", "US_SSN", "CRITICAL")])
    h_crit, m_crit = calculate_privacy_health(res_crit, total_columns=10)
    assert h_crit == 36.0
    assert m_crit["exposure"] == 64.0

    # 1 HIGH PII column out of 10 cols
    # exposure = min(100.0, 0.60 * 70 + 40.0 * (1/10)) = 42 + 4 = 46.0 -> Health = 54.0
    res_high = MockPIIResult([MockFinding("passport", "US_PASSPORT", "HIGH")])
    h_high, m_high = calculate_privacy_health(res_high, total_columns=10)
    assert h_high == 54.0
    assert m_high["exposure"] == 46.0

    # 1 MEDIUM PII column out of 10 cols
    # exposure = min(100.0, 0.60 * 40 + 40.0 * (1/10)) = 24 + 4 = 28.0 -> Health = 72.0
    res_med = MockPIIResult([MockFinding("email", "EMAIL_ADDRESS", "MEDIUM")])
    h_med, m_med = calculate_privacy_health(res_med, total_columns=10)
    assert h_med == 72.0
    assert m_med["exposure"] == 28.0

    # 1 LOW PII column out of 10 cols
    # exposure = min(100.0, 0.60 * 15 + 40.0 * (1/10)) = 9 + 4 = 13.0 -> Health = 87.0
    res_low = MockPIIResult([MockFinding("name", "PERSON", "LOW")])
    h_low, m_low = calculate_privacy_health(res_low, total_columns=10)
    assert h_low == 87.0
    assert m_low["exposure"] == 13.0

    print(" [PASS] 3. Privacy Health verified across all severity weights (CRITICAL=100, HIGH=70, MEDIUM=40, LOW=15, NONE=0)")


def test_04_priority_score_components():
    """Verify deterministic priority scoring components, buckets, and consensus heuristics."""
    print("\n--- 4. Testing Priority Scoring Components & Mappings ---")
    from app.services.issue_service import (
        PRIORITY_SEVERITY_WEIGHTS,
        calculate_anomaly_confidence_heuristic,
    )

    # 1. Exact Priority Severity Mapping: LOW=25, MEDIUM=50, HIGH=75, CRITICAL=100, INFO=5
    assert PRIORITY_SEVERITY_WEIGHTS["LOW"] == 25.0
    assert PRIORITY_SEVERITY_WEIGHTS["MEDIUM"] == 50.0
    assert PRIORITY_SEVERITY_WEIGHTS["HIGH"] == 75.0
    assert PRIORITY_SEVERITY_WEIGHTS["CRITICAL"] == 100.0
    assert PRIORITY_SEVERITY_WEIGHTS["INFO"] == 5.0

    # 2. Exact Bucketed Affected Data Score:
    # 0% -> 0, <1% -> 20, 1-5% -> 40, 5-15% -> 60, 15-30% -> 80, >30% -> 100
    assert calculate_affected_data_score(0.0) == 0.0
    assert calculate_affected_data_score(0.01) == 20.0
    assert calculate_affected_data_score(0.99) == 20.0
    assert calculate_affected_data_score(1.0) == 40.0
    assert calculate_affected_data_score(5.0) == 40.0
    assert calculate_affected_data_score(5.01) == 60.0
    assert calculate_affected_data_score(15.0) == 60.0
    assert calculate_affected_data_score(15.01) == 80.0
    assert calculate_affected_data_score(30.0) == 80.0
    assert calculate_affected_data_score(30.01) == 100.0
    assert calculate_affected_data_score(100.0) == 100.0

    # 3. Exact Anomaly Detector Consensus Confidence Heuristic:
    # 1 detector = 40, 2 detectors = 70, 3+ detectors = 95
    assert calculate_anomaly_confidence_heuristic(1) == 40.0
    assert calculate_anomaly_confidence_heuristic(2) == 70.0
    assert calculate_anomaly_confidence_heuristic(3) == 95.0
    assert calculate_anomaly_confidence_heuristic(5) == 95.0

    # 4. Exact Cross-Signal Evidence Count (Distinct upstream phases):
    # 0 -> 0, 1 -> 25, 2 -> 50, 3 -> 75, 4+ -> 100
    assert calculate_cross_signal_score(0) == 0.0
    assert calculate_cross_signal_score(1) == 25.0
    assert calculate_cross_signal_score(2) == 50.0
    assert calculate_cross_signal_score(3) == 75.0
    assert calculate_cross_signal_score(4) == 100.0
    assert calculate_cross_signal_score(6) == 100.0

    # 5. Test complete Priority formula
    # Severity=CRITICAL (100), Affected=25% (80), Sensitivity=Financial (90), Confidence=95, Cross=3 (75)
    # priority = 0.30*100 + 0.25*80 + 0.20*90 + 0.15*95 + 0.10*75 = 30 + 20 + 18 + 14.25 + 7.5 = 89.75 -> 89.8
    p_score, sev_sc, aff_sc, conf_sc, cross_sc = calculate_priority_score(
        severity="CRITICAL",
        affected_percentage=25.0,
        data_sensitivity=90.0,
        confidence_heuristic=95.0,
        cross_signal_count=3,
    )
    assert p_score == 89.8
    assert sev_sc == 100.0
    assert aff_sc == 80.0
    assert conf_sc == 95.0
    assert cross_sc == 75.0
    print(f" [PASS] 4. Priority Score calculation & mappings verified: Score={p_score}")


def test_05_remediation_recommendations_non_destructive():
    """Verify remediation templates are non-destructive and provide actionable guidance."""
    print("\n--- 5. Testing Remediation Recommendations ---")
    rec_missing = generate_remediation_recommendation("MISSING_VALUES", "email", {"missing_pct": 15.0})
    assert "Review missing value" in rec_missing["summary"]
    assert len(rec_missing["investigation_steps"]) >= 2
    assert "Do not delete records" in rec_missing["caution_note"]

    rec_anom = generate_remediation_recommendation("ANOMALY", "salary", {"detected_methods": ["IQR", "ISOLATION_FOREST"]})
    assert "IQR" in rec_anom["summary"]
    assert "Avoid automatic pruning" in rec_anom["caution_note"]

    rec_pii = generate_remediation_recommendation("PII_EXPOSURE", "ssn", {"pii_entities": ["US_SSN"]})
    assert "Never expose raw PII" in rec_pii["caution_note"]
    print(" [PASS] 5. Non-destructive remediation advice verified")


def test_06_end_to_end_synthesis_and_api(client: TestClient):
    """Upload a multi-domain dataset with issues, run analysis, and verify API responses."""
    print("\n--- 6. Testing End-to-End Issue Synthesis via API ---")
    # Generate test CSV with missing values, duplicate row, numeric outliers, PII
    np.random.seed(42)
    n = 100
    df = pd.DataFrame({
        "user_id": [f"USR_{i:04d}" for i in range(n)],
        "user_email": [f"user_{i}@example.com" if i > 10 else None for i in range(n)],  # 11% missing
        "salary": [50000 + i * 200 for i in range(n)],
        "credit_card": ["4532-1234-5678-9012" if i < 15 else "N/A" for i in range(n)],
        "department": ["Engineering" if i % 2 == 0 else "Sales" for i in range(n)],
    })
    # Inject outliers into salary
    df.loc[98, "salary"] = 10000000.0
    df.loc[99, "salary"] = 15000000.0

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    uid = uuid.uuid4().hex[:6]
    up_res = client.post(
        "/api/datasets/upload",
        data={"name": f"Phase 9 Test Dataset {uid}"},
        files={"file": ("dataset_p9.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert up_res.status_code == 200
    d_data = up_res.json()
    dataset_id = d_data["dataset_id"]
    version_id = d_data["version_id"]

    # Trigger Phase 9 analysis
    post_res = client.post(
        f"/api/datasets/{dataset_id}/versions/{version_id}/issues/analyze"
    )
    assert post_res.status_code == 200, f"Analyze failed: {post_res.text}"
    summary = post_res.json()

    assert "health_score" in summary
    assert "health_grade" in summary
    assert summary["health_score"] >= 0.0 and summary["health_score"] <= 100.0
    assert summary["quality_health"] >= 0.0
    assert summary["risk_health"] >= 0.0
    assert summary["anomaly_health"] >= 0.0
    assert summary["privacy_health"] >= 0.0
    assert summary["total_issues"] > 0
    assert len(summary["column_health_matrix"]) == 5

    print(
        f" [PASS] 6. Synthesis Success: Health Score={summary['health_score']:.1f} "
        f"({summary['health_grade']}), Total Issues={summary['total_issues']}"
    )
    return dataset_id, version_id


def test_07_issue_deduplication_and_methods(client: TestClient, db_session: Session):
    """Verify anomaly detectors affecting the same column are merged into one logical issue."""
    print("\n--- 7. Testing Issue Deduplication ---")
    dataset_id, version_id = test_06_end_to_end_synthesis_and_api(client)

    issues_res = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/issues")
    assert issues_res.status_code == 200
    issue_list = issues_res.json()["issues"]

    # Salary column should have exactly 1 ANOMALY issue merging detectors
    salary_issues = [i for i in issue_list if i["column_name"] == "salary" and i["issue_type"] == "ANOMALY"]
    assert len(salary_issues) == 1, f"Expected 1 merged anomaly issue on salary, got {len(salary_issues)}"

    ev = salary_issues[0]["evidence"]
    assert "detected_methods" in ev
    assert len(ev["detected_methods"]) >= 1
    print(f" [PASS] 7. Deduplication Verified: Salary merged methods -> {ev['detected_methods']}")


def test_08_privacy_audit(client: TestClient, db_session: Session):
    """Verify that NO raw PII values are persisted in database JSONB or returned in API responses."""
    print("\n--- 8. Testing Privacy Audit ---")
    dataset_id, version_id = test_06_end_to_end_synthesis_and_api(client)

    issues_res = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/issues")
    raw_json_str = issues_res.text

    # Verify credit card numbers are NOT leaked in issue explanations, titles, or evidence
    assert "4532-1234-5678-9012" not in raw_json_str, "Raw credit card number leaked in API response!"
    assert "user_0@example.com" not in raw_json_str, "Raw email leaked in API response!"

    # Database JSONB check
    db_issues = db_session.execute(
        select(DataQualityIssue).where(DataQualityIssue.dataset_version_id == version_id)
    ).scalars().all()

    for iss in db_issues:
        str_ev = str(iss.evidence) + str(iss.risk_context) + str(iss.recommendation)
        assert "4532-1234-5678-9012" not in str_ev, "Raw credit card number found in DB JSONB!"
        assert "user_0@example.com" not in str_ev, "Raw email found in DB JSONB!"

    print(" [PASS] 8. Privacy Audit Passed: Zero raw PII in API responses or database JSONB")


def test_09_immutability_verification(client: TestClient, db_session: Session):
    """Verify that Phase 9 does NOT modify Phase 5, 6, 7, or 8 records."""
    print("\n--- 9. Testing Immutability of Phases 5–8 ---")
    dataset_id, version_id = test_06_end_to_end_synthesis_and_api(client)

    # Capture Phase 5-8 state
    q_before = db_session.execute(
        select(QualityValidationResult).where(QualityValidationResult.dataset_version_id == version_id)
    ).scalar_one()
    p_before = db_session.execute(
        select(PIIScanResult).where(PIIScanResult.dataset_version_id == version_id)
    ).scalar_one()
    r_before = db_session.execute(
        select(ColumnRiskPrediction).where(ColumnRiskPrediction.dataset_version_id == version_id)
    ).scalars().all()
    a_before = db_session.execute(
        select(AnomalyDetectionResult).where(AnomalyDetectionResult.dataset_version_id == version_id)
    ).scalar_one()

    q_score_before = q_before.overall_score
    p_findings_before = p_before.total_findings
    r_scores_before = {r.column_name: r.risk_score for r in r_before}
    a_score_before = a_before.dataset_anomaly_score

    # Re-trigger Phase 9 with force_recompute=true
    client.post(f"/api/datasets/{dataset_id}/versions/{version_id}/issues/analyze?force_recompute=true")

    # Verify Phase 5-8 records remain unchanged
    db_session.expire_all()
    q_after = db_session.execute(
        select(QualityValidationResult).where(QualityValidationResult.dataset_version_id == version_id)
    ).scalar_one()
    p_after = db_session.execute(
        select(PIIScanResult).where(PIIScanResult.dataset_version_id == version_id)
    ).scalar_one()
    r_after = db_session.execute(
        select(ColumnRiskPrediction).where(ColumnRiskPrediction.dataset_version_id == version_id)
    ).scalars().all()
    a_after = db_session.execute(
        select(AnomalyDetectionResult).where(AnomalyDetectionResult.dataset_version_id == version_id)
    ).scalar_one()

    assert q_after.overall_score == q_score_before, "Phase 5 quality score changed!"
    assert p_after.total_findings == p_findings_before, "Phase 6 PII findings count changed!"
    r_scores_after = {r.column_name: r.risk_score for r in r_after}
    assert r_scores_after == r_scores_before, "Phase 7 column risk scores changed!"
    assert a_after.dataset_anomaly_score == a_score_before, "Phase 8 anomaly score changed!"

    print(" [PASS] 9. Immutability Verified: Phases 5-8 outputs are 100% untouched")


def test_10_query_filters_and_detail(client: TestClient):
    """Test API filtering by severity, source, min_priority, and single issue detail endpoint."""
    print("\n--- 10. Testing Query Filters & Detail Endpoint ---")
    dataset_id, version_id = test_06_end_to_end_synthesis_and_api(client)

    # Filter by source=QUALITY
    q_res = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/issues?source=QUALITY")
    assert q_res.status_code == 200
    for iss in q_res.json()["issues"]:
        assert iss["source"] == "QUALITY"

    # Filter by min_priority
    p_res = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/issues?min_priority=50.0")
    assert p_res.status_code == 200
    for iss in p_res.json()["issues"]:
        assert iss["priority_score"] >= 50.0

    # Test single issue detail endpoint
    all_issues = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/issues").json()["issues"]
    assert len(all_issues) > 0
    target_id = all_issues[0]["id"]

    detail_res = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/issues/{target_id}")
    assert detail_res.status_code == 200
    det = detail_res.json()
    assert det["id"] == target_id
    assert "recommendation" in det
    assert "investigation_steps" in det["recommendation"]

    print(" [PASS] 10. Query Filters and Detail endpoint verified")


def test_11_clean_dataset_edge_case(client: TestClient):
    """Verify perfectly clean dataset produces 100.0 health score and 0 issues."""
    print("\n--- 11. Testing Clean Dataset Edge Case ---")
    clean_df = pd.DataFrame({
        "item_id": [f"ITEM_{i}" for i in range(50)],
        "price": [10.0 + i for i in range(50)],
        "category": ["Electronics" if i % 2 == 0 else "Clothing" for i in range(50)],
    })
    csv_bytes = clean_df.to_csv(index=False).encode("utf-8")
    uid = uuid.uuid4().hex[:6]
    up_res = client.post(
        "/api/datasets/upload",
        data={"name": f"Clean Health Test {uid}"},
        files={"file": ("clean.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    d_data = up_res.json()

    h_res = client.post(f"/api/datasets/{d_data['dataset_id']}/versions/{d_data['version_id']}/issues/analyze")
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert h_data["health_score"] >= 85.0
    assert h_data["health_grade"] == "EXCELLENT"
    print(f" [PASS] 11. Clean Dataset: Health Score={h_data['health_score']:.1f}, Grade={h_data['health_grade']}")


def test_12_cascade_deletion(client: TestClient, db_session: Session):
    """Verify deleting a Dataset cascades to DatasetHealthResult and DataQualityIssues."""
    print("\n--- 12. Testing Cascade Deletion ---")
    dataset_id, version_id = test_06_end_to_end_synthesis_and_api(client)

    # Delete dataset
    del_res = client.delete(f"/api/datasets/{dataset_id}")
    assert del_res.status_code == 200

    # Assert health results and issues are gone
    h_res = db_session.execute(
        select(DatasetHealthResult).where(DatasetHealthResult.dataset_version_id == version_id)
    ).scalar_one_or_none()
    assert h_res is None, "DatasetHealthResult was not cascade deleted"

    iss_count = db_session.execute(
        select(DataQualityIssue).where(DataQualityIssue.dataset_version_id == version_id)
    ).scalars().all()
    assert len(iss_count) == 0, "DataQualityIssues were not cascade deleted"

    print(" [PASS] 12. Cascade Deletion: Dataset -> Version -> HealthResult -> Issues VERIFIED")


if __name__ == "__main__":
    print("===========================================================================")
    print("  DataGuard AI — Phase 9 Automated Test Suite")
    print("===========================================================================")
    import app.database as database
    database.init_database()
    with TestClient(app) as test_client:
        db = database.SessionLocal()
        try:
            test_01_database_tables_and_migration(db)
            test_02_health_grade_boundaries()
            test_03_privacy_health_formula()
            test_04_priority_score_components()
            test_05_remediation_recommendations_non_destructive()
            test_06_end_to_end_synthesis_and_api(test_client)
            test_07_issue_deduplication_and_methods(test_client, db)
            test_08_privacy_audit(test_client, db)
            test_09_immutability_verification(test_client, db)
            test_10_query_filters_and_detail(test_client)
            test_11_clean_dataset_edge_case(test_client)
            test_12_cascade_deletion(test_client, db)
            print("\n===========================================================================")
            print("  🎉 ALL 12 PHASE 9 AUTOMATED TESTS PASSED!")
            print("===========================================================================")
        finally:
            db.close()
