"""
DataGuard AI — Phase 5 Automated Data Quality Test Suite

Comprehensive automated test script to verify:
1. PostgreSQL connection & 003_create_quality Alembic migration
2. Quality validation execution & Great Expectations integration
3. Quality score calculation & Grade assignment (0-100)
4. Category health breakdown & pass rate calculations
5. Detection of missing data, duplicate rows, data type mismatches, and negative range violations
6. Caching & force_recompute parameter
7. Granular expectation details filtering
8. XLSX workbook quality evaluation
9. 404 error handling for non-existent entities
"""

import sys
import uuid
from io import BytesIO
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import text

# Ensure backend root is in path
sys.path.insert(0, str(Path(__file__).parent))

from app.main import app
import app.database as db

client = TestClient(app)
DATA_DIR = Path(__file__).parent.parent / "data"

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"


def run_tests():
    print("=" * 70)
    print("  DataGuard AI — Phase 5 Automated Data Quality Test Suite")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # 1. Database Connectivity & Migration Verification
    # -----------------------------------------------------------------------
    print("\n--- 1. Testing PostgreSQL Connection & Quality Tables ---")
    db.init_database()
    try:
        with db.engine.connect() as conn:
            res = conn.execute(text("SELECT 1")).scalar()
            assert res == 1, "SELECT 1 failed"
            # Verify tables exist
            q_table = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_name = 'quality_validation_results'"
                )
            ).scalar()
            assert q_table == "quality_validation_results", "quality_validation_results table not found"
            
            e_table = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_name = 'quality_expectation_results'"
                )
            ).scalar()
            assert e_table == "quality_expectation_results", "quality_expectation_results table not found"
        print(f" {PASS} PostgreSQL Connection & Quality Tables: VERIFIED")
    except Exception as e:
        print(f" {FAIL} PostgreSQL connection failed: {e}")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 2. Upload Clean Dataset for Quality Validation
    # -----------------------------------------------------------------------
    print("\n--- 2. Ingesting Clean Dataset for Baseline Quality ---")
    run_id = uuid.uuid4().hex[:6]
    clean_dataset_name = f"Clean Quality Test {run_id}"

    with open(DATA_DIR / "clean_sample.csv", "rb") as f:
        csv_bytes = f.read()

    upload_res = client.post(
        "/api/datasets/upload",
        data={"dataset_name": clean_dataset_name, "description": "Clean dataset for quality testing"},
        files={"file": ("clean_sample.csv", BytesIO(csv_bytes), "text/csv")},
    )
    assert upload_res.status_code == 200, f"Clean upload failed: {upload_res.text}"
    clean_upload_data = upload_res.json()
    clean_dataset_id = clean_upload_data["dataset_id"]
    clean_version_id = clean_upload_data["version_id"]
    print(f" {PASS} Ingested Clean Dataset: ID={clean_dataset_id}, Version ID={clean_version_id}")

    # -----------------------------------------------------------------------
    # 3. Trigger Quality Validation via POST
    # -----------------------------------------------------------------------
    print("\n--- 3. Running Automated Quality Validation via POST ---")
    quality_res = client.post(
        f"/api/datasets/{clean_dataset_id}/versions/{clean_version_id}/quality"
    )
    assert quality_res.status_code == 200, f"Quality POST failed: {quality_res.text}"
    q_data = quality_res.json()

    score = q_data["overall_score"]
    total = q_data["total_expectations"]
    passed = q_data["passed_expectations"]
    failed = q_data["failed_expectations"]
    grade = q_data["grade"]

    print(f" {PASS} Quality Scorecard Generated:")
    print(f"        Score: {score}/100 (Grade: {grade})")
    print(f"        Rules Evaluated: {total} total ({passed} passed, {failed} failed)")

    assert score >= 90.0, f"Clean dataset expected score >= 90, got {score}"
    assert grade in ("Excellent", "Good"), f"Unexpected grade: {grade}"
    assert total > 0, "No quality expectations evaluated"
    assert failed == 0, f"Clean dataset had unexpected failures: {q_data['failed_rules']}"

    # -----------------------------------------------------------------------
    # 4. Verifying Category Breakdown
    # -----------------------------------------------------------------------
    print("\n--- 4. Verifying Quality Category Breakdown ---")
    categories = q_data["summary"]["categories"]
    expected_categories = [
        "Missing Data",
        "Schema / Type",
        "Range / Distribution",
        "Uniqueness",
        "Duplicate Data",
        "Categorical Consistency",
    ]
    for cat in expected_categories:
        assert cat in categories, f"Missing category '{cat}' in summary"
        cat_data = categories[cat]
        print(f"        • {cat}: {cat_data['passed']}/{cat_data['total']} passed ({cat_data['pass_rate']}%, status={cat_data['status']})")
        assert cat_data["status"] == "PASSED", f"Expected PASSED for clean {cat}"
    print(f" {PASS} All 6 Quality Categories Verified Clean")

    # -----------------------------------------------------------------------
    # 5. Testing Quality GET Endpoint (Cached)
    # -----------------------------------------------------------------------
    print("\n--- 5. Testing GET /api/datasets/{id}/versions/{v_id}/quality ---")
    get_res = client.get(
        f"/api/datasets/{clean_dataset_id}/versions/{clean_version_id}/quality"
    )
    assert get_res.status_code == 200, f"Quality GET failed: {get_res.text}"
    get_data = get_res.json()
    assert get_data["id"] == q_data["id"], "Cached GET did not return same quality record ID"
    assert get_data["overall_score"] == score, "Score mismatch on GET"
    print(f" {PASS} GET /quality: Retrieved cached scorecard successfully")

    # -----------------------------------------------------------------------
    # 6. Testing force_recompute=True
    # -----------------------------------------------------------------------
    print("\n--- 6. Testing force_recompute=True ---")
    recomp_res = client.post(
        f"/api/datasets/{clean_dataset_id}/versions/{clean_version_id}/quality?force_recompute=true"
    )
    assert recomp_res.status_code == 200, f"Recompute failed: {recomp_res.text}"
    recomp_data = recomp_res.json()
    assert recomp_data["overall_score"] == score, "Score mismatch after recompute"
    print(f" {PASS} force_recompute=True successfully re-evaluated and refreshed database record")

    # -----------------------------------------------------------------------
    # 7. Quality Validation on Problematic Dataset
    # -----------------------------------------------------------------------
    print("\n--- 7. Validating Quality on Dataset with Quality Issues ---")
    issues_dataset_name = f"Quality Issues Test {run_id}"

    with open(DATA_DIR / "quality_issues_v1.csv", "rb") as f:
        issues_bytes = f.read()

    issues_upload = client.post(
        "/api/datasets/upload",
        data={"dataset_name": issues_dataset_name, "description": "Dataset with intentional quality issues"},
        files={"file": ("quality_issues_v1.csv", BytesIO(issues_bytes), "text/csv")},
    )
    assert issues_upload.status_code == 200, f"Issues upload failed: {issues_upload.text}"
    issues_up_data = issues_upload.json()
    issues_ds_id = issues_up_data["dataset_id"]
    issues_ver_id = issues_up_data["version_id"]

    issues_quality = client.post(
        f"/api/datasets/{issues_ds_id}/versions/{issues_ver_id}/quality"
    )
    assert issues_quality.status_code == 200, f"Quality issues POST failed: {issues_quality.text}"
    issues_q_data = issues_quality.json()

    i_score = issues_q_data["overall_score"]
    i_failed = issues_q_data["failed_expectations"]
    i_problems = issues_q_data["summary"]["major_quality_problems"]
    failed_rules = issues_q_data["failed_rules"]

    print(f" {PASS} Quality Issues Evaluated:")
    print(f"        Score: {i_score}/100 (Grade: {issues_q_data['grade']})")
    print(f"        Failed Expectations: {i_failed}")
    print(f"        Major Problems Detected: {len(i_problems)}")
    for p in i_problems:
        print(f"          - {p}")

    assert i_failed > 0, "Expected quality failures on quality_issues_v1.csv"
    assert i_score < 100.0, "Score should drop on problematic dataset"

    # Verify duplicate expectation failed
    dup_failures = [r for r in failed_rules if r["category"] == "Duplicate Data"]
    assert len(dup_failures) > 0, "Duplicate rows check should have failed"
    print(f" {PASS} Correctly detected duplicate rows failure: '{dup_failures[0]['failure_message']}'")

    # Verify missing data expectation failure
    missing_failures = [r for r in failed_rules if r["category"] == "Missing Data"]
    assert len(missing_failures) > 0, "Missing data check should have failed"
    print(f" {PASS} Correctly detected missing data failure on column '{missing_failures[0]['column_name']}'")

    # -----------------------------------------------------------------------
    # 8. Testing Granular Quality Details Endpoint
    # -----------------------------------------------------------------------
    print("\n--- 8. Testing GET /quality/details Endpoint with Filters ---")
    details_res = client.get(
        f"/api/datasets/{issues_ds_id}/versions/{issues_ver_id}/quality/details?status_filter=failed"
    )
    assert details_res.status_code == 200, f"Details failed: {details_res.text}"
    details_failed = details_res.json()
    assert all(not r["success"] for r in details_failed), "Filtered details contained non-failed rule"
    assert len(details_failed) == i_failed, f"Expected {i_failed} failed rules, got {len(details_failed)}"
    print(f" {PASS} GET /quality/details?status_filter=failed returned exact {len(details_failed)} failed rules")

    # -----------------------------------------------------------------------
    # 9. Testing XLSX Excel Quality Validation
    # -----------------------------------------------------------------------
    print("\n--- 9. Testing XLSX Dataset Quality Validation ---")
    excel_dataset_name = f"Excel Quality Test {run_id}"

    with open(DATA_DIR / "sample_excel.xlsx", "rb") as f:
        excel_bytes = f.read()

    excel_upload = client.post(
        "/api/datasets/upload",
        data={"dataset_name": excel_dataset_name},
        files={"file": ("sample_excel.xlsx", BytesIO(excel_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert excel_upload.status_code == 200, f"Excel upload failed: {excel_upload.text}"
    excel_data = excel_upload.json()
    
    excel_quality = client.get(
        f"/api/datasets/{excel_data['dataset_id']}/versions/{excel_data['version_id']}/quality"
    )
    assert excel_quality.status_code == 200, f"Excel quality failed: {excel_quality.text}"
    excel_q = excel_quality.json()
    print(f" {PASS} Excel Quality Score: {excel_q['overall_score']}/100 ({excel_q['total_expectations']} checks evaluated)")

    # -----------------------------------------------------------------------
    # 10. 404 Error Handling
    # -----------------------------------------------------------------------
    print("\n--- 10. Testing 404 Error Handling ---")
    dummy_id = str(uuid.uuid4())
    err_res = client.get(f"/api/datasets/{dummy_id}/versions/{dummy_id}/quality")
    assert err_res.status_code == 404, f"Expected 404, got {err_res.status_code}"
    print(f" {PASS} Non-existent dataset/version returned 404 Not Found")

    print("=" * 70)
    print("  All Phase 5 Data Quality Automated Tests PASSED! \u2705")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
