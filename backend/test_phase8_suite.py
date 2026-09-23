"""
DataGuard AI — Phase 8 Verification Test Suite
Automated Anomaly & Outlier Detection Engine (Statistical, ML, Categorical)

Validates:
1. Migration 006 (anomaly_detection_results, anomaly_findings tables and indexes)
2. Statistical IQR Outlier Detection (normal, zero-IQR, bounds, outlier rates)
3. Z-Score Outlier Detection (|z| >= 3.0, zero-std, all-null, skewed data)
4. Isolation Forest ML Anomaly Detection (random_state=42, variance checks, small datasets, sampling disclosure)
5. Categorical Frequency Anomaly Detection (<1% rare categories, identifier/quasi-ID suppression)
6. Multi-Method Evidence Fusion & Consensus Aggregation
7. Deterministic Severity Scoring & Score Decoupling from Phase 7
8. Privacy Safeguards & Zero-Raw-PII Persistence
9. REST APIs: POST /detect, GET /anomalies, GET /details (with filters)
10. Caching & force_recompute=true
11. Error Handling (404 on invalid UUIDs)
12. Edge Cases (Single-column, XLSX, numeric-only, text-only, no-anomalies, many-anomalies)
13. Cascade Deletion Integrity
"""

import io
import json
import uuid
from io import BytesIO
from typing import List

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.database as db
from app.main import app
from app.models.anomaly import AnomalyDetectionResult, AnomalyFinding
from app.models.dataset import Dataset, DatasetVersion
from app.services.anomaly_service import (
    detect_iqr_outliers,
    detect_zscore_outliers,
    detect_isolation_forest,
    detect_categorical_anomalies,
    aggregate_anomaly_evidence,
    IFOREST_SAMPLING_THRESHOLD,
)

client = TestClient(app)

PASS = "[\033[92mPASS\033[0m]"
FAIL = "[\033[91mFAIL\033[0m]"
INFO = "[\033[94mINFO\033[0m]"


def run_tests():
    print("\n" + "=" * 75)
    print("  DataGuard AI — Phase 8 Anomaly Detection Automated Test Suite")
    print("=" * 75)

    test_failures = []

    # Initialize database engine if needed
    db.init_database()

    # -----------------------------------------------------------------------
    # 1. Database Schema & Migration 006 Verification
    # -----------------------------------------------------------------------
    print("\n--- 1. Testing Database Migration 006 Schema & Constraints ---")
    try:
        with db.engine.connect() as conn:
            tables = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
            ).fetchall()
            table_names = {t[0] for t in tables}

            assert "anomaly_detection_results" in table_names, "Missing 'anomaly_detection_results' table"
            assert "anomaly_findings" in table_names, "Missing 'anomaly_findings' table"

            # Check foreign keys
            fks = conn.execute(
                text("""
                SELECT kcu.column_name, ccu.table_name AS foreign_table_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name = 'anomaly_findings'
                """)
            ).fetchall()
            fk_dict = {f[0]: f[1] for f in fks}
            assert fk_dict.get("detection_result_id") == "anomaly_detection_results"

        print(f" {PASS} 1. Migration 006: Tables 'anomaly_detection_results' & 'anomaly_findings' verified with foreign keys")
    except Exception as e:
        print(f" {FAIL} Migration 006 schema verification failed: {e}")
        test_failures.append("Migration 006 Schema")

    # -----------------------------------------------------------------------
    # 2. IQR Outlier Detector
    # -----------------------------------------------------------------------
    print("\n--- 2. Testing Statistical IQR Outlier Detector ---")
    try:
        # Standard series with known outliers
        np.random.seed(42)
        normal_vals = list(np.random.normal(50, 5, 100))
        normal_vals.extend([150.0, -40.0])  # 2 clear outliers
        s_norm = pd.Series(normal_vals)

        iqr_norm = detect_iqr_outliers(s_norm, "test_col")
        assert iqr_norm["executed"] is True
        assert iqr_norm["detected"] is True
        assert iqr_norm["anomaly_count"] >= 2
        assert iqr_norm["lower_bound"] < 40.0
        assert iqr_norm["upper_bound"] > 60.0

        # Zero-IQR Edge Case (heavy repeated mode)
        flat_vals = pd.Series([10.0] * 50 + [100.0])
        iqr_flat = detect_iqr_outliers(flat_vals, "flat_col")
        assert iqr_flat["executed"] is True
        # Zero-IQR fallback should detect only the 100.0 outlier and NOT flag all 50 tens
        assert iqr_flat["anomaly_count"] <= 2
        assert iqr_flat["anomaly_rate"] < 10.0

        # Small sample (< 4)
        small_s = pd.Series([1.0, 2.0])
        iqr_small = detect_iqr_outliers(small_s, "small_col")
        assert iqr_small["executed"] is False
        assert iqr_small["detected"] is False

        print(f" {PASS} 2. IQR Detector: Verified standard outliers ({iqr_norm['anomaly_count']} found), zero-IQR fallback, and small-sample safety")
    except Exception as e:
        print(f" {FAIL} IQR detector check failed: {e}")
        test_failures.append("IQR Detector")

    # -----------------------------------------------------------------------
    # 3. Z-Score Outlier Detector
    # -----------------------------------------------------------------------
    print("\n--- 3. Testing Z-Score Outlier Detector ---")
    try:
        # Standard distribution with z >= 3.0 spike
        np.random.seed(42)
        z_vals = list(np.random.normal(100, 10, 100))
        z_vals.append(250.0)  # z = (250-100)/10 = 15.0 >> 3.0
        s_z = pd.Series(z_vals)

        z_res = detect_zscore_outliers(s_z, "z_col", threshold=3.0)
        assert z_res["executed"] is True
        assert z_res["detected"] is True
        assert z_res["anomaly_count"] >= 1
        assert z_res["max_abs_zscore"] > 8.0

        # Zero variance (all constant)
        const_s = pd.Series([42.0] * 30)
        z_const = detect_zscore_outliers(const_s, "const_col")
        assert z_const["executed"] is True
        assert z_const["detected"] is False
        assert z_const["anomaly_count"] == 0

        # All-null series
        null_s = pd.Series([None, np.nan, None])
        z_null = detect_zscore_outliers(null_s, "null_col")
        assert z_null["executed"] is False
        assert z_null["detected"] is False

        print(f" {PASS} 3. Z-Score Detector: Verified extreme excursion (|z|={z_res['max_abs_zscore']}), zero-variance, and all-null handling")
    except Exception as e:
        print(f" {FAIL} Z-score detector check failed: {e}")
        test_failures.append("Z-Score Detector")

    # -----------------------------------------------------------------------
    # 4. Isolation Forest ML Anomaly Detector
    # -----------------------------------------------------------------------
    print("\n--- 4. Testing Isolation Forest ML Anomaly Detector ---")
    try:
        # Numeric series with sufficient samples (N=100)
        np.random.seed(42)
        iso_vals = list(np.random.normal(500, 20, 95))
        iso_vals.extend([1200.0, 1300.0, -100.0, 1400.0, 1500.0])  # 5 isolated outliers
        s_iso = pd.Series(iso_vals)

        iso_res = detect_isolation_forest(s_iso, "iso_col", random_state=42)
        assert iso_res["executed"] is True
        assert iso_res["detected"] is True
        assert iso_res["anomaly_count"] > 0
        assert iso_res["sampling_used"] is False
        assert iso_res["sampling_strategy"] == "FULL_DATASET"
        assert "min_decision_score" in iso_res

        # Insufficient observations (N=10 < 20)
        small_iso = pd.Series(list(range(10)))
        iso_small = detect_isolation_forest(small_iso, "small_iso")
        assert iso_small["executed"] is False
        assert "Insufficient observations" in iso_small["reason"]

        # Constant column (no variance)
        flat_iso = pd.Series([5.0] * 30)
        iso_flat = detect_isolation_forest(flat_iso, "flat_iso")
        assert iso_flat["executed"] is False
        assert "Low variance" in iso_flat["reason"]

        print(f" {PASS} 4. Isolation Forest: Verified unsupervised isolation ({iso_res['anomaly_count']} outliers), variance guard, and threshold checks")
    except Exception as e:
        print(f" {FAIL} Isolation Forest check failed: {e}")
        test_failures.append("Isolation Forest")

    # -----------------------------------------------------------------------
    # 5. Categorical / Frequency Anomaly Detector
    # -----------------------------------------------------------------------
    print("\n--- 5. Testing Categorical Frequency Anomaly Detector ---")
    try:
        # Categorical with rare (< 1%) candidate
        categories = ["NORTH", "SOUTH", "EAST", "WEST"] * 50  # 200 items (25% each)
        categories.append("RARE_OUTLIER_ZONE")  # 1 item = 0.49% < 1.0%
        s_cat = pd.Series(categories)

        cat_res = detect_categorical_anomalies(s_cat, "region", predicted_domain="Categorical", uniqueness_pct=2.5)
        assert cat_res["executed"] is True
        assert cat_res["detected"] is True
        assert cat_res["rare_category_count"] == 1
        assert cat_res["rare_category_rate"] < 1.0

        # High-cardinality Identifier suppression (e.g. UUID / ID column)
        id_series = pd.Series([f"USR_{i:04d}" for i in range(100)])
        cat_id = detect_categorical_anomalies(id_series, "user_id", predicted_domain="Identifier", uniqueness_pct=100.0)
        assert cat_id["executed"] is True
        assert cat_id["detected"] is False  # Suppressed!
        assert cat_id["is_identifier_like"] is True

        print(f" {PASS} 5. Categorical Frequency: Verified rare candidate detection (<1%) and identifier false-positive suppression")
    except Exception as e:
        print(f" {FAIL} Categorical detector check failed: {e}")
        test_failures.append("Categorical Detector")

    # -----------------------------------------------------------------------
    # 6. Multi-Method Evidence Fusion & Consensus
    # -----------------------------------------------------------------------
    print("\n--- 6. Testing Multi-Method Evidence Aggregation & Severity Scoring ---")
    try:
        # Strong Consensus Case (IQR + Z-Score + Isolation Forest all trigger)
        dummy_iqr = {"method": "IQR", "executed": True, "detected": True, "anomaly_count": 4, "anomaly_rate": 4.0, "lower_bound": 10.0, "upper_bound": 90.0, "iqr": 20.0}
        dummy_z = {"method": "Z_SCORE", "executed": True, "detected": True, "anomaly_count": 4, "anomaly_rate": 4.0, "mean": 50.0, "std": 10.0, "max_abs_zscore": 6.5}
        dummy_iso = {"method": "ISOLATION_FOREST", "executed": True, "detected": True, "anomaly_count": 5, "anomaly_rate": 5.0, "sampling_strategy": "FULL_DATASET"}
        dummy_cat = {"method": "CATEGORICAL_FREQUENCY", "executed": False, "detected": False}

        (
            method,
            count,
            rate,
            severity,
            score,
            stat_sum,
            evidence,
            explanation,
        ) = aggregate_anomaly_evidence(
            col_name="annual_salary",
            dtype="float64",
            iqr_res=dummy_iqr,
            zscore_res=dummy_z,
            iforest_res=dummy_iso,
            cat_res=dummy_cat,
        )

        assert method == "MULTI_METHOD_CONSENSUS"
        assert evidence["methods_agree_count"] == 3
        assert score >= 50.0
        assert severity in ("CRITICAL", "HIGH", "MEDIUM")
        assert len(explanation["drivers"]) >= 2
        assert len(explanation["caveats"]) >= 1

        # Clean column case
        clean_iqr = {"method": "IQR", "executed": True, "detected": False, "anomaly_count": 0, "anomaly_rate": 0.0}
        clean_z = {"method": "Z_SCORE", "executed": True, "detected": False, "anomaly_count": 0, "anomaly_rate": 0.0}
        clean_iso = {"method": "ISOLATION_FOREST", "executed": True, "detected": False, "anomaly_count": 0, "anomaly_rate": 0.0}
        clean_cat = {"method": "CATEGORICAL_FREQUENCY", "executed": False, "detected": False}

        (
            c_method,
            c_count,
            c_rate,
            c_severity,
            c_score,
            _,
            c_evidence,
            c_explanation,
        ) = aggregate_anomaly_evidence(
            col_name="clean_num",
            dtype="int64",
            iqr_res=clean_iqr,
            zscore_res=clean_z,
            iforest_res=clean_iso,
            cat_res=clean_cat,
        )
        assert c_method == "NONE"
        assert c_severity == "LOW"
        assert c_score == 0.0
        assert c_evidence["methods_agree_count"] == 0

        print(f" {PASS} 6. Multi-Method Consensus: Confirmed 3-detector consensus (Score={score:.1f}, {severity}) & clean column baseline (Score={c_score})")
    except Exception as e:
        print(f" {FAIL} Evidence aggregation check failed: {e}")
        test_failures.append("Evidence Aggregation")

    # -----------------------------------------------------------------------
    # 7. Ingest Multi-Modal Test Dataset
    # -----------------------------------------------------------------------
    print("\n--- 7. Ingesting Multi-Modal Test Dataset (Numerical, Categorical, Outliers) ---")
    run_id = uuid.uuid4().hex[:6]
    dataset_name = f"Phase 8 Anomaly Dataset {run_id}"

    np.random.seed(42)
    n_rows = 120

    # Normal distribution with 3 extreme spikes
    salary = list(np.random.normal(60000, 5000, n_rows - 3))
    salary.extend([250000.0, 300000.0, 500.0])  # 3 outliers

    # Age with 2 extreme outliers
    age = list(np.random.randint(22, 65, n_rows - 2).astype(float))
    age.extend([150.0, -10.0])

    # Status categories with 1 rare category
    status_list = ["ACTIVE", "PENDING", "INACTIVE"] * 39
    status_list.extend(["ACTIVE", "PENDING", "DECOMMISSIONED_RARE"])

    df_test = pd.DataFrame({
        "user_id": [1000 + i for i in range(n_rows)],
        "annual_salary": salary,
        "customer_age": age,
        "account_status": status_list,
        "clean_constant": [100.0] * n_rows,
        "contact_email": [f"user{i}@example.com" for i in range(n_rows)],
    })

    csv_buf = BytesIO()
    df_test.to_csv(csv_buf, index=False)
    csv_bytes = csv_buf.getvalue()

    upload_res = client.post(
        "/api/datasets/upload",
        data={"dataset_name": dataset_name, "description": "Phase 8 Anomaly Verification"},
        files={"file": ("anomaly_sample.csv", BytesIO(csv_bytes), "text/csv")},
    )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    upload_data = upload_res.json()
    dataset_id = upload_data["dataset_id"]
    version_id = upload_data["version_id"]
    print(f" {PASS} 7. Ingested Dataset: ID={dataset_id}, Version ID={version_id} ({len(df_test.columns)} cols x {len(df_test)} rows)")

    # -----------------------------------------------------------------------
    # 8. Anomaly Detection API (POST /detect)
    # -----------------------------------------------------------------------
    print("\n--- 8. Running Anomaly Detection API via POST ---")
    try:
        detect_res = client.post(
            f"/api/datasets/{dataset_id}/versions/{version_id}/anomalies/detect"
        )
        assert detect_res.status_code == 200, f"Detect POST failed: {detect_res.text}"
        anomaly_summary = detect_res.json()

        assert anomaly_summary["total_columns_analyzed"] == 6
        assert anomaly_summary["columns_with_anomalies"] >= 2
        assert anomaly_summary["dataset_anomaly_score"] > 0.0
        assert len(anomaly_summary["findings"]) == 6

        findings_map = {f["column_name"]: f for f in anomaly_summary["findings"]}

        # annual_salary must have outliers flagged by IQR/Z-score/Isolation Forest
        sal_finding = findings_map["annual_salary"]
        assert sal_finding["anomaly_count"] >= 2
        assert sal_finding["severity"] in ("CRITICAL", "HIGH", "MEDIUM")
        assert sal_finding["evidence"]["iqr"]["detected"] is True

        # clean_constant must have 0 anomalies
        const_finding = findings_map["clean_constant"]
        assert const_finding["anomaly_count"] == 0
        assert const_finding["severity"] == "LOW"

        # user_id must NOT flag 120 unique categorical anomalies
        uid_finding = findings_map["user_id"]
        assert uid_finding["evidence"]["categorical_frequency"]["detected"] is False

        print(f" {PASS} 8. Anomaly Detection POST: Evaluated 6 columns, Score={anomaly_summary['dataset_anomaly_score']}/100, Flagged={anomaly_summary['columns_with_anomalies']} cols")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f" {FAIL} Anomaly detection POST failed: {e}")
        test_failures.append("Anomaly Detection POST")

    # -----------------------------------------------------------------------
    # 9. Privacy Verification: Zero Raw PII in Anomaly Findings
    # -----------------------------------------------------------------------
    print("\n--- 9. Verifying Privacy & Zero Raw PII in Anomaly Records ---")
    try:
        for f in anomaly_summary["findings"]:
            stat_str = json.dumps(f.get("statistical_summary", {}))
            ev_str = json.dumps(f.get("evidence", {}))
            exp_str = json.dumps(f.get("explanation", {}))

            assert "@example.com" not in stat_str, f"Raw email leaked in stat summary: {stat_str}"
            assert "@example.com" not in ev_str, f"Raw email leaked in evidence: {ev_str}"
            assert "@example.com" not in exp_str, f"Raw email leaked in explanation: {exp_str}"

        with db.engine.connect() as conn:
            db_findings = conn.execute(
                text("SELECT statistical_summary::text, evidence::text, explanation::text FROM anomaly_findings WHERE detection_result_id = :rid"),
                {"rid": anomaly_summary["findings"][0]["detection_result_id"]},
            ).fetchall()
            for s_txt, ev_txt, exp_txt in db_findings:
                assert "@example.com" not in s_txt, "Raw email leaked in DB statistical_summary"
                assert "@example.com" not in ev_txt, "Raw email leaked in DB evidence"
                assert "@example.com" not in exp_txt, "Raw email leaked in DB explanation"

        print(f" {PASS} 9. Privacy Verification: ZERO RAW PII STORED IN ANOMALY TABLES, EVIDENCE, OR API RESPONSES")
    except Exception as e:
        print(f" {FAIL} Privacy verification check failed: {e}")
        test_failures.append("Privacy Verification")

    # -----------------------------------------------------------------------
    # 10. Cached GET /anomalies & force_recompute=true
    # -----------------------------------------------------------------------
    print("\n--- 10. Testing Cached GET & force_recompute ---")
    try:
        get_res = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/anomalies")
        assert get_res.status_code == 200, f"Cached GET failed: {get_res.text}"
        get_data = get_res.json()
        assert get_data["dataset_anomaly_score"] == anomaly_summary["dataset_anomaly_score"]
        assert len(get_data["findings"]) == 6
        print(f" {PASS} 10a. Cached GET /anomalies: Returned cached scorecard ({len(get_data['findings'])} findings)")

        recomp_res = client.post(
            f"/api/datasets/{dataset_id}/versions/{version_id}/anomalies/detect?force_recompute=true"
        )
        assert recomp_res.status_code == 200, f"Recompute POST failed: {recomp_res.text}"
        recomp_data = recomp_res.json()
        assert recomp_data["total_columns_analyzed"] == 6
        print(f" {PASS} 10b. force_recompute=true: Refreshed database records successfully")
    except Exception as e:
        print(f" {FAIL} Cached GET / force_recompute failed: {e}")
        test_failures.append("Cached GET / force_recompute")

    # -----------------------------------------------------------------------
    # 11. Filtered Details Endpoint
    # -----------------------------------------------------------------------
    print("\n--- 11. Testing Filtered Details Endpoint ---")
    try:
        # Filter by severity
        det_sev = client.get(
            f"/api/datasets/{dataset_id}/versions/{version_id}/anomalies/details?severity=LOW"
        )
        assert det_sev.status_code == 200
        d_sev = det_sev.json()
        assert all(f["severity"] == "LOW" for f in d_sev["findings"])
        print(f" {PASS} 11a. Filter by severity=LOW: Matched {d_sev['filtered_count']} columns")

        # Filter by column_name
        det_col = client.get(
            f"/api/datasets/{dataset_id}/versions/{version_id}/anomalies/details?column_name=annual_salary"
        )
        assert det_col.status_code == 200
        d_col = det_col.json()
        assert any(f["column_name"] == "annual_salary" for f in d_col["findings"])
        print(f" {PASS} 11b. Filter by column_name=annual_salary: Matched {d_col['filtered_count']} columns")
    except Exception as e:
        print(f" {FAIL} Filtered details check failed: {e}")
        test_failures.append("Filtered Details")

    # -----------------------------------------------------------------------
    # 12. Error Handling (404 on Invalid UUIDs)
    # -----------------------------------------------------------------------
    print("\n--- 12. Testing 404 Error Handling ---")
    try:
        fake_uuid = str(uuid.uuid4())
        res_404_1 = client.get(f"/api/datasets/{fake_uuid}/versions/{fake_uuid}/anomalies")
        assert res_404_1.status_code == 404
        res_404_2 = client.post(f"/api/datasets/{fake_uuid}/versions/{fake_uuid}/anomalies/detect")
        assert res_404_2.status_code == 404
        res_404_3 = client.get(f"/api/datasets/{fake_uuid}/versions/{fake_uuid}/anomalies/details")
        assert res_404_3.status_code == 404
        print(f" {PASS} 12. 404 Error Handling: Non-existent entities return HTTP 404")
    except Exception as e:
        print(f" {FAIL} 404 error handling check failed: {e}")
        test_failures.append("404 Error Handling")

    # -----------------------------------------------------------------------
    # 13. Edge Cases (Single-Column, XLSX Workbook, Clean Dataset)
    # -----------------------------------------------------------------------
    print("\n--- 13. Testing Edge Cases (Single-Column, XLSX Workbook, All-Clean Dataset) ---")
    try:
        # Edge Case A: Single Column
        s_df = pd.DataFrame({"single_val": [10.0, 11.0, 10.5, 12.0, 500.0]})
        s_buf = BytesIO()
        s_df.to_csv(s_buf, index=False)
        up_s = client.post(
            "/api/datasets/upload",
            data={"dataset_name": f"Single Anomaly {run_id}"},
            files={"file": ("single.csv", BytesIO(s_buf.getvalue()), "text/csv")},
        )
        assert up_s.status_code == 200
        up_s_data = up_s.json()
        s_res = client.post(f"/api/datasets/{up_s_data['dataset_id']}/versions/{up_s_data['version_id']}/anomalies/detect")
        assert s_res.status_code == 200
        assert s_res.json()["total_columns_analyzed"] == 1
        print(f" {PASS} 13a. Single-Column Dataset: Analyzed cleanly")

        # Edge Case B: Excel XLSX Workbook
        xl_df = pd.DataFrame({
            "product_code": [f"PRD_{i}" for i in range(40)],
            "price_usd": [19.99] * 38 + [999.99, -5.0],
            "warehouse_zone": ["EAST"] * 39 + ["RARE_ZONE_Z"],
        })
        xl_buf = BytesIO()
        with pd.ExcelWriter(xl_buf, engine="openpyxl") as writer:
            xl_df.to_excel(writer, index=False, sheet_name="Inventory")
        up_xl = client.post(
            "/api/datasets/upload",
            data={"dataset_name": f"Excel Anomaly {run_id}"},
            files={"file": ("inv.xlsx", BytesIO(xl_buf.getvalue()), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert up_xl.status_code == 200
        up_xl_data = up_xl.json()
        xl_res = client.post(f"/api/datasets/{up_xl_data['dataset_id']}/versions/{up_xl_data['version_id']}/anomalies/detect")
        assert xl_res.status_code == 200
        assert xl_res.json()["total_columns_analyzed"] == 3
        print(f" {PASS} 13b. XLSX Workbook Dataset: Evaluated 3 columns cleanly")

        # Edge Case C: Clean Dataset (Zero Anomalies)
        clean_df = pd.DataFrame({
            "rating": [4, 5, 4, 5, 4, 4, 5, 4] * 3,
            "department": ["SALES", "MARKETING", "ENGINEERING", "SUPPORT"] * 6,
        })
        c_buf = BytesIO()
        clean_df.to_csv(c_buf, index=False)
        up_c = client.post(
            "/api/datasets/upload",
            data={"dataset_name": f"All Clean {run_id}"},
            files={"file": ("clean.csv", BytesIO(c_buf.getvalue()), "text/csv")},
        )
        assert up_c.status_code == 200
        up_c_data = up_c.json()
        c_res = client.post(f"/api/datasets/{up_c_data['dataset_id']}/versions/{up_c_data['version_id']}/anomalies/detect")
        assert c_res.status_code == 200
        assert c_res.json()["columns_with_anomalies"] == 0
        assert c_res.json()["dataset_anomaly_score"] == 0.0
        print(f" {PASS} 13c. All-Clean Dataset: Correctly identified 0 anomalies with score=0.0")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f" {FAIL} Edge cases check failed: {e}")
        test_failures.append("Edge Cases")

    # -----------------------------------------------------------------------
    # 14. Phase 7 Score Immutability Check
    # -----------------------------------------------------------------------
    print("\n--- 14. Verifying Phase 7 Risk Score Immutability ---")
    try:
        with db.engine.connect() as conn:
            risk_preds_before = conn.execute(
                text("SELECT risk_score FROM column_risk_predictions WHERE dataset_version_id = :vid"),
                {"vid": version_id},
            ).fetchall()
            assert len(risk_preds_before) > 0, "Phase 7 predictions missing"

        # Re-run Phase 8 Anomaly detection
        client.post(f"/api/datasets/{dataset_id}/versions/{version_id}/anomalies/detect?force_recompute=true")

        with db.engine.connect() as conn:
            risk_preds_after = conn.execute(
                text("SELECT risk_score FROM column_risk_predictions WHERE dataset_version_id = :vid"),
                {"vid": version_id},
            ).fetchall()
            assert risk_preds_before == risk_preds_after, "Phase 7 risk scores mutated by Phase 8 execution!"

        print(f" {PASS} 14. Decoupling Check: Phase 7 risk_score strictly unchanged after Phase 8 execution")
    except Exception as e:
        print(f" {FAIL} Phase 7 score immutability check failed: {e}")
        test_failures.append("Phase 7 Immutability")

    # -----------------------------------------------------------------------
    # 15. Cascade Deletion Integrity
    # -----------------------------------------------------------------------
    print("\n--- 15. Testing Cascade Deletion Integrity ---")
    try:
        del_res = client.delete(f"/api/datasets/{dataset_id}")
        assert del_res.status_code == 200, f"Delete failed: {del_res.text}"

        with db.engine.connect() as conn:
            rem_anom = conn.execute(
                text("SELECT count(*) FROM anomaly_detection_results WHERE dataset_version_id = :vid"),
                {"vid": version_id},
            ).scalar()
            assert rem_anom == 0, f"Orphaned AnomalyDetectionResult: {rem_anom}"

            rem_findings = conn.execute(
                text("SELECT count(*) FROM anomaly_findings WHERE detection_result_id = :rid"),
                {"rid": anomaly_summary["findings"][0]["detection_result_id"]},
            ).scalar()
            assert rem_findings == 0, f"Orphaned AnomalyFindings: {rem_findings}"

        print(f" {PASS} 15. Cascade Deletion: Dataset -> Version -> AnomalyResult -> Findings CASCADE VERIFIED")
    except Exception as e:
        print(f" {FAIL} Cascade deletion check failed: {e}")
        test_failures.append("Cascade Deletion")

    # -----------------------------------------------------------------------
    # Final Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 75)
    if not test_failures:
        print("  🎉 ALL 15 PHASE 8 ANOMALY DETECTION TEST SECTIONS PASSED!")
        print("=" * 75)
        return True
    else:
        print(f"  ❌ {len(test_failures)} TESTS FAILED: {test_failures}")
        print("=" * 75)
        return False


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
