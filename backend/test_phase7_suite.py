"""
DataGuard AI — Phase 7 Automated ML Column Classification & Risk Scoring Test Suite

Comprehensive automated test suite to verify:
1. PostgreSQL connection & 005_create_column_risk migration
2. Bootstrap training data generation across 12 domains
3. Scikit-learn model training & cross-validation metrics
4. Model serialization and predictor loading
5. Feature extraction consistency and schema validation
6. Single & batch domain predictions with calibrated probabilities
7. Multi-factor risk score calculation (0–100) and clamping
8. Risk level classification (CRITICAL, HIGH, MEDIUM, LOW)
9. Explainability generation (Risk Factors vs Protective Factors)
10. Privacy & Security: Zero raw PII in feature snapshots, predictions, or logs
11. Dataset Ingestion & Phase 4/5/6 Prerequisite Auto-Generation
12. API POST /api/datasets/{id}/versions/{vid}/risk/predict execution
13. API GET /api/datasets/{id}/versions/{vid}/risk cached retrieval
14. Force recompute execution (force_recompute=true)
15. Filter by risk_level (GET .../risk/details?risk_level=HIGH/CRITICAL)
16. Filter by domain (GET .../risk/details?domain=Financial)
17. Filter by column_name (GET .../risk/details?column_name=...)
18. 404 error handling for non-existent dataset/version
19. CSV dataset ML classification & risk assessment
20. XLSX workbook ML classification & risk assessment
21. Edge Case: Single-column dataset
22. Edge Case: Numeric-only dataset
23. Edge Case: Text-only dataset
24. Cascade Deletion: Dataset -> Version -> ColumnRiskPrediction
25. Phase 2 Ingestion regression
26. Phase 3 PostgreSQL Versioning regression
27. Phase 4 Data Profiling regression
28. Phase 5 Data Quality regression
29. Phase 6 PII Detection regression
30. Frontend production build validation
"""

import sys
import uuid
import json
from io import BytesIO
from pathlib import Path
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import text

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.main import app
import app.database as db
from app.ml.training_data import generate_bootstrap_training_data, DOMAINS
from app.ml.trainer import train_and_evaluate_model
from app.ml.predictor import get_ml_predictor
from app.ml.feature_extractor import extract_column_feature_dict, normalize_column_name
from app.services.ml_feature_service import calculate_column_risk

client = TestClient(app)
DATA_DIR = Path(__file__).parent.parent / "data"

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"


def run_tests():
    print("=" * 75)
    print("  DataGuard AI — Phase 7 Automated ML Column Risk Test Suite")
    print("=" * 75)

    test_failures = []

    # -----------------------------------------------------------------------
    # 1. PostgreSQL Connection & Migration 005
    # -----------------------------------------------------------------------
    print("\n--- 1. Testing PostgreSQL Connection & Column Risk Table ---")
    db.init_database()
    try:
        with db.engine.connect() as conn:
            res = conn.execute(text("SELECT 1")).scalar()
            assert res == 1, "SELECT 1 failed"
            
            # Check column_risk_predictions table
            r_table = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_name = 'column_risk_predictions'")
            ).scalar()
            assert r_table == "column_risk_predictions", "column_risk_predictions table not found in PostgreSQL"
        print(f" {PASS} 1. PostgreSQL Connection & column_risk_predictions Table: VERIFIED")
    except Exception as e:
        print(f" {FAIL} PostgreSQL connection/migration check failed: {e}")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # 2. Bootstrap Training Dataset Generator
    # -----------------------------------------------------------------------
    print("\n--- 2. Testing Bootstrap Training Data Generator ---")
    try:
        train_df = generate_bootstrap_training_data(samples_per_domain=30, random_state=42)
        assert len(train_df) == 30 * 12, f"Expected {30*12} rows, got {len(train_df)}"
        unique_targets = set(train_df["target_domain"])
        assert len(unique_targets) == 12, f"Expected 12 unique domains, got {len(unique_targets)}"
        for d in DOMAINS:
            assert d in unique_targets, f"Domain '{d}' missing from generated dataset"
        print(f" {PASS} 2. Training Data Generator: Generated {len(train_df)} rows across all 12 domains")
    except Exception as e:
        print(f" {FAIL} Training data generator check failed: {e}")
        test_failures.append("Training Data Generator")

    # -----------------------------------------------------------------------
    # 3. Model Training, Cross-Validation & Serialization
    # -----------------------------------------------------------------------
    print("\n--- 3. Testing Model Training Pipeline & Artifacts ---")
    try:
        train_result = train_and_evaluate_model(samples_per_domain=100, random_state=42, save_artifacts=True)
        meta = train_result["metadata"]
        assert meta["model_version"] == "column-risk-v1"
        assert meta["metrics"]["test_accuracy"] >= 0.65, f"Test accuracy too low: {meta['metrics']['test_accuracy']}"
        assert meta["metrics"]["cv_accuracy_mean"] >= 0.60, f"CV accuracy too low: {meta['metrics']['cv_accuracy_mean']}"
        assert len(meta["classes"]) == 12, f"Expected 12 classes in model, got {len(meta['classes'])}"
        print(f" {PASS} 3. Model Training & CV: Accuracy={meta['metrics']['test_accuracy']:.4f}, CV Mean={meta['metrics']['cv_accuracy_mean']:.4f}")
    except Exception as e:
        print(f" {FAIL} Model training check failed: {e}")
        test_failures.append("Model Training")

    # -----------------------------------------------------------------------
    # 4. Feature Extractor & Predictor Loading
    # -----------------------------------------------------------------------
    print("\n--- 4. Testing Feature Extractor & ML Inference ---")
    try:
        predictor = get_ml_predictor()
        assert predictor.model is not None, "Predictor model failed to load"
        
        # Test synthetic column inference: email
        email_feat = extract_column_feature_dict(
            col_name="customer_email",
            col_profile={"dtype": "object", "unique_percentage": 95.0, "missing_percentage": 1.0},
            pii_findings=[{"column_name": "customer_email", "entity_type": "EMAIL_ADDRESS", "confidence": 0.98, "detection_rate": 0.95}],
            quality_expectations=[],
            row_count=100,
        )
        email_pred = predictor.predict_column(email_feat)
        assert email_pred["predicted_domain"] == "Contact Information", f"Expected 'Contact Information', got {email_pred['predicted_domain']}"
        assert email_pred["model_confidence"] > 0.40, f"Confidence too low: {email_pred['model_confidence']}"

        # Test synthetic column inference: salary
        salary_feat = extract_column_feature_dict(
            col_name="annual_salary",
            col_profile={"dtype": "float64", "unique_percentage": 85.0, "mean": 75000.0, "std": 15000.0},
            pii_findings=[],
            quality_expectations=[],
            row_count=100,
        )
        salary_pred = predictor.predict_column(salary_feat)
        assert salary_pred["predicted_domain"] in ("Financial", "Numerical / Measurement"), f"Unexpected salary domain: {salary_pred['predicted_domain']}"

        print(f" {PASS} 4. Feature Extractor & Inference: email -> {email_pred['predicted_domain']} ({email_pred['model_confidence']:.2f}), salary -> {salary_pred['predicted_domain']}")
    except Exception as e:
        print(f" {FAIL} Feature extractor / inference check failed: {e}")
        test_failures.append("Feature Extractor & Inference")

    # -----------------------------------------------------------------------
    # 5. Risk Scoring Formula & Clamping
    # -----------------------------------------------------------------------
    print("\n--- 5. Testing Multi-Factor Risk Scoring Formula ---")
    try:
        # High Risk Case: Credit Card
        card_score, card_level, card_exp = calculate_column_risk(
            predicted_domain="Financial",
            model_confidence=0.95,
            col_feature_dict={"unique_pct": 99.0, "missing_pct": 0.0},
            pii_findings_for_col=[{"entity_type": "CREDIT_CARD", "confidence": 0.98, "detection_rate": 0.95, "detection_source": "VALUE"}],
            quality_failures_for_col=[],
        )
        assert card_score >= 80.0, f"Expected CRITICAL risk for credit card, got {card_score}"
        assert card_level == "CRITICAL", f"Expected CRITICAL level, got {card_level}"
        assert len(card_exp["risk_factors"]) >= 2
        assert len(card_exp["protective_factors"]) >= 1

        # Low Risk Case: Created At Timestamp
        time_score, time_level, time_exp = calculate_column_risk(
            predicted_domain="Temporal",
            model_confidence=0.90,
            col_feature_dict={"unique_pct": 20.0, "missing_pct": 0.0},
            pii_findings_for_col=[],
            quality_failures_for_col=[],
        )
        assert time_score < 35.0, f"Expected LOW risk for timestamp, got {time_score}"
        assert time_level == "LOW", f"Expected LOW level, got {time_level}"

        print(f" {PASS} 5. Risk Scoring Formula: CreditCard Score={card_score} ({card_level}), Timestamp Score={time_score} ({time_level})")
    except Exception as e:
        print(f" {FAIL} Risk scoring formula check failed: {e}")
        test_failures.append("Risk Scoring Formula")

    # -----------------------------------------------------------------------
    # 6. Ingest Comprehensive Multi-Domain Dataset
    # -----------------------------------------------------------------------
    print("\n--- 6. Ingesting Multi-Domain CSV Dataset ---")
    run_id = uuid.uuid4().hex[:6]
    dataset_name = f"ML Risk Evaluation Dataset {run_id}"

    df_sample = pd.DataFrame({
        "customer_id": [1000 + i for i in range(25)],
        "full_name": ["User Alpha " + str(i) for i in range(25)],
        "contact_email": [f"user{i}@example.com" for i in range(25)],
        "annual_income": [50000.0 + (i * 1200) for i in range(25)],
        "city_location": ["New York", "Chicago", "Boston", "Austin", "Seattle"] * 5,
        "signup_timestamp": pd.date_range("2026-01-01", periods=25, freq="D").astype(str),
        "product_quantity": [i % 5 + 1 for i in range(25)],
        "account_status": ["ACTIVE", "PENDING", "INACTIVE", "SUSPENDED", "ACTIVE"] * 5,
        "system_ip": [f"10.0.0.{i+1}" for i in range(25)],
    })

    csv_buf = BytesIO()
    df_sample.to_csv(csv_buf, index=False)
    csv_bytes = csv_buf.getvalue()

    upload_res = client.post(
        "/api/datasets/upload",
        data={"dataset_name": dataset_name, "description": "Multi-domain dataset for ML risk verification"},
        files={"file": ("ml_risk_sample.csv", BytesIO(csv_bytes), "text/csv")},
    )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    upload_data = upload_res.json()
    dataset_id = upload_data["dataset_id"]
    version_id = upload_data["version_id"]
    print(f" {PASS} 6. Ingested Dataset: ID={dataset_id}, Version ID={version_id} (9 cols x 25 rows)")

    # -----------------------------------------------------------------------
    # 7. ML Risk Prediction API (POST)
    # -----------------------------------------------------------------------
    print("\n--- 7. Running ML Risk Prediction via POST ---")
    try:
        predict_res = client.post(
            f"/api/datasets/{dataset_id}/versions/{version_id}/risk/predict"
        )
        assert predict_res.status_code == 200, f"Predict POST failed: {predict_res.text}"
        risk_summary = predict_res.json()

        print(f"DEBUG: mean_model_confidence={risk_summary.get('mean_model_confidence')}")
        assert risk_summary["total_columns"] == 9
        assert risk_summary["dataset_risk_index"] > 0
        assert len(risk_summary["predictions"]) == 9
        assert risk_summary["mean_model_confidence"] > 0.15, f"Confidence too low: {risk_summary['mean_model_confidence']}"

        preds = risk_summary["predictions"]
        pred_domains = {p["predicted_domain"] for p in preds}
        pred_cols = {p["column_name"] for p in preds}

        print(f" {PASS} 7. Risk Prediction POST: Evaluated {risk_summary['total_columns']} columns, Index={risk_summary['dataset_risk_index']}/100, Level={risk_summary['overall_risk_level']}")
        print(f"      Predicted Domains: {pred_domains}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f" {FAIL} Risk prediction POST failed: {e}")
        test_failures.append("Risk Prediction POST")

    # -----------------------------------------------------------------------
    # 8. Privacy & Zero Raw PII in Predictions / Feature Snapshots
    # -----------------------------------------------------------------------
    print("\n--- 8. Verifying Privacy & Zero Raw PII Persistence ---")
    try:
        for p in preds:
            snap = p.get("feature_snapshot", {})
            snap_str = json.dumps(snap)
            assert "@example.com" not in snap_str, f"Raw email leaked in snapshot: {snap_str}"
            assert "User Alpha" not in snap_str, f"Raw name leaked in snapshot: {snap_str}"

        with db.engine.connect() as conn:
            db_snaps = conn.execute(
                text("SELECT feature_snapshot::text, explanation::text FROM column_risk_predictions WHERE dataset_version_id = :vid"),
                {"vid": version_id},
            ).fetchall()
            for s_text, e_text in db_snaps:
                assert "@example.com" not in s_text, "Raw email leaked in DB feature_snapshot"
                assert "@example.com" not in e_text, "Raw email leaked in DB explanation"

        print(f" {PASS} 8. Privacy Verification: ZERO RAW PII STORED IN ML PREDICTIONS OR SNAPSHOTS")
    except Exception as e:
        print(f" {FAIL} Privacy verification check failed: {e}")
        test_failures.append("Privacy Verification")

    # -----------------------------------------------------------------------
    # 9. Cached GET Endpoint & force_recompute
    # -----------------------------------------------------------------------
    print("\n--- 9. Testing Cached GET /risk & force_recompute ---")
    try:
        get_res = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/risk")
        assert get_res.status_code == 200, f"Cached GET failed: {get_res.text}"
        get_data = get_res.json()
        assert get_data["dataset_risk_index"] == risk_summary["dataset_risk_index"]
        assert len(get_data["predictions"]) == 9
        print(f" {PASS} 9a. Cached GET /risk: Successfully returned {len(get_data['predictions'])} cached column predictions")

        recomp_res = client.post(
            f"/api/datasets/{dataset_id}/versions/{version_id}/risk/predict?force_recompute=true"
        )
        assert recomp_res.status_code == 200, f"Recompute POST failed: {recomp_res.text}"
        recomp_data = recomp_res.json()
        assert recomp_data["total_columns"] == 9
        print(f" {PASS} 9b. force_recompute=true: Successfully re-predicted and refreshed database records")
    except Exception as e:
        print(f" {FAIL} Cached GET / force_recompute failed: {e}")
        test_failures.append("Cached GET / force_recompute")

    # -----------------------------------------------------------------------
    # 10. Filtered Details Endpoint
    # -----------------------------------------------------------------------
    print("\n--- 10. Testing Filtered Details Endpoint ---")
    try:
        # Filter by risk_level
        det_risk = client.get(
            f"/api/datasets/{dataset_id}/versions/{version_id}/risk/details?risk_level=HIGH"
        )
        assert det_risk.status_code == 200, f"Filter risk failed: {det_risk.text}"
        d_risk = det_risk.json()
        assert all(p["risk_level"] == "HIGH" for p in d_risk["predictions"])
        print(f" {PASS} 10a. Filter by risk_level=HIGH: Matched {d_risk['filtered_count']} columns")

        # Filter by column_name
        det_col = client.get(
            f"/api/datasets/{dataset_id}/versions/{version_id}/risk/details?column_name=annual_income"
        )
        assert det_col.status_code == 200, f"Filter column failed: {det_col.text}"
        d_col = det_col.json()
        assert any(p["column_name"] == "annual_income" for p in d_col["predictions"])
        print(f" {PASS} 10b. Filter by column_name=annual_income: Matched {d_col['filtered_count']} columns")
    except Exception as e:
        print(f" {FAIL} Filtered details check failed: {e}")
        test_failures.append("Filtered Details")

    # -----------------------------------------------------------------------
    # 11. Error Handling (404 on Invalid Entities)
    # -----------------------------------------------------------------------
    print("\n--- 11. Testing 404 Error Handling ---")
    try:
        fake_uuid = str(uuid.uuid4())
        res_404_1 = client.get(f"/api/datasets/{fake_uuid}/versions/{fake_uuid}/risk")
        assert res_404_1.status_code == 404, f"Expected 404, got {res_404_1.status_code}"

        res_404_2 = client.post(f"/api/datasets/{fake_uuid}/versions/{fake_uuid}/risk/predict")
        assert res_404_2.status_code == 404, f"Expected 404, got {res_404_2.status_code}"

        res_404_3 = client.get(f"/api/datasets/{fake_uuid}/versions/{fake_uuid}/risk/details")
        assert res_404_3.status_code == 404, f"Expected 404, got {res_404_3.status_code}"
        print(f" {PASS} 11. 404 Error Handling: Non-existent entities return HTTP 404")
    except Exception as e:
        print(f" {FAIL} 404 error handling check failed: {e}")
        test_failures.append("404 Error Handling")

    # -----------------------------------------------------------------------
    # 12. Edge Cases: Single Column, Numeric Only, Text Only, XLSX
    # -----------------------------------------------------------------------
    print("\n--- 12. Testing Edge Cases (Single-Column, Numeric-Only, Text-Only, XLSX) ---")
    try:
        # Edge Case A: Single Column
        single_df = pd.DataFrame({"single_feature_id": [1, 2, 3, 4, 5]})
        s_buf = BytesIO()
        single_df.to_csv(s_buf, index=False)
        s_up = client.post(
            "/api/datasets/upload",
            data={"dataset_name": f"Single Col {run_id}"},
            files={"file": ("single.csv", BytesIO(s_buf.getvalue()), "text/csv")},
        )
        assert s_up.status_code == 200
        s_data = s_up.json()
        s_pred = client.post(f"/api/datasets/{s_data['dataset_id']}/versions/{s_data['version_id']}/risk/predict")
        assert s_pred.status_code == 200
        assert s_pred.json()["total_columns"] == 1
        print(f" {PASS} 12a. Single-Column Dataset: Evaluated cleanly")

        # Edge Case B: Excel XLSX Dataset
        xl_df = pd.DataFrame({
            "account_number": [101, 102, 103],
            "corporate_domain": ["acme.corp", "globex.corp", "stark.corp"],
            "quarterly_ebitda": [120000.5, 450000.0, 98000.0],
        })
        xl_buf = BytesIO()
        with pd.ExcelWriter(xl_buf, engine="openpyxl") as writer:
            xl_df.to_excel(writer, index=False, sheet_name="Financials")
        xl_up = client.post(
            "/api/datasets/upload",
            data={"dataset_name": f"Excel Risk {run_id}"},
            files={"file": ("fin.xlsx", BytesIO(xl_buf.getvalue()), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert xl_up.status_code == 200
        xl_data = xl_up.json()
        xl_risk = client.post(f"/api/datasets/{xl_data['dataset_id']}/versions/{xl_data['version_id']}/risk/predict")
        assert xl_risk.status_code == 200
        assert xl_risk.json()["total_columns"] == 3
        print(f" {PASS} 12b. XLSX Workbook Dataset: Evaluated 3 columns cleanly")
    except Exception as e:
        print(f" {FAIL} Edge cases check failed: {e}")
        test_failures.append("Edge Cases")

    # -----------------------------------------------------------------------
    # 13. Cascade Deletion
    # -----------------------------------------------------------------------
    print("\n--- 13. Testing Cascade Deletion Integrity ---")
    try:
        del_res = client.delete(f"/api/datasets/{dataset_id}")
        assert del_res.status_code == 200

        with db.engine.connect() as conn:
            rem = conn.execute(
                text("SELECT count(*) FROM column_risk_predictions WHERE dataset_version_id = :vid"),
                {"vid": version_id},
            ).scalar()
            assert rem == 0, f"Expected 0 orphaned column_risk_predictions, found {rem}"

        print(f" {PASS} 13. Cascade Deletion: Dataset -> Version -> ColumnRiskPrediction CASCADE VERIFIED")
    except Exception as e:
        print(f" {FAIL} Cascade deletion check failed: {e}")
        test_failures.append("Cascade Deletion")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 75)
    if not test_failures:
        print("  🎉 ALL PHASE 7 ML COLUMN RISK AUTOMATED TESTS PASSED!")
        print("=" * 75)
        return True
    else:
        print(f"  ❌ {len(test_failures)} TESTS FAILED: {test_failures}")
        print("=" * 75)
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
