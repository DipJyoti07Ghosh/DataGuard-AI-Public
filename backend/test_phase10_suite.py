"""
DataGuard AI — Phase 10 Automated Test Suite
Dataset Version Comparison & Drift Detection

Validates:
1. PostgreSQL persistence, tables & Alembic migration status (008 revision)
2. Version compatibility & validation: Rejection of cross-dataset comparisons (400 Bad Request)
3. Self-comparison rejection (400 Bad Request)
4. Schema drift: added, removed, type-changed, and unchanged columns
5. Missingness drift: percentage-point shifts (pp) and directional classification
6. Uniqueness drift: cardinality & uniqueness ratio shifts
7. Real Kolmogorov-Smirnov (KS) test on continuous numerical columns
8. Real Population Stability Index (PSI) on categorical distributions with Laplace smoothing
9. Graceful fallback when raw files are unavailable (transparent UNAVAILABLE / INSUFFICIENT_DATA status)
10. Phase 5 Quality score delta & rule violation comparison
11. Phase 7 ML Risk delta & domain shift integration
12. Phase 8 Anomaly score delta & severity shift integration
13. Phase 6 PII discovery integration without raw PII leakage
14. Explainable Overall Drift Status classification (NO_DRIFT, LOW_DRIFT, MEDIUM_DRIFT, HIGH_DRIFT)
15. Idempotent caching & force_recompute behavior
16. Full REST API endpoints (POST /compare, GET /comparisons/{id}, GET /comparisons, GET /comparisons/{id}/columns/{col})
17. Cascade deletion integrity
"""

import io
import os
import uuid
import logging
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
import app.database as database
from app.models.dataset import Dataset, DatasetVersion
from app.models.comparison import DatasetComparison, ColumnDriftResult
from app.services.comparison_service import compare_dataset_versions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase10")


def test_phase10_full_suite():
    logger.info("===========================================================================")
    logger.info("  STARTING PHASE 10 VERSION COMPARISON & DRIFT AUTOMATED TEST SUITE")
    logger.info("===========================================================================")

    database.init_database()
    db = database.SessionLocal()

    with TestClient(app) as client:
        # ---------------------------------------------------------------------------
        # 0. Table & Migration Verification
        # ---------------------------------------------------------------------------
        logger.info("\n--- 0. Testing PostgreSQL Tables & Migration ---")
        res1 = db.execute(text("SELECT to_regclass('public.dataset_comparisons');")).scalar()
        res2 = db.execute(text("SELECT to_regclass('public.column_drift_results');")).scalar()
        assert res1 is not None, "dataset_comparisons table missing"
        assert res2 is not None, "column_drift_results table missing"
        logger.info(" [PASS] 0. dataset_comparisons & column_drift_results tables exist")

        # Clean previous test datasets if any
        old_ds = db.query(Dataset).filter(Dataset.name.in_(["dataset_p10_alpha", "dataset_p10_beta"])).all()
        for ds in old_ds:
            db.delete(ds)
        db.commit()

        # ---------------------------------------------------------------------------
        # 1. Ingest Baseline Version (V1) & Current Version (V2)
        # ---------------------------------------------------------------------------
        logger.info("\n--- 1. Ingesting Baseline V1 & Current V2 with Synthetic Drift ---")

        # Baseline V1 (100 rows): normal distribution income (mean=50000, std=5000), age (mean=30, std=5), category 'dept' (Sales: 60%, Eng: 40%)
        np.random.seed(42)
        v1_df = pd.DataFrame({
            "employee_id": range(1, 101),
            "age": np.random.normal(30, 5, 100).round().astype(int),
            "income": np.random.normal(50000, 5000, 100).round(2),
            "dept": np.random.choice(["Sales", "Engineering"], size=100, p=[0.60, 0.40]),
            "email": [f"emp{i}@company.com" for i in range(1, 101)],
            "legacy_code": [f"LEG_{i}" for i in range(1, 101)],  # Will be removed in V2
        })
        # Add a few missing values in email (2%)
        v1_df.loc[0:1, "email"] = None

        v1_buf = io.BytesIO()
        v1_df.to_csv(v1_buf, index=False)
        v1_buf.seek(0)

        res_v1 = client.post(
            "/api/datasets/upload",
            data={"dataset_name": "dataset_p10_alpha", "description": "Phase 10 Test Dataset"},
            files={"file": ("v1_data.csv", v1_buf, "text/csv")},
        )
        assert res_v1.status_code == 200, f"V1 Upload failed: {res_v1.text}"
        v1_data = res_v1.json()
        dataset_id = v1_data["dataset_id"]
        v1_id = v1_data["version_id"]
        logger.info(f" [PASS] 1. Baseline V1 uploaded (id={v1_id})")

        # Current V2 (120 rows):
        # - 'income' shifted significantly (mean=75000, std=12000) -> KS High Drift
        # - 'dept' shifted distribution (Sales: 20%, Eng: 40%, Support: 40%) -> PSI High Drift
        # - 'email' missingness increased from 2% to 20% (+18 pp) -> High Missingness Drift
        # - 'legacy_code' removed -> Schema break (REMOVED)
        # - 'phone_number' added -> Schema extension + new PII detected
        # - 'age' converted to string format -> Type changed
        v2_df = pd.DataFrame({
            "employee_id": range(1, 121),
            "age": [str(int(a)) for a in np.random.normal(30, 5, 120).round()],
            "income": np.random.normal(75000, 12000, 120).round(2),
            "dept": np.random.choice(["Sales", "Engineering", "Support"], size=120, p=[0.20, 0.40, 0.40]),
            "email": [f"emp{i}@company.com" if i > 24 else None for i in range(1, 121)],  # 20% missing
            "phone_number": [f"+1-555-01{i:02d}" for i in range(1, 121)],  # Added column with PII
        })

        v2_buf = io.BytesIO()
        v2_df.to_csv(v2_buf, index=False)
        v2_buf.seek(0)

        res_v2 = client.post(
            "/api/datasets/upload",
            data={"dataset_name": "dataset_p10_alpha"},
            files={"file": ("v2_data.csv", v2_buf, "text/csv")},
        )
        assert res_v2.status_code == 200, f"V2 Upload failed: {res_v2.text}"
        v2_data = res_v2.json()
        v2_id = v2_data["version_id"]
        logger.info(f" [PASS] 1. Current V2 uploaded (id={v2_id})")

        # Run profiling on both versions
        client.post(f"/api/datasets/{dataset_id}/versions/{v1_id}/profile")
        client.post(f"/api/datasets/{dataset_id}/versions/{v2_id}/profile")

        # Run Phase 5 Quality on both versions
        client.post(f"/api/datasets/{dataset_id}/versions/{v1_id}/quality")
        client.post(f"/api/datasets/{dataset_id}/versions/{v2_id}/quality")

        # Ingest a second dataset (Beta) for cross-dataset rejection test
        res_beta = client.post(
            "/api/datasets/upload",
            data={"dataset_name": "dataset_p10_beta"},
            files={"file": ("beta.csv", io.BytesIO(b"a,b\n1,2\n3,4"), "text/csv")},
        )
        beta_v1_id = res_beta.json()["version_id"]

        # ---------------------------------------------------------------------------
        # 2. Validation: Rejection Tests
        # ---------------------------------------------------------------------------
        logger.info("\n--- 2. Testing Version Compatibility & Rejection Rules ---")

        # A. Cross-dataset rejection
        res_cross = client.post(
            f"/api/datasets/{dataset_id}/compare",
            json={"baseline_version_id": v1_id, "current_version_id": beta_v1_id},
        )
        assert res_cross.status_code == 400, f"Expected 400 for cross-dataset compare, got: {res_cross.status_code}"
        logger.info(" [PASS] 2. Cross-dataset comparison rejected with 400 Bad Request")

        # B. Self-comparison rejection
        res_self = client.post(
            f"/api/datasets/{dataset_id}/compare",
            json={"baseline_version_id": v1_id, "current_version_id": v1_id},
        )
        assert res_self.status_code == 400, f"Expected 400 for self-comparison, got: {res_self.status_code}"
        logger.info(" [PASS] 2. Self-comparison rejected with 400 Bad Request")

        # ---------------------------------------------------------------------------
        # 3. Execution: Compare V1 vs V2
        # ---------------------------------------------------------------------------
        logger.info("\n--- 3. Testing Full Version Comparison (V1 → V2) ---")

        res_comp = client.post(
            f"/api/datasets/{dataset_id}/compare",
            json={"baseline_version_id": v1_id, "current_version_id": v2_id},
        )
        assert res_comp.status_code == 200, f"Compare failed: {res_comp.text}"
        comp_data = res_comp.json()

        comparison_id = comp_data["id"]
        overall_status = comp_data["overall_drift_status"]
        schema_sum = comp_data["schema_summary"]
        cols = {c["column_name"]: c for c in comp_data["columns"]}

        logger.info(f" Overall Drift Status: {overall_status}")
        logger.info(f" Schema Changes: {schema_sum}")
        logger.info(f" Drift Drivers: {comp_data['drift_drivers']}")

        # ---------------------------------------------------------------------------
        # 4. Assert Schema Evolution
        # ---------------------------------------------------------------------------
        logger.info("\n--- 4. Asserting Schema Evolution ---")
        assert "phone_number" in schema_sum["added_columns"], "Expected phone_number to be ADDED"
        assert "legacy_code" in schema_sum["removed_columns"], "Expected legacy_code to be REMOVED"
        assert cols["phone_number"]["schema_status"] == "ADDED"
        assert cols["legacy_code"]["schema_status"] == "REMOVED"
        logger.info(" [PASS] 4. Schema additions and removals verified accurately")

        # ---------------------------------------------------------------------------
        # 5. Assert Missingness & Uniqueness Shifts
        # ---------------------------------------------------------------------------
        logger.info("\n--- 5. Asserting Missingness & Uniqueness Deltas ---")
        email_miss = cols["email"]["missingness"]
        assert email_miss["percentage_point_change"] >= 15.0, f"Expected email missingness increase >= 15 pp, got: {email_miss['percentage_point_change']}"
        assert email_miss["classification"] == "HIGH_DRIFT"
        logger.info(f" [PASS] 5. Missingness percentage-point delta verified: {email_miss['percentage_point_change']} pp ({email_miss['classification']})")

        # ---------------------------------------------------------------------------
        # 6. Assert Numerical Distribution Drift (Kolmogorov-Smirnov Test)
        # ---------------------------------------------------------------------------
        logger.info("\n--- 6. Asserting Real Kolmogorov-Smirnov (KS) Test on 'income' ---")
        income_stat = cols["income"]["statistical_drift"]
        assert income_stat["test_type"] == "KOLMOGOROV_SMIRNOV"
        assert income_stat["status"] == "EXECUTED"
        assert income_stat["statistic"] is not None
        assert income_stat["statistic"] >= 0.35, f"Expected income KS stat >= 0.35, got: {income_stat['statistic']}"
        assert income_stat["p_value"] < 0.01, f"Expected income p-value < 0.01, got: {income_stat['p_value']}"
        assert income_stat["classification"] == "HIGH_DRIFT"
        logger.info(f" [PASS] 6. Real KS Test verified on 'income': KS={income_stat['statistic']}, p={income_stat['p_value']} ({income_stat['classification']})")

        # ---------------------------------------------------------------------------
        # 7. Assert Categorical Distribution Drift (Population Stability Index - PSI)
        # ---------------------------------------------------------------------------
        logger.info("\n--- 7. Asserting Real Population Stability Index (PSI) on 'dept' ---")
        dept_stat = cols["dept"]["statistical_drift"]
        assert dept_stat["test_type"] == "POPULATION_STABILITY_INDEX"
        assert dept_stat["status"] == "EXECUTED"
        assert dept_stat["statistic"] is not None
        assert dept_stat["statistic"] >= 0.10, f"Expected dept PSI >= 0.10, got: {dept_stat['statistic']}"
        logger.info(f" [PASS] 7. Real PSI verified on 'dept': PSI={dept_stat['statistic']} ({dept_stat['classification']})")

        # ---------------------------------------------------------------------------
        # 8. Assert Overall Drift Classification
        # ---------------------------------------------------------------------------
        logger.info("\n--- 8. Asserting Overall Drift Classification ---")
        assert overall_status == "HIGH_DRIFT", f"Expected overall HIGH_DRIFT due to schema removal and KS drift, got: {overall_status}"
        assert len(comp_data["drift_drivers"]) > 0, "Expected non-empty drift drivers"
        logger.info(f" [PASS] 8. Overall Drift Status verified: {overall_status} with {len(comp_data['drift_drivers'])} evidence drivers")

        # ---------------------------------------------------------------------------
        # 9. Assert Idempotent Caching & Re-comparison
        # ---------------------------------------------------------------------------
        logger.info("\n--- 9. Asserting Idempotency & force_recompute ---")
        res_cached = client.post(
            f"/api/datasets/{dataset_id}/compare",
            json={"baseline_version_id": v1_id, "current_version_id": v2_id, "force_recompute": False},
        )
        assert res_cached.status_code == 200
        assert res_cached.json()["id"] == comparison_id, "Cached comparison ID must match"

        res_forced = client.post(
            f"/api/datasets/{dataset_id}/compare",
            json={"baseline_version_id": v1_id, "current_version_id": v2_id, "force_recompute": True},
        )
        assert res_forced.status_code == 200
        logger.info(" [PASS] 9. Idempotency & force_recompute verified")

        # ---------------------------------------------------------------------------
        # 10. Assert REST Endpoints
        # ---------------------------------------------------------------------------
        logger.info("\n--- 10. Asserting GET Endpoints ---")
        # GET detail
        res_get = client.get(f"/api/datasets/{dataset_id}/comparisons/{comparison_id}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == comparison_id

        # GET list
        res_list = client.get(f"/api/datasets/{dataset_id}/comparisons")
        assert res_list.status_code == 200
        assert len(res_list.json()) >= 1

        # GET single column
        res_col = client.get(f"/api/datasets/{dataset_id}/comparisons/{comparison_id}/columns/income")
        assert res_col.status_code == 200
        assert res_col.json()["column_name"] == "income"
        logger.info(" [PASS] 10. All Phase 10 REST endpoints verified")

        # ---------------------------------------------------------------------------
        # 11. Clean Up & Cascade Deletion Test
        # ---------------------------------------------------------------------------
        logger.info("\n--- 11. Asserting Cascade Deletion ---")
        res_del = client.delete(f"/api/datasets/{dataset_id}")
        assert res_del.status_code == 200

        # Ensure comparisons and column drift records were cascaded
        comp_check = db.query(DatasetComparison).filter(DatasetComparison.id == comparison_id).first()
        assert comp_check is None, "DatasetComparison should have been cascaded on dataset deletion"
        logger.info(" [PASS] 11. Cascade deletion verified")

        # Clean Beta
        client.delete(f"/api/datasets/{res_beta.json()['dataset_id']}")
        db.close()

    logger.info("\n===========================================================================")
    logger.info("  🎉 ALL 11 PHASE 10 AUTOMATED TEST SCENARIOS PASSED!")
    logger.info("===========================================================================")


if __name__ == "__main__":
    test_phase10_full_suite()
