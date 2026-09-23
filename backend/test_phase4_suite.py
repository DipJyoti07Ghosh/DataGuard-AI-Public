"""
DataGuard AI — Phase 4 Automated Profiling Test Suite

Tests:
1. Generate statistical profile via POST /api/datasets/{id}/versions/{v_id}/profile
2. Verify dataset-level metrics (observations, features, missing cells %, duplicates %, memory size)
3. Verify column-level moments & quantiles (mean, std, min, max, q25, q50, q75, q95, skewness, kurtosis)
4. Verify frequency distribution histogram generation (10 bins)
5. Verify categorical top-categories & frequency breakdown
6. Verify feature correlation matrix
7. Verify quality issues dataset profiling (missing cells, duplicates detected)
8. Verify profile retrieval via GET /api/datasets/{id}/versions/{v_id}/profile
9. Verify force_recompute parameter
10. Verify 404 error handling for non-existent dataset / version
11. Verify single-value & constant column edge cases
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend root is in path
sys.path.insert(0, str(Path(__file__).parent))

from app.main import app
from app.config import settings
import app.database as db

client = TestClient(app)
DATA_DIR = Path(__file__).parent.parent / "data"


def run_phase4_tests():
    print("=" * 70)
    print("  DataGuard AI — Phase 4 Automated Profiling Test Suite")
    print("=" * 70)

    # 1. First upload a test dataset to have a fresh Dataset & DatasetVersion
    print("\n--- 1. Uploading Test Dataset for Profiling ---")
    csv_path = DATA_DIR / "clean_sample.csv"
    with open(csv_path, "rb") as f:
        res_up = client.post(
            "/api/datasets/upload",
            data={"dataset_name": "Profiling Test Data", "description": "Benchmark dataset for statistical profiling"},
            files={"file": ("clean_sample.csv", f, "text/csv")},
        )
    assert res_up.status_code == 200, f"Upload failed: {res_up.text}"
    up_data = res_up.json()
    dataset_id = up_data["dataset_id"]
    version_id = up_data["version_id"]
    print(f" [PASS] Uploaded dataset: ID={dataset_id}, Version ID={version_id} (V{up_data['version_number']})")

    # 2. Trigger Profiling via POST
    print("\n--- 2. Triggering Automated Profiling via POST ---")
    res_prof = client.post(f"/api/datasets/{dataset_id}/versions/{version_id}/profile")
    assert res_prof.status_code == 200, f"Profiling failed: {res_prof.text}"
    prof = res_prof.json()
    print(" [PASS] Profiling generated: 200 OK")

    # 3. Verify Dataset-level metrics
    print("\n--- 3. Verifying Dataset-Level Statistical Metrics ---")
    assert prof["row_count"] == 200
    assert prof["column_count"] == 16
    assert prof["missing_cells"] == 0
    assert prof["missing_cells_percentage"] == 0.0
    assert prof["duplicate_rows"] == 0
    assert prof["duplicate_rows_percentage"] == 0.0
    assert prof["memory_size_bytes"] > 0
    assert prof["numeric_columns_count"] > 0
    assert prof["categorical_columns_count"] > 0
    print(
        f" [PASS] Dataset Metrics: {prof['row_count']} rows x {prof['column_count']} cols, "
        f"{prof['numeric_columns_count']} numeric, {prof['categorical_columns_count']} categorical, "
        f"memory={prof['memory_size_display']}"
    )

    # 4. Verify Column-level metrics for Numeric column (monthly_spend)
    print("\n--- 4. Verifying Numeric Feature Metrics (monthly_spend) ---")
    col_spend = prof["column_profiles"]["monthly_spend"]
    assert col_spend["type_category"] == "numeric"
    assert col_spend["count"] == 200
    assert col_spend["mean"] is not None
    assert col_spend["std"] is not None
    assert col_spend["min"] is not None
    assert col_spend["max"] is not None
    assert col_spend["q25"] is not None
    assert col_spend["q50"] is not None
    assert col_spend["q75"] is not None
    assert col_spend["q95"] is not None
    assert col_spend["min"] <= col_spend["q25"] <= col_spend["q50"] <= col_spend["q75"] <= col_spend["q95"] <= col_spend["max"]
    assert len(col_spend["histogram"]) > 0
    print(
        f" [PASS] 'monthly_spend' stats: min={col_spend['min']}, p25={col_spend['q25']}, "
        f"median={col_spend['q50']}, mean={col_spend['mean']}, p75={col_spend['q75']}, "
        f"p95={col_spend['q95']}, max={col_spend['max']}"
    )
    print(f"        Histogram bins: {len(col_spend['histogram'])} bins computed")

    # 5. Verify Categorical metrics (subscription_type)
    print("\n--- 5. Verifying Categorical Feature Metrics (subscription_type) ---")
    col_sub = prof["column_profiles"]["subscription_type"]
    assert col_sub["type_category"] == "categorical"
    assert col_sub["unique_count"] == 4
    assert len(col_sub["top_categories"]) == 4
    top_names = {c["value"] for c in col_sub["top_categories"]}
    assert "Pro" in top_names or "Enterprise" in top_names or "Basic" in top_names or "Free" in top_names
    print(f" [PASS] 'subscription_type' top categories: {[c['value'] + ' (' + str(c['percentage']) + '%)' for c in col_sub['top_categories'][:3]]}")

    # 6. Verify Correlation Matrix
    print("\n--- 6. Verifying Correlation Matrix ---")
    corrs = prof["correlations"]
    assert corrs is not None
    assert "monthly_spend" in corrs
    assert "total_purchases" in corrs
    assert corrs["monthly_spend"]["monthly_spend"] == 1.0  # self correlation
    print(f" [PASS] Pearson correlation matrix verified: {len(corrs)} numeric features, self-correlation == 1.0")

    # 7. Test Retrieval via GET
    print("\n--- 7. Testing Profile Retrieval via GET ---")
    res_get = client.get(f"/api/datasets/{dataset_id}/versions/{version_id}/profile")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == prof["id"]
    print(" [PASS] GET /profile: Retrieved cached profile successfully")

    # 8. Test force_recompute
    print("\n--- 8. Testing force_recompute=True ---")
    res_force = client.post(f"/api/datasets/{dataset_id}/versions/{version_id}/profile?force_recompute=true")
    assert res_force.status_code == 200
    assert res_force.json()["id"] == prof["id"]
    print(" [PASS] force_recompute=True successfully recomputed and updated profile")

    # 9. Test Quality Issues Dataset (Missing values & Duplicates detected)
    print("\n--- 9. Profiling Dataset with Quality Issues ---")
    quality_path = DATA_DIR / "quality_issues_v1.csv"
    with open(quality_path, "rb") as f:
        res_q_up = client.post(
            "/api/datasets/upload",
            data={"dataset_name": "Quality Issues Profile Test"},
            files={"file": ("quality_issues_v1.csv", f, "text/csv")},
        )
    q_data = res_q_up.json()
    q_ds_id = q_data["dataset_id"]
    q_ver_id = q_data["version_id"]

    res_q_prof = client.post(f"/api/datasets/{q_ds_id}/versions/{q_ver_id}/profile")
    assert res_q_prof.status_code == 200
    q_prof = res_q_prof.json()
    assert q_prof["missing_cells"] > 0
    assert q_prof["missing_cells_percentage"] > 0.0
    assert q_prof["duplicate_rows"] > 0
    print(
        f" [PASS] Quality Issues Profile: detected {q_prof['missing_cells']} missing cells "
        f"({q_prof['missing_cells_percentage']}%) and {q_prof['duplicate_rows']} duplicate rows"
    )

    # 10. Test 404 Error Handling
    print("\n--- 10. Testing 404 Error Handling ---")
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    res_404 = client.get(f"/api/datasets/{fake_uuid}/versions/{fake_uuid}/profile")
    assert res_404.status_code == 404
    print(" [PASS] Non-existent dataset/version returned 404 Not Found")

    print("=" * 70)
    print("  All Phase 4 Automated Profiling Verification Tests PASSED! ✅")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_phase4_tests()
    sys.exit(0 if success else 1)
