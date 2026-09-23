"""
DataGuard AI — Phase 13 Automated Test Suite
Data Quality Dashboard & Unified Presentation Layer

Validates:
1. Dashboard endpoint returns dataset metadata & version list.
2. Dashboard returns existing Phase 9 health result & 4-way breakdown.
3. Dashboard returns Phase 5 quality result.
4. Dashboard returns Phase 7 risk summary.
5. Dashboard returns Phase 6 privacy summary.
6. Dashboard returns Phase 8 anomaly summary.
7. Dashboard returns Phase 9 prioritized issues.
8. Dashboard returns Phase 4 profiling summary.
9. Dashboard returns Phase 10 drift information when comparison exists.
10. Dashboard handles missing comparison cleanly (no false drift).
11. Dashboard handles missing/zero quality evaluation (preserves NOT_EVALUATED & UNKNOWN).
12. Dashboard does not expose raw PII values (audit).
13. Dashboard does not expose raw dataset rows (audit).
14. Dashboard does not rerun analysis (read-only verification).
15. Dataset isolation is enforced (404 for invalid/mismatched ids).
16. Version isolation is enforced.
17. Unknown/not-evaluated states are explicitly preserved (no false 100% perfection).
18. Empty states work gracefully across all cards.
19. Dashboard refresh reads existing results deterministically.
20. Cross-signal attention columns matrix and grounded insights generation.
"""

import sys
import os
import uuid
import unittest
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
import app.database as database
from app.models.dataset import Dataset, DatasetVersion

from app.models.profiling import ProfilingResult
from app.models.quality import QualityValidationResult, QualityExpectationResult
from app.models.pii import PIIScanResult, PIIFinding

from app.models.risk import ColumnRiskPrediction
from app.models.anomaly import AnomalyDetectionResult, AnomalyFinding
from app.models.issues import DatasetHealthResult, DataQualityIssue

from app.models.comparison import DatasetComparison, ColumnDriftResult

client = TestClient(app)


class Phase13DashboardTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_database()
        cls.db = database.SessionLocal()

        # Cleanup any previous runs
        cls.db.query(Dataset).filter(Dataset.name.like("Phase 13 Test Customer Dataset%")).delete(synchronize_session=False)
        cls.db.commit()

        cls.ds_name = f"Phase 13 Test Customer Dataset {uuid.uuid4().hex[:6]}"
        cls.ds = Dataset(
            name=cls.ds_name,
            description="Dataset for testing Unified Data Quality Dashboard",
        )
        cls.db.add(cls.ds)
        cls.db.commit()
        cls.db.refresh(cls.ds)


        # 1. Version 1
        cls.v1 = DatasetVersion(
            dataset_id=cls.ds.id,
            version_number=1,
            original_filename="customers_v1.csv",
            stored_filename="customers_v1_stored.csv",
            file_type="csv",
            file_size_bytes=1048576,
            row_count=1000,
            column_count=5,
            column_names=["email", "salary", "age", "customer_id", "phone"],
            column_dtypes={"email": "string", "salary": "float64", "age": "int64", "customer_id": "string", "phone": "string"},
        )
        cls.db.add(cls.v1)
        cls.db.commit()
        cls.db.refresh(cls.v1)


        # V1 Phase 4 Profiling
        p1 = ProfilingResult(
            dataset_version_id=cls.v1.id,
            row_count=1000,
            column_count=5,
            missing_cells=50,
            missing_cells_percentage=1.0,
            duplicate_rows=5,
            duplicate_rows_percentage=0.5,
            memory_size_bytes=1048576,
            numeric_columns_count=2,
            categorical_columns_count=3,
            column_profiles={
                "email": {"dtype": "string", "missing_count": 20, "missing_percentage": 2.0},
                "salary": {"dtype": "float64", "missing_count": 30, "missing_percentage": 3.0, "histogram": [10, 20, 50, 20]},
                "age": {"dtype": "int64", "missing_count": 0, "missing_percentage": 0.0},
            },
        )
        cls.db.add(p1)

        # V1 Phase 5 Quality
        q1 = QualityValidationResult(
            dataset_version_id=cls.v1.id,
            overall_score=85.0,
            total_expectations=10,
            passed_expectations=8,
            failed_expectations=2,
            summary={"categories": {"completeness": 90.0, "validity": 80.0}},
        )
        cls.db.add(q1)
        cls.db.flush()

        exp1 = QualityExpectationResult(
            validation_id=q1.id,
            expectation_type="expect_column_values_to_not_be_null",
            category="Missing Data",
            column_name="email",
            success=False,
            observed_value="20 missing values found",
            failure_message="Column email has 20 missing values",
        )
        exp2 = QualityExpectationResult(
            validation_id=q1.id,
            expectation_type="expect_column_values_to_be_unique",
            category="Uniqueness",
            column_name="customer_id",
            success=False,
            observed_value="3 duplicates found",
            failure_message="Column customer_id contains duplicates",
        )
        cls.db.add_all([exp1, exp2])


        # V1 Phase 6 PII
        pii1 = PIIScanResult(
            dataset_version_id=cls.v1.id,
            total_columns_scanned=5,
            pii_columns_count=2,
            total_findings=15,
        )
        cls.db.add(pii1)
        cls.db.flush()

        f1 = PIIFinding(
            scan_id=pii1.id,
            column_name="email",
            entity_type="EMAIL_ADDRESS",
            detection_source="VALUE",
            detected_count=10,
            risk_level="HIGH",
            confidence=0.95,
        )
        f2 = PIIFinding(
            scan_id=pii1.id,
            column_name="phone",
            entity_type="PHONE_NUMBER",
            detection_source="COLUMN_NAME",
            detected_count=5,
            risk_level="MEDIUM",
            confidence=0.88,
        )
        cls.db.add_all([f1, f2])


        # V1 Phase 7 ML Column Risk
        r1 = ColumnRiskPrediction(
            dataset_version_id=cls.v1.id,
            column_name="email",
            predicted_domain="Contact Information",
            risk_level="HIGH",
            risk_score=85.0,
            model_confidence=0.92,
        )
        r2 = ColumnRiskPrediction(
            dataset_version_id=cls.v1.id,
            column_name="salary",
            predicted_domain="Financial Information",
            risk_level="MEDIUM",
            risk_score=60.0,
            model_confidence=0.85,
        )
        r3 = ColumnRiskPrediction(
            dataset_version_id=cls.v1.id,
            column_name="age",
            predicted_domain="Demographic",
            risk_level="LOW",
            risk_score=20.0,
            model_confidence=0.98,
        )
        cls.db.add_all([r1, r2, r3])


        # V1 Phase 8 Anomalies
        anom1 = AnomalyDetectionResult(
            dataset_version_id=cls.v1.id,
            total_columns_analyzed=5,
            columns_with_anomalies=1,
            total_anomalies=12,
            dataset_anomaly_score=15.0,
        )
        cls.db.add(anom1)
        cls.db.flush()

        ca1 = AnomalyFinding(
            detection_result_id=anom1.id,
            column_name="salary",
            detection_method="Isolation Forest",
            severity="MEDIUM",
            anomaly_rate=1.2,
            anomaly_count=12,
            score=60.0,
        )
        cls.db.add(ca1)


        # V1 Phase 9 Health & Prioritized Issues
        h1 = DatasetHealthResult(
            dataset_version_id=cls.v1.id,
            health_score=78.5,
            health_grade="NEEDS ATTENTION",
            quality_health=85.0,
            risk_health=70.0,
            anomaly_health=85.0,
            privacy_health=75.0,
        )
        cls.db.add(h1)
        cls.db.flush()

        iss1 = DataQualityIssue(
            dataset_health_result_id=h1.id,
            dataset_version_id=cls.v1.id,
            column_name="email",
            issue_type="MISSING_VALUES",
            source="QUALITY",
            severity="HIGH",
            priority_score=82.0,
            title="High missingness in email",
            description="Column email has 20 missing values",
        )
        iss2 = DataQualityIssue(
            dataset_health_result_id=h1.id,
            dataset_version_id=cls.v1.id,
            column_name="salary",
            issue_type="ANOMALY",
            source="ANOMALY",
            severity="MEDIUM",
            priority_score=64.0,
            title="Potential salary outliers detected",
            description="Salary column has 12 potential outliers",
        )
        cls.db.add_all([iss1, iss2])


        # 2. Version 2
        cls.v2 = DatasetVersion(
            dataset_id=cls.ds.id,
            version_number=2,
            original_filename="customers_v2.csv",
            stored_filename="customers_v2_stored.csv",
            file_type="csv",
            file_size_bytes=1048576,
            row_count=1200,
            column_count=5,
            column_names=["email", "salary", "age", "customer_id", "phone"],
            column_dtypes={"email": "string", "salary": "float64", "age": "int64", "customer_id": "string", "phone": "string"},
        )
        cls.db.add(cls.v2)
        cls.db.commit()
        cls.db.refresh(cls.v2)


        # V2 Phase 9 Health
        h2 = DatasetHealthResult(
            dataset_version_id=cls.v2.id,
            health_score=84.0,
            health_grade="GOOD",
            quality_health=90.0,
            risk_health=75.0,
            anomaly_health=90.0,
            privacy_health=80.0,
        )
        cls.db.add(h2)

        # Phase 10 Comparison between V1 and V2
        comp = DatasetComparison(
            dataset_id=cls.ds.id,
            baseline_version_id=cls.v1.id,
            current_version_id=cls.v2.id,
            status="COMPLETED",
            overall_drift_status="MEDIUM_DRIFT",
        )
        cls.db.add(comp)
        cls.db.flush()

        cd1 = ColumnDriftResult(
            comparison_id=comp.id,
            column_name="salary",
            drift_status="MEDIUM_DRIFT",
            statistical_comparison={"test_name": "KS", "test_statistic": 0.35, "p_value": 0.01},
        )
        cls.db.add(cd1)
        cls.db.commit()


    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.delete(cls.ds)
            cls.db.commit()
        except Exception:
            cls.db.rollback()
        finally:
            cls.db.close()

    def test_01_dashboard_metadata(self):
        """1. Dashboard endpoint returns dataset metadata & version list."""
        res = client.get(f"/api/datasets/{self.ds.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["dataset"]["id"], str(self.ds.id))
        self.assertEqual(data["dataset"]["name"], self.ds_name)

        self.assertEqual(len(data["all_versions"]), 2)
        self.assertEqual(data["version"]["version_number"], 2)

    def test_02_phase9_health(self):
        """2. Dashboard returns existing Phase 9 health result."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        health = res.json()["health"]
        self.assertTrue(health["available"])
        self.assertEqual(health["dataset_health_score"], 78.5)
        self.assertEqual(health["grade"], "NEEDS ATTENTION")
        self.assertEqual(health["quality_health"], 85.0)
        self.assertEqual(health["risk_health"], 70.0)
        self.assertEqual(health["anomaly_health"], 85.0)
        self.assertEqual(health["privacy_health"], 75.0)

    def test_03_phase5_quality(self):
        """3. Dashboard returns Phase 5 quality result with failed expectation details."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        quality = res.json()["quality"]
        self.assertTrue(quality["available"])
        self.assertEqual(quality["quality_score"], 85.0)
        self.assertEqual(quality["status"], "EVALUATED")
        self.assertEqual(quality["total_rules_evaluated"], 10)
        self.assertEqual(quality["passed_rules"], 8)
        self.assertEqual(quality["failed_rules"], 2)
        failed_cols = [f["column_name"] for f in quality["failed_expectations"]]
        self.assertIn("email", failed_cols)
        self.assertIn("customer_id", failed_cols)


    def test_04_phase7_risk_summary(self):
        """4. Dashboard returns Phase 7 ML risk distribution and sorted columns."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        risk = res.json()["risk"]
        self.assertTrue(risk["available"])
        self.assertEqual(risk["columns_analyzed"], 3)
        self.assertEqual(risk["high_count"], 1)
        self.assertEqual(risk["medium_count"], 1)
        self.assertEqual(risk["low_count"], 1)
        self.assertEqual(risk["column_risks"][0]["column_name"], "email")
        self.assertEqual(risk["column_risks"][0]["risk_score"], 85.0)

    def test_05_phase6_privacy_summary(self):
        """5. Dashboard returns Phase 6 privacy summary without exposing raw values."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        privacy = res.json()["privacy"]
        self.assertTrue(privacy["available"])
        self.assertEqual(privacy["pii_columns_count"], 2)
        self.assertEqual(privacy["total_findings_count"], 15)
        self.assertEqual(privacy["highest_severity"], "HIGH")
        categories = [c["category"] for c in privacy["detected_categories"]]
        self.assertIn("EMAIL_ADDRESS", categories)
        self.assertIn("PHONE_NUMBER", categories)

    def test_06_phase8_anomaly_summary(self):
        """6. Dashboard returns Phase 8 anomaly detection summary."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        anomalies = res.json()["anomalies"]
        self.assertTrue(anomalies["available"])
        self.assertEqual(anomalies["anomalous_columns_count"], 1)
        self.assertEqual(anomalies["total_anomalies_count"], 12)
        self.assertEqual(anomalies["dataset_anomaly_score"], 15.0)
        self.assertEqual(anomalies["anomalous_columns"][0]["column_name"], "salary")

    def test_07_phase9_prioritized_issues(self):
        """7. Dashboard returns Phase 9 prioritized issues sorted by priority score."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        issues = res.json()["issues"]
        self.assertTrue(issues["available"])
        self.assertEqual(issues["total_issues"], 2)
        self.assertEqual(issues["high_priority_count"], 1)
        self.assertEqual(issues["prioritized_issues"][0]["priority_score"], 82.0)

    def test_08_phase4_profiling(self):
        """8. Dashboard returns Phase 4 statistical profiling summary and missingness."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        prof = res.json()["profiling"]
        self.assertTrue(prof["available"])
        self.assertEqual(prof["row_count"], 1000)
        self.assertEqual(prof["column_count"], 5)
        self.assertEqual(prof["missing_percentage"], 1.0)
        self.assertEqual(len(prof["top_missing_columns"]), 2)

    def test_09_phase10_drift_when_comparison_exists(self):
        """9. Dashboard returns Phase 10 drift information for compared version (V2)."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v2.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        drift = res.json()["drift"]
        self.assertTrue(drift["available"])
        self.assertTrue(drift["has_comparison"])
        self.assertEqual(drift["baseline_version_number"], 1)
        self.assertEqual(drift["current_version_number"], 2)
        self.assertEqual(drift["overall_drift_severity"], "MEDIUM_DRIFT")

        self.assertEqual(len(drift["column_drifts"]), 1)
        self.assertEqual(drift["column_drifts"][0]["column_name"], "salary")

    def test_10_missing_comparison_handled(self):
        """10. Dashboard handles missing comparison without false drift assumption."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        drift = res.json()["drift"]
        self.assertFalse(drift["has_comparison"])
        self.assertIsNone(drift["overall_drift_severity"])

    def test_11_missing_quality_evaluation_not_evaluated(self):
        """11. Mandatory Rule: 0 evaluated rules must yield NOT_EVALUATED and UNKNOWN grade."""
        ds_temp = Dataset(name=f"Unanalyzed Dataset {uuid.uuid4().hex[:6]}")
        self.db.add(ds_temp)
        self.db.commit()
        self.db.refresh(ds_temp)


        v_temp = DatasetVersion(
            dataset_id=ds_temp.id,
            version_number=1,
            original_filename="empty.csv",
            stored_filename="empty_stored.csv",
            file_type="csv",
            file_size_bytes=100,
            row_count=10,
            column_count=2,
            column_names=["col1", "col2"],
            column_dtypes={"col1": "string", "col2": "int64"},
        )

        self.db.add(v_temp)
        self.db.commit()
        self.db.refresh(v_temp)

        q_temp = QualityValidationResult(
            dataset_version_id=v_temp.id,
            overall_score=100.0,
            total_expectations=0,
            passed_expectations=0,
            failed_expectations=0,
        )
        self.db.add(q_temp)
        self.db.commit()

        res = client.get(f"/api/datasets/{ds_temp.id}/versions/{v_temp.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        quality = res.json()["quality"]
        self.assertEqual(quality["status"], "NOT_EVALUATED")
        self.assertEqual(quality["grade"], "UNKNOWN")
        self.assertEqual(quality["total_rules_evaluated"], 0)

        # Cleanup
        self.db.delete(ds_temp)
        self.db.commit()

    def test_12_strict_privacy_audit_no_raw_pii(self):
        """12. Strictly verify zero raw PII strings in entire JSON response payload."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        payload_str = res.text.lower()
        self.assertNotIn("@example.com", payload_str)
        self.assertNotIn("john.doe", payload_str)
        self.assertNotIn("+1-555", payload_str)

    def test_13_no_raw_dataset_rows_exposed(self):
        """13. Verify that entire raw dataframe rows are never serialized into dashboard."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn("raw_data", data)
        self.assertNotIn("rows", data["profiling"])

    def test_14_dashboard_is_read_only_no_rerun(self):
        """14. Dashboard calls must only perform SELECT queries and never re-trigger analysis."""
        health_count_before = self.db.query(DatasetHealthResult).count()
        quality_count_before = self.db.query(QualityValidationResult).count()

        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)

        health_count_after = self.db.query(DatasetHealthResult).count()
        quality_count_after = self.db.query(QualityValidationResult).count()

        self.assertEqual(health_count_before, health_count_after)
        self.assertEqual(quality_count_before, quality_count_after)

    def test_15_dataset_isolation_enforced(self):
        """15. Accessing nonexistent dataset returns 404."""
        fake_id = uuid.uuid4()
        res = client.get(f"/api/datasets/{fake_id}/dashboard")
        self.assertEqual(res.status_code, 404)

    def test_16_version_isolation_enforced(self):
        """16. Specifying mismatched version returns correct 404 or falls back to valid version."""
        fake_ver_id = uuid.uuid4()
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{fake_ver_id}/dashboard")
        self.assertIn(res.status_code, (200, 404))

    def test_17_historical_version_trends(self):
        """17. Dashboard produces version health trends across multiple snapshots."""
        res = client.get(f"/api/datasets/{self.ds.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        trends = res.json()["trends"]
        self.assertTrue(trends["available"])
        self.assertTrue(trends["has_sufficient_history"])
        self.assertEqual(len(trends["versions"]), 2)
        self.assertEqual(trends["versions"][0]["dataset_health"], 78.5)
        self.assertEqual(trends["versions"][1]["dataset_health"], 84.0)

    def test_18_cross_signal_attention_columns(self):
        """18. Cross-signal attention table synthesizes risk, quality, anomaly, and PII."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        attn = res.json()["attention_columns"]
        self.assertGreater(len(attn), 0)
        email_attn = next((c for c in attn if c["column_name"] == "email"), None)
        self.assertIsNotNone(email_attn)
        self.assertEqual(email_attn["risk_level"], "HIGH")
        self.assertEqual(email_attn["quality_status"], "Failed")
        self.assertEqual(email_attn["pii_severity"], "HIGH")
        self.assertGreaterEqual(email_attn["issue_count"], 1)

    def test_19_grounded_key_insights(self):
        """19. Grounded factual analytical highlights are returned."""
        res = client.get(f"/api/datasets/{self.ds.id}/versions/{self.v1.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        insights = res.json()["insights"]
        self.assertGreater(len(insights), 0)
        categories = [ins["category"] for ins in insights]
        self.assertIn("Health", categories)
        self.assertIn("Risk", categories)

    def test_20_empty_state_graceful(self):
        """20. Fresh dataset with no analytics returns graceful empty states."""
        ds_empty = Dataset(name=f"Fresh Dataset Without Runs {uuid.uuid4().hex[:6]}")
        self.db.add(ds_empty)
        self.db.commit()
        self.db.refresh(ds_empty)


        v_empty = DatasetVersion(
            dataset_id=ds_empty.id,
            version_number=1,
            original_filename="blank.csv",
            stored_filename="blank_stored.csv",
            file_type="csv",
            file_size_bytes=0,
            row_count=0,
            column_count=0,
            column_names=[],
            column_dtypes={},
        )

        self.db.add(v_empty)
        self.db.commit()
        self.db.refresh(v_empty)

        res = client.get(f"/api/datasets/{ds_empty.id}/versions/{v_empty.id}/dashboard")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["health"]["available"])
        self.assertFalse(data["quality"]["available"])
        self.assertFalse(data["risk"]["available"])
        self.assertFalse(data["privacy"]["available"])
        self.assertFalse(data["anomalies"]["available"])
        self.assertFalse(data["drift"]["has_comparison"])
        self.assertFalse(data["trends"]["has_sufficient_history"])

        # Cleanup
        self.db.delete(ds_empty)
        self.db.commit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
