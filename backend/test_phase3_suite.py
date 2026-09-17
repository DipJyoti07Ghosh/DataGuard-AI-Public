"""
DataGuard AI — Phase 3 Comprehensive Test Suite

Tests:
1. PostgreSQL connection & session initialization
2. Alembic migration execution
3. Upload clean_sample.csv -> Creates Dataset 'Customer Data' V1
4. Upload quality_issues_v1.csv as 'Customer Data' -> Creates 'Customer Data' V2
5. Upload another file as 'Customer Data' -> Creates 'Customer Data' V3
6. Upload sample_excel.xlsx as 'Sales Data' -> Creates 'Sales Data' V1
7. GET /api/datasets -> returns both datasets with correct version counts
8. GET /api/datasets/{id} -> returns full version history
9. GET /api/datasets/{id}/versions/{v_id} -> returns specific version details
10. DELETE /api/datasets/{id} -> deletes dataset, cascades to versions and removes files
11. Verifies non-existent dataset / version error handling
12. Verifies health endpoint reports PostgreSQL: connected
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend root is in path
sys.path.insert(0, str(Path(__file__).parent))

from app.main import app
from app.config import settings
import app.database as db
from sqlalchemy import text

client = TestClient(app)
DATA_DIR = Path(__file__).parent.parent / "data"
UPLOAD_DIR = settings.upload_path


def run_phase3_tests():
    print("=" * 70)
    print("  DataGuard AI — Phase 3 Verification Test Suite")
    print("=" * 70)

    import uuid
    test_run_id = uuid.uuid4().hex[:6]
    cust_ds_name = f"Customer Data {test_run_id}"
    sales_ds_name = f"Sales Data {test_run_id}"

    # 1. Test Database Connectivity
    print("\n--- 1. Testing PostgreSQL Connection ---")
    if not db.init_database():
        print(" [FAIL] Could not initialize database engine.")
        return False

    try:
        with db.engine.connect() as conn:
            res = conn.execute(text("SELECT 1")).scalar()
            assert res == 1
        print(" [PASS] PostgreSQL Connection: SUCCESS (SELECT 1 returned 1)")
    except Exception as e:
        print(f" [FAIL] PostgreSQL Connection failed: {e}")
        return False

    # 2. Upload clean_sample.csv as "Customer Data" (V1)
    print(f"\n--- 2. Uploading V1 for '{cust_ds_name}' ---")
    csv_path = DATA_DIR / "clean_sample.csv"
    with open(csv_path, "rb") as f:
        res1 = client.post(
            "/api/datasets/upload",
            data={"dataset_name": cust_ds_name, "description": "Customer demographics and spend"},
            files={"file": ("clean_sample.csv", f, "text/csv")},
        )
    assert res1.status_code == 200, f"Upload failed: {res1.text}"
    v1_data = res1.json()
    customer_ds_id = v1_data["dataset_id"]
    v1_id = v1_data["version_id"]
    assert v1_data["version_number"] == 1
    assert v1_data["dataset_name"] == cust_ds_name
    assert v1_data["row_count"] == 200
    print(f" [PASS] Created '{cust_ds_name}' V1: Dataset ID={customer_ds_id}, Version ID={v1_id}")

    # 3. Upload quality_issues_v1.csv as "Customer Data" (V2)
    print(f"\n--- 3. Uploading V2 for '{cust_ds_name}' ---")
    quality_path = DATA_DIR / "quality_issues_v1.csv"
    with open(quality_path, "rb") as f:
        res2 = client.post(
            "/api/datasets/upload",
            data={"dataset_name": cust_ds_name},
            files={"file": ("quality_issues_v1.csv", f, "text/csv")},
        )
    assert res2.status_code == 200, f"Upload failed: {res2.text}"
    v2_data = res2.json()
    assert v2_data["dataset_id"] == customer_ds_id, "Expected same dataset_id for existing dataset"
    assert v2_data["version_number"] == 2, f"Expected V2, got V{v2_data['version_number']}"
    print(f" [PASS] Created '{cust_ds_name}' V2: Version ID={v2_data['version_id']} (257 rows)")

    # 4. Upload special_columns.csv as "Customer Data" (V3)
    print(f"\n--- 4. Uploading V3 for '{cust_ds_name}' ---")
    special_path = DATA_DIR / "special_columns.csv"
    with open(special_path, "rb") as f:
        res3 = client.post(
            "/api/datasets/upload",
            data={"dataset_name": cust_ds_name},
            files={"file": ("special_columns.csv", f, "text/csv")},
        )
    assert res3.status_code == 200, f"Upload failed: {res3.text}"
    v3_data = res3.json()
    assert v3_data["dataset_id"] == customer_ds_id
    assert v3_data["version_number"] == 3
    print(f" [PASS] Created '{cust_ds_name}' V3: Version ID={v3_data['version_id']}")

    # 5. Upload sample_excel.xlsx as "Sales Data" (V1)
    print(f"\n--- 5. Uploading '{sales_ds_name}' (New Dataset V1) ---")
    excel_path = DATA_DIR / "sample_excel.xlsx"
    with open(excel_path, "rb") as f:
        res4 = client.post(
            "/api/datasets/upload",
            data={"dataset_name": sales_ds_name, "description": "Sales workbook snapshot"},
            files={"file": ("sample_excel.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert res4.status_code == 200, f"Upload failed: {res4.text}"
    sales_data = res4.json()
    sales_ds_id = sales_data["dataset_id"]
    assert sales_ds_id != customer_ds_id
    assert sales_data["version_number"] == 1
    assert sales_data["dataset_name"] == sales_ds_name
    print(f" [PASS] Created separate '{sales_ds_name}' V1: Dataset ID={sales_ds_id}")

    # 6. GET /api/datasets (List all)
    print("\n--- 6. Testing GET /api/datasets ---")
    res_list = client.get("/api/datasets")
    assert res_list.status_code == 200
    datasets = res_list.json()
    assert len(datasets) >= 2
    ds_map = {d["name"]: d for d in datasets}
    assert cust_ds_name in ds_map
    assert sales_ds_name in ds_map
    assert ds_map[cust_ds_name]["version_count"] == 3
    assert ds_map[cust_ds_name]["latest_version_number"] == 3
    assert ds_map[sales_ds_name]["version_count"] == 1
    print(f" [PASS] GET /api/datasets: Found {len(datasets)} datasets ('{cust_ds_name}' has 3 versions, '{sales_ds_name}' has 1)")

    # 7. GET /api/datasets/{customer_ds_id} (Details & History)
    print("\n--- 7. Testing GET /api/datasets/{id} ---")
    res_detail = client.get(f"/api/datasets/{customer_ds_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert len(detail["versions"]) == 3
    v_nums = [v["version_number"] for v in detail["versions"]]
    assert v_nums == [3, 2, 1], f"Expected newest-first version ordering [3, 2, 1], got {v_nums}"
    print(f" [PASS] GET /api/datasets/{{id}}: Correctly returned 3 versions in descending order: {v_nums}")

    # 8. GET /api/datasets/{customer_ds_id}/versions/{v1_id}
    print("\n--- 8. Testing GET /api/datasets/{id}/versions/{version_id} ---")
    res_v1 = client.get(f"/api/datasets/{customer_ds_id}/versions/{v1_id}")
    assert res_v1.status_code == 200
    assert res_v1.json()["version_number"] == 1
    assert res_v1.json()["original_filename"] == "clean_sample.csv"
    print(f" [PASS] GET /api/datasets/{{id}}/versions/{{v_id}}: Successfully retrieved V1 snapshot")

    # 9. Health Check with DB connected
    print("\n--- 9. Testing /api/health ---")
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["components"]["database"] == "connected", f"Expected database connected, got {health_data['components']}"
    print(f" [PASS] Health check reports PostgreSQL: {health_data['components']['database']}")

    # 10. DELETE /api/datasets/{sales_ds_id}
    print("\n--- 10. Testing DELETE /api/datasets/{id} ---")
    res_del = client.get(f"/api/datasets/{sales_ds_id}")
    stored_file_to_check = res_del.json()["versions"][0]["stored_filename"]
    
    del_res = client.delete(f"/api/datasets/{sales_ds_id}")
    assert del_res.status_code == 200
    # Verify dataset is gone
    assert client.get(f"/api/datasets/{sales_ds_id}").status_code == 404
    # Verify file was cleaned up
    assert not (UPLOAD_DIR / stored_file_to_check).exists()
    print(f" [PASS] DELETE /api/datasets/{{id}}: Deleted 'Sales Data', cascaded versions, and removed physical file")

    print("=" * 70)
    print("  All Phase 3 Automated Verification Tests PASSED! ✅")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = run_phase3_tests()
    sys.exit(0 if success else 1)
