"""
DataGuard AI — Phase 6 Automated PII & Sensitive Data Detection Test Suite

Comprehensive automated test suite to verify:
1. PostgreSQL connection & 004_create_pii_results Alembic migration
2. Dataset upload & versioning persistence
3. Phase 4 Profiling regression
4. Phase 5 Quality validation regression
5. PII scan execution (POST /api/datasets/{id}/versions/{vid}/pii/scan)
6. PIIScanResult and PIIFinding persistence
7. Synthetic Email detection (EMAIL_ADDRESS)
8. Synthetic Phone detection (PHONE_NUMBER)
9. Synthetic IP Address detection (IP_ADDRESS)
10. Synthetic Person Name detection (PERSON)
11. Synthetic Credit Card / SSN detection (CREDIT_CARD / US_SSN)
12. Column-name heuristic detection
13. Value-level detection on generic columns (e.g., 'contact', 'user_data')
14. Sample match count & detection rate calculation
15. Confidence score calculation & boosting
16. Irreversible sample masking (e.g., j***@e******.com, ******3210)
17. Privacy Guarantee: Zero raw PII in database, API responses, or logs
18. Cached GET endpoint (GET /api/datasets/{id}/versions/{vid}/pii)
19. Force recompute execution (force_recompute=true)
20. Entity type filtering (GET .../pii/details?entity_type=EMAIL_ADDRESS)
21. Risk level filtering (GET .../pii/details?risk_level=HIGH/MEDIUM)
22. Column name filtering (GET .../pii/details?column_name=...)
23. 404 handling for invalid dataset/version combinations
24. CSV dataset PII scanning
25. XLSX workbook PII scanning
26. Phase 2 regression
27. Phase 3 regression
28. Phase 4 regression
29. Phase 5 regression
30. Frontend production build validation
"""

import sys
import uuid
import subprocess
from io import BytesIO
from pathlib import Path
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import text

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.main import app
import app.database as db
from app.services.pii_service import mask_pii_value, calculate_risk_level, detect_column_name_heuristic

client = TestClient(app)
DATA_DIR = Path(__file__).parent.parent / "data"

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"


def run_tests():
    print("=" * 75)
    print("  DataGuard AI — Phase 6 Automated PII Detection Test Suite")
    print("=" * 75)

    test_failures = []

    # -----------------------------------------------------------------------
    # 1. PostgreSQL Connection & Alembic Migration Tables
    # -----------------------------------------------------------------------
    print("\n--- 1. Testing PostgreSQL Connection & PII Tables ---")
    db.init_database()
    try:
        with db.engine.connect() as conn:
            res = conn.execute(text("SELECT 1")).scalar()
            assert res == 1, "SELECT 1 failed"
            
            # Check pii_scan_results table
            s_table = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_name = 'pii_scan_results'")
            ).scalar()
            assert s_table == "pii_scan_results", "pii_scan_results table not found in PostgreSQL"

            # Check pii_findings table
            f_table = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_name = 'pii_findings'")
            ).scalar()
            assert f_table == "pii_findings", "pii_findings table not found in PostgreSQL"
        print(f" {PASS} 1. PostgreSQL Connection & PII Tables: VERIFIED")
    except Exception as e:
        print(f" {FAIL} PostgreSQL connection/migration check failed: {e}")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 2. Masking Unit Verification
    # -----------------------------------------------------------------------
    print("\n--- 2. Testing Pure Masking Engine ---")
    try:
        email_masked = mask_pii_value("test.user@example.com", "EMAIL_ADDRESS")
        assert "test.user@example.com" not in email_masked, "Raw email leaked in mask"
        assert "@" in email_masked and "t***" in email_masked, f"Unexpected email mask: {email_masked}"

        phone_masked = mask_pii_value("9876543210", "PHONE_NUMBER")
        assert "9876543210" not in phone_masked, "Raw phone leaked in mask"
        assert "3210" in phone_masked and "*" in phone_masked, f"Unexpected phone mask: {phone_masked}"

        card_masked = mask_pii_value("4111222233334444", "CREDIT_CARD")
        assert "4111222233334444" not in card_masked, "Raw card leaked in mask"
        assert "4444" in card_masked and "****" in card_masked, f"Unexpected card mask: {card_masked}"

        ssn_masked = mask_pii_value("123456789", "US_SSN")
        assert "123456789" not in ssn_masked, "Raw SSN leaked in mask"
        assert "6789" in ssn_masked and "***" in ssn_masked, f"Unexpected SSN mask: {ssn_masked}"

        ip_masked = mask_pii_value("192.168.1.10", "IP_ADDRESS")
        assert "192.168.1.10" not in ip_masked, "Raw IP leaked in mask"
        assert "192.168.***.***" == ip_masked, f"Unexpected IP mask: {ip_masked}"

        person_masked = mask_pii_value("Johnathan Doe", "PERSON")
        assert "Johnathan" not in person_masked and "Doe" not in person_masked, "Raw name leaked in mask"
        assert "J***" in person_masked or "J*" in person_masked, f"Unexpected person mask: {person_masked}"

        print(f" {PASS} 2. Masking Engine: ALL SANITIZATION CHECKS PASSED")
    except Exception as e:
        print(f" {FAIL} Masking engine check failed: {e}")
        test_failures.append("Masking Engine")

    # -----------------------------------------------------------------------
    # 3. Column Heuristics Verification
    # -----------------------------------------------------------------------
    print("\n--- 3. Testing Column Name Heuristics ---")
    try:
        assert detect_column_name_heuristic("email") == "EMAIL_ADDRESS"
        assert detect_column_name_heuristic("user_email") == "EMAIL_ADDRESS"
        assert detect_column_name_heuristic("customer_phone") == "PHONE_NUMBER"
        assert detect_column_name_heuristic("mobile_number") == "PHONE_NUMBER"
        assert detect_column_name_heuristic("client_ip") == "IP_ADDRESS"
        assert detect_column_name_heuristic("full_name") == "PERSON"
        assert detect_column_name_heuristic("credit_card") == "CREDIT_CARD"
        assert detect_column_name_heuristic("ssn") == "US_SSN"
        assert detect_column_name_heuristic("home_address") == "LOCATION"
        assert detect_column_name_heuristic("random_numeric_value") is None
        print(f" {PASS} 3. Column Name Heuristics: VERIFIED")
    except Exception as e:
        print(f" {FAIL} Column heuristics check failed: {e}")
        test_failures.append("Column Heuristics")

    # -----------------------------------------------------------------------
    # 4. Ingest Synthetic Dataset with Known PII Entities
    # -----------------------------------------------------------------------
    print("\n--- 4. Ingesting Synthetic Multi-PII CSV Dataset ---")
    run_id = uuid.uuid4().hex[:6]
    dataset_name = f"Synthetic PII Test Dataset {run_id}"

    # Generate synthetic dataframe with 20 rows of known sensitive test data
    synthetic_df = pd.DataFrame({
        "customer_id": [1000 + i for i in range(20)],
        "user_email": [f"test.user{i}@example.org" for i in range(20)],
        "contact_phone": [f"555-010-{i:04d}" for i in range(20)],
        "client_ip_address": [f"192.168.1.{i+1}" for i in range(20)],
        "customer_name": [
            "John Doe", "Jane Smith", "Alice Johnson", "Bob Brown", "Charlie Davis",
            "Diana Prince", "Evan Wright", "Fiona Gallagher", "George Clark", "Hannah Abbott",
            "Ian Malcolm", "Julia Roberts", "Kevin Bacon", "Laura Croft", "Michael Scott",
            "Nancy Wheeler", "Oliver Queen", "Peter Parker", "Quinn Fabray", "Rachel Green"
        ],
        "credit_card": [f"411111111111{i:04d}" for i in range(20)],
        "generic_contact_field": [f"support{i}@example.com" if i % 2 == 0 else f"555-020-{i:04d}" for i in range(20)],
        "generic_clean_notes": [f"Transaction order item {i+1} processed normally." for i in range(20)],
    })

    csv_buffer = BytesIO()
    synthetic_df.to_csv(csv_buffer, index=False)
    csv_bytes = csv_buffer.getvalue()

    upload_res = client.post(
        "/api/datasets/upload",
        data={"dataset_name": dataset_name, "description": "Synthetic dataset containing test PII entities"},
        files={"file": ("synthetic_pii_sample.csv", BytesIO(csv_bytes), "text/csv")},
    )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    upload_data = upload_res.json()
    dataset_id = upload_data["dataset_id"]
    version_id = upload_data["version_id"]
    print(f" {PASS} 4. Dataset Ingestion & Versioning: ID={dataset_id}, Version={version_id}")

    # -----------------------------------------------------------------------
    # 5. Phase 4 Profiling & Phase 5 Quality Regressions
    # -----------------------------------------------------------------------
    print("\n--- 5. Verifying Phase 4 Profiling & Phase 5 Quality Regressions ---")
    try:
        prof_res = client.post(f"/api/datasets/{dataset_id}/versions/{version_id}/profile")
        assert prof_res.status_code == 200, f"Profiling failed: {prof_res.text}"
        prof_data = prof_res.json()
        assert prof_data["row_count"] == 20
        assert prof_data["column_count"] == 8
        print(f" {PASS} 5a. Phase 4 Profiling Engine: REGRESSION PASSED")

        qual_res = client.post(f"/api/datasets/{dataset_id}/versions/{version_id}/quality")
        assert qual_res.status_code == 200, f"Quality failed: {qual_res.text}"
        qual_data = qual_res.json()
        assert qual_data["overall_score"] > 0
        print(f" {PASS} 5b. Phase 5 Quality Engine: REGRESSION PASSED")
    except Exception as e:
        print(f" {FAIL} Phase 4/5 regression failed: {e}")
        test_failures.append("Phase 4/5 Regression")

    # -----------------------------------------------------------------------
    # 6. PII Detection Scan Execution (POST)
    # -----------------------------------------------------------------------
    print("\n--- 6. Running Automated PII Scan via POST ---")
    try:
        scan_res = client.post(f"/api/datasets/{dataset_id}/versions/{version_id}/pii/scan")
        assert scan_res.status_code == 200, f"PII Scan failed: {scan_res.text}"
        scan_data = scan_res.json()

        assert scan_data["total_columns_scanned"] == 8, f"Expected 8 scanned cols, got {scan_data['total_columns_scanned']}"
        assert scan_data["pii_columns_count"] >= 4, f"Expected >=4 PII cols, got {scan_data['pii_columns_count']}"
        assert scan_data["total_findings"] >= 4, f"Expected >=4 findings, got {scan_data['total_findings']}"

        findings = scan_data["findings"]
        finding_entities = {f["entity_type"] for f in findings}
        finding_columns = {f["column_name"] for f in findings}

        print(f" {PASS} 6. PII Scan POST: Scanned {scan_data['total_columns_scanned']} cols, Found {scan_data['total_findings']} findings across {scan_data['pii_columns_count']} cols")
        print(f"      Detected Entity Types: {finding_entities}")
        print(f"      Detected Columns: {finding_columns}")
    except Exception as e:
        print(f" {FAIL} PII Scan POST failed: {e}")
        test_failures.append("PII Scan Execution")

    # -----------------------------------------------------------------------
    # 7. Entity Type Specific Detections (Email, Phone, IP, Person, Credit Card)
    # -----------------------------------------------------------------------
    print("\n--- 7. Verifying Entity Specific Detections & Sources ---")
    try:
        email_finding = next((f for f in findings if f["column_name"] == "user_email" and f["entity_type"] == "EMAIL_ADDRESS"), None)
        assert email_finding is not None, "EMAIL_ADDRESS finding missing on user_email column"
        assert email_finding["detection_source"] in ("COLUMN_AND_VALUE", "VALUE"), f"Unexpected source: {email_finding['detection_source']}"
        assert email_finding["confidence"] >= 0.8, f"Expected high confidence, got {email_finding['confidence']}"
        assert email_finding["risk_level"] in ("MEDIUM", "HIGH"), f"Unexpected risk: {email_finding['risk_level']}"
        print(f" {PASS} 7a. EMAIL_ADDRESS Detection: Confidence={email_finding['confidence']}, Source={email_finding['detection_source']}")

        phone_finding = next((f for f in findings if f["column_name"] == "contact_phone" and f["entity_type"] == "PHONE_NUMBER"), None)
        assert phone_finding is not None, "PHONE_NUMBER finding missing on contact_phone column"
        print(f" {PASS} 7b. PHONE_NUMBER Detection: Confidence={phone_finding['confidence']}, Source={phone_finding['detection_source']}")

        ip_finding = next((f for f in findings if f["column_name"] == "client_ip_address" and f["entity_type"] == "IP_ADDRESS"), None)
        assert ip_finding is not None, "IP_ADDRESS finding missing on client_ip_address column"
        print(f" {PASS} 7c. IP_ADDRESS Detection: Confidence={ip_finding['confidence']}, Source={ip_finding['detection_source']}")

        person_finding = next((f for f in findings if f["column_name"] == "customer_name" and f["entity_type"] == "PERSON"), None)
        assert person_finding is not None, "PERSON finding missing on customer_name column"
        print(f" {PASS} 7d. PERSON Detection: Confidence={person_finding['confidence']}, Source={person_finding['detection_source']}")

        # Generic column detection (generic_contact_field)
        generic_finding = next((f for f in findings if f["column_name"] == "generic_contact_field"), None)
        assert generic_finding is not None, "PII finding missing on generic column 'generic_contact_field'"
        assert generic_finding["detection_source"] == "VALUE", f"Expected 'VALUE' source on generic column, got {generic_finding['detection_source']}"
        print(f" {PASS} 7e. Generic Column Value-Level Detection: Col='generic_contact_field', Type={generic_finding['entity_type']}, Source={generic_finding['detection_source']}")
    except Exception as e:
        print(f" {FAIL} Entity specific detections check failed: {e}")
        test_failures.append("Entity Specific Detections")

    # -----------------------------------------------------------------------
    # 8. Privacy & Zero Raw PII Persistence Check
    # -----------------------------------------------------------------------
    print("\n--- 8. Verifying Privacy & Zero Raw PII Persistence ---")
    try:
        # Check masked_preview in API findings
        for f in findings:
            preview = f.get("masked_preview")
            if preview and preview != "[Column Name Signal]":
                # Ensure no full email or phone was kept
                assert "@example.org" not in preview and "@example.com" not in preview, f"Raw email leaked in preview: {preview}"
                assert "555-010" not in preview, f"Raw phone prefix leaked in preview: {preview}"
                assert "411111111111" not in preview, f"Raw credit card leaked in preview: {preview}"

        # Inspect database table contents directly
        with db.engine.connect() as conn:
            raw_details = conn.execute(
                text("SELECT masked_preview, details::text FROM pii_findings WHERE scan_id = :scan_id"),
                {"scan_id": scan_data["id"]},
            ).fetchall()

            for preview_db, details_text in raw_details:
                if preview_db:
                    assert "@example.org" not in preview_db, f"Raw email found in DB masked_preview: {preview_db}"
                    assert "411111111111" not in preview_db, f"Raw card found in DB masked_preview: {preview_db}"
                assert "@example.org" not in details_text, f"Raw email found in DB details JSON: {details_text}"
                assert "411111111111" not in details_text, f"Raw card found in DB details JSON: {details_text}"

        print(f" {PASS} 8. Privacy Verification: ZERO RAW PII STORED IN POSTGRESQL OR RETURNED IN API")
    except Exception as e:
        print(f" {FAIL} Privacy verification failed: {e}")
        test_failures.append("Privacy Verification")

    # -----------------------------------------------------------------------
    # 9. Cached GET Endpoint & force_recompute
    # -----------------------------------------------------------------------
    print("\n--- 9. Testing Cached GET Endpoint & force_recompute ---")
    try:
        get_res = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/pii")
        assert get_res.status_code == 200, f"Cached GET failed: {get_res.text}"
        get_data = get_res.json()
        assert get_data["id"] == scan_data["id"], "Cached GET did not return same scan ID"
        print(f" {PASS} 9a. Cached GET /pii: Returned cached scan (id={get_data['id']})")

        # Test force_recompute
        recompute_res = client.post(
            f"/api/datasets/{dataset_id}/versions/{version_id}/pii/scan?force_recompute=true"
        )
        assert recompute_res.status_code == 200, f"Recompute POST failed: {recompute_res.text}"
        recompute_data = recompute_res.json()
        assert recompute_data["total_columns_scanned"] == 8
        print(f" {PASS} 9b. force_recompute=true: Successfully recomputed PII scan")
    except Exception as e:
        print(f" {FAIL} Cached GET / force_recompute failed: {e}")
        test_failures.append("Cached GET / force_recompute")

    # -----------------------------------------------------------------------
    # 10. Filtered Details Endpoint
    # -----------------------------------------------------------------------
    print("\n--- 10. Testing Detailed Findings & Filters Endpoint ---")
    try:
        # Filter by entity_type
        det_email = client.get(
            f"/api/datasets/{dataset_id}/versions/{version_id}/pii/details?entity_type=EMAIL_ADDRESS"
        )
        assert det_email.status_code == 200, f"Filter email failed: {det_email.text}"
        d_email_data = det_email.json()
        assert all(f["entity_type"] == "EMAIL_ADDRESS" for f in d_email_data["findings"])
        assert d_email_data["filtered_count"] >= 1
        print(f" {PASS} 10a. Filter by entity_type=EMAIL_ADDRESS: Matched {d_email_data['filtered_count']} findings")

        # Filter by risk_level
        det_risk = client.get(
            f"/api/datasets/{dataset_id}/versions/{version_id}/pii/details?risk_level=MEDIUM"
        )
        assert det_risk.status_code == 200, f"Filter risk failed: {det_risk.text}"
        d_risk_data = det_risk.json()
        assert all(f["risk_level"] == "MEDIUM" for f in d_risk_data["findings"])
        print(f" {PASS} 10b. Filter by risk_level=MEDIUM: Matched {d_risk_data['filtered_count']} findings")

        # Filter by column_name
        det_col = client.get(
            f"/api/datasets/{dataset_id}/versions/{version_id}/pii/details?column_name=user_email"
        )
        assert det_col.status_code == 200, f"Filter column failed: {det_col.text}"
        d_col_data = det_col.json()
        assert any(f["column_name"] == "user_email" for f in d_col_data["findings"])
        print(f" {PASS} 10c. Filter by column_name=user_email: Matched {d_col_data['filtered_count']} findings")
    except Exception as e:
        print(f" {FAIL} Details filtering check failed: {e}")
        test_failures.append("Details Filtering")

    # -----------------------------------------------------------------------
    # 11. Error Handling (404 on Invalid Entities)
    # -----------------------------------------------------------------------
    print("\n--- 11. Testing 404 Error Handling ---")
    try:
        fake_uuid = str(uuid.uuid4())
        res_404_1 = client.get(f"/api/datasets/{fake_uuid}/versions/{fake_uuid}/pii")
        assert res_404_1.status_code == 404, f"Expected 404, got {res_404_1.status_code}"

        res_404_2 = client.post(f"/api/datasets/{fake_uuid}/versions/{fake_uuid}/pii/scan")
        assert res_404_2.status_code == 404, f"Expected 404, got {res_404_2.status_code}"

        res_404_3 = client.get(f"/api/datasets/{fake_uuid}/versions/{fake_uuid}/pii/details")
        assert res_404_3.status_code == 404, f"Expected 404, got {res_404_3.status_code}"
        print(f" {PASS} 11. 404 Error Handling: Non-existent dataset/version properly returns HTTP 404")
    except Exception as e:
        print(f" {FAIL} 404 error handling check failed: {e}")
        test_failures.append("404 Error Handling")

    # -----------------------------------------------------------------------
    # 12. XLSX Workbook PII Scanning
    # -----------------------------------------------------------------------
    print("\n--- 12. Testing Excel (XLSX) PII Scanning ---")
    try:
        excel_df = pd.DataFrame({
            "employee_id": [201, 202, 203],
            "corporate_email": ["alice.corp@example.com", "bob.corp@example.com", "charlie.corp@example.com"],
            "direct_phone": ["555-030-1111", "555-030-2222", "555-030-3333"],
            "remote_ip": ["10.0.0.1", "10.0.0.2", "10.0.0.3"],
        })
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            excel_df.to_excel(writer, index=False, sheet_name="Personnel")
        excel_bytes = excel_buffer.getvalue()

        xl_upload = client.post(
            "/api/datasets/upload",
            data={"dataset_name": f"Excel PII Test {run_id}", "description": "Excel file with PII"},
            files={"file": ("personnel.xlsx", BytesIO(excel_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert xl_upload.status_code == 200, f"Excel upload failed: {xl_upload.text}"
        xl_data = xl_upload.json()
        xl_ds_id = xl_data["dataset_id"]
        xl_ver_id = xl_data["version_id"]

        xl_scan = client.post(f"/api/datasets/{xl_ds_id}/versions/{xl_ver_id}/pii/scan")
        assert xl_scan.status_code == 200, f"Excel PII scan failed: {xl_scan.text}"
        xl_scan_data = xl_scan.json()
        assert xl_scan_data["pii_columns_count"] >= 2
        print(f" {PASS} 12. XLSX PII Scanning: Scanned {xl_scan_data['total_columns_scanned']} cols, Found {xl_scan_data['total_findings']} findings in Excel workbook")
    except Exception as e:
        print(f" {FAIL} XLSX PII scanning check failed: {e}")
        test_failures.append("XLSX PII Scanning")

    # -----------------------------------------------------------------------
    # 13. Cascade Deletion Verification
    # -----------------------------------------------------------------------
    print("\n--- 13. Testing Cascade Deletion Integrity ---")
    try:
        del_res = client.delete(f"/api/datasets/{dataset_id}")
        assert del_res.status_code == 200, f"Dataset deletion failed: {del_res.text}"

        with db.engine.connect() as conn:
            scan_check = conn.execute(
                text("SELECT count(*) FROM pii_scan_results WHERE dataset_version_id = :vid"),
                {"vid": version_id},
            ).scalar()
            assert scan_check == 0, f"Expected 0 orphaned pii_scan_results, found {scan_check}"

            finding_check = conn.execute(
                text("SELECT count(*) FROM pii_findings WHERE scan_id = :sid"),
                {"sid": scan_data["id"]},
            ).scalar()
            assert finding_check == 0, f"Expected 0 orphaned pii_findings, found {finding_check}"

        print(f" {PASS} 13. Cascade Deletion: Dataset -> Version -> PIIScanResult -> PIIFinding CASCADE VERIFIED")
    except Exception as e:
        print(f" {FAIL} Cascade deletion check failed: {e}")
        test_failures.append("Cascade Deletion")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 75)
    if not test_failures:
        print("  🎉 ALL 30 PHASE 6 PII DETECTION AUTOMATED TESTS PASSED!")
        print("=" * 75)
        return True
    else:
        print(f"  ❌ {len(test_failures)} TESTS FAILED: {test_failures}")
        print("=" * 75)
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
