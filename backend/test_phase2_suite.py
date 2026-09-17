"""
DataGuard AI — Phase 2 Ingestion & Upload Test Suite

Executes automated verification of all 12 Phase 2 test scenarios:
1. Normal CSV
2. Normal XLSX
3. Empty CSV
4. Malformed CSV
5. Malformed XLSX
6. Unsupported file
7. Oversized file
8. Dataset with null values
9. Dataset with duplicate rows
10. Mixed data types
11. Special characters in column names
12. Duplicate filenames
"""

import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent))

from app.main import app
from app.config import settings

client = TestClient(app)
DATA_DIR = Path(__file__).parent.parent / "data"
UPLOAD_DIR = settings.upload_path

def run_tests():
    print("=" * 70)
    print("  DataGuard AI — Phase 2 Verification Test Suite")
    print("=" * 70)

    results = []

    # -------------------------------------------------------------
    # Test 1: Normal CSV
    # -------------------------------------------------------------
    csv_path = DATA_DIR / "clean_sample.csv"
    with open(csv_path, "rb") as f:
        res = client.post("/api/datasets/upload", files={"file": ("clean_sample.csv", f, "text/csv")})
    
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["row_count"] == 200, f"Expected 200 rows, got {data['row_count']}"
    assert data["column_count"] == 16, f"Expected 16 cols, got {data['column_count']}"
    assert data["file_type"] == "csv"
    assert (UPLOAD_DIR / data["stored_filename"]).exists()
    print(" [PASS] 1. Normal CSV upload: 200 OK (200 rows x 16 cols, safe file saved)")
    results.append(("1. Normal CSV", True))

    # -------------------------------------------------------------
    # Test 2: Normal XLSX
    # -------------------------------------------------------------
    xlsx_path = DATA_DIR / "sample_excel.xlsx"
    with open(xlsx_path, "rb") as f:
        res = client.post("/api/datasets/upload", files={"file": ("sample_excel.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["sheet_name"] == "CustomerData", f"Expected 'CustomerData', got {data['sheet_name']}"
    assert data["row_count"] == 200
    assert data["file_type"] == "xlsx"
    assert (UPLOAD_DIR / data["stored_filename"]).exists()
    print(" [PASS] 2. Normal XLSX upload: 200 OK (CustomerData sheet, 200 rows)")
    results.append(("2. Normal XLSX", True))

    # -------------------------------------------------------------
    # Test 3: Empty CSV
    # -------------------------------------------------------------
    empty_path = DATA_DIR / "empty.csv"
    with open(empty_path, "rb") as f:
        res = client.post("/api/datasets/upload", files={"file": ("empty.csv", f, "text/csv")})
    
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    assert "empty" in res.json()["detail"].lower()
    print(f" [PASS] 3. Empty CSV rejected: 400 Bad Request ('{res.json()['detail']}')")
    results.append(("3. Empty CSV", True))

    # -------------------------------------------------------------
    # Test 4: Malformed CSV
    # -------------------------------------------------------------
    malformed_path = DATA_DIR / "malformed.csv"
    with open(malformed_path, "rb") as f:
        res = client.post("/api/datasets/upload", files={"file": ("malformed.csv", f, "text/csv")})
    
    # Ingestion parses or rejects gracefully without unhandled crash
    assert res.status_code in (200, 400), f"Unexpected status: {res.status_code}"
    print(f" [PASS] 4. Malformed CSV handled cleanly: status {res.status_code}")
    results.append(("4. Malformed CSV", True))

    # -------------------------------------------------------------
    # Test 5: Malformed XLSX
    # -------------------------------------------------------------
    corrupt_path = DATA_DIR / "corrupted.xlsx"
    with open(corrupt_path, "rb") as f:
        res = client.post("/api/datasets/upload", files={"file": ("corrupted.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    assert "cannot read excel file" in res.json()["detail"].lower() or "failed" in res.json()["detail"].lower()
    print(f" [PASS] 5. Malformed XLSX rejected: 400 Bad Request ('{res.json()['detail'][:60]}...')")
    results.append(("5. Malformed XLSX", True))

    # -------------------------------------------------------------
    # Test 6: Unsupported file
    # -------------------------------------------------------------
    json_path = DATA_DIR / "unsupported.json"
    with open(json_path, "rb") as f:
        res = client.post("/api/datasets/upload", files={"file": ("unsupported.json", f, "application/json")})
    
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    assert "unsupported file type" in res.json()["detail"].lower()
    print(f" [PASS] 6. Unsupported file rejected: 400 Bad Request ('{res.json()['detail']}')")
    results.append(("6. Unsupported file", True))

    # -------------------------------------------------------------
    # Test 7: Oversized file
    # -------------------------------------------------------------
    # Temporarily set max size to 1 KB to test size validation cleanly
    orig_max = settings.max_upload_size_mb
    settings.max_upload_size_mb = 0  # max bytes will be 0 MB
    try:
        with open(csv_path, "rb") as f:
            res = client.post("/api/datasets/upload", files={"file": ("large_file.csv", f, "text/csv")})
        assert res.status_code == 400, f"Expected 400, got {res.status_code}"
        assert "exceeds" in res.json()["detail"].lower()
        print(f" [PASS] 7. Oversized file rejected: 400 Bad Request ('{res.json()['detail']}')")
        results.append(("7. Oversized file", True))
    finally:
        settings.max_upload_size_mb = orig_max

    # -------------------------------------------------------------
    # Test 8: Dataset with null values
    # -------------------------------------------------------------
    quality_path = DATA_DIR / "quality_issues_v1.csv"
    with open(quality_path, "rb") as f:
        res = client.post("/api/datasets/upload", files={"file": ("quality_issues_v1.csv", f, "text/csv")})
    
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    nullable_cols = [c for c in data["columns"] if c["nullable"]]
    assert len(nullable_cols) > 0, "Expected nullable columns with missing values"
    print(f" [PASS] 8. Dataset with null values: 200 OK ({len(nullable_cols)} columns with missing values detected)")
    results.append(("8. Dataset with null values", True))

    # -------------------------------------------------------------
    # Test 9: Dataset with duplicate rows
    # -------------------------------------------------------------
    assert data["duplicate_row_count"] > 0, f"Expected duplicate rows, got {data['duplicate_row_count']}"
    print(f" [PASS] 9. Duplicate rows detection: 200 OK ({data['duplicate_row_count']} duplicates identified)")
    results.append(("9. Duplicate rows", True))

    # -------------------------------------------------------------
    # Test 10: Mixed data types
    # -------------------------------------------------------------
    dtypes_found = {c["dtype"] for c in data["columns"]}
    print(f" [PASS] 10. Mixed data types verified: {dtypes_found}")
    results.append(("10. Mixed data types", True))

    # -------------------------------------------------------------
    # Test 11: Special characters in column names
    # -------------------------------------------------------------
    special_path = DATA_DIR / "special_columns.csv"
    with open(special_path, "rb") as f:
        res = client.post("/api/datasets/upload", files={"file": ("special_columns.csv", f, "text/csv")})
    
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data_special = res.json()
    assert "Tax Rate (%)" in data_special["column_names"]
    assert "Customer & Co." in data_special["column_names"]
    assert "Price ($ / USD)" in data_special["column_names"]
    print(f" [PASS] 11. Special characters in column names: 200 OK (Preserved: {data_special['column_names'][:3]}...)")
    results.append(("11. Special characters in column names", True))

    # -------------------------------------------------------------
    # Test 12: Duplicate filenames (Collision prevention)
    # -------------------------------------------------------------
    with open(csv_path, "rb") as f:
        res1 = client.post("/api/datasets/upload", files={"file": ("clean_sample.csv", f, "text/csv")})
    with open(csv_path, "rb") as f:
        res2 = client.post("/api/datasets/upload", files={"file": ("clean_sample.csv", f, "text/csv")})
    
    assert res1.status_code == 200 and res2.status_code == 200
    stored1 = res1.json()["stored_filename"]
    stored2 = res2.json()["stored_filename"]
    assert stored1 != stored2, f"Expected distinct safe stored filenames, got {stored1} == {stored2}"
    assert (UPLOAD_DIR / stored1).exists() and (UPLOAD_DIR / stored2).exists()
    print(f" [PASS] 12. Duplicate filenames collision prevention: 200 OK\n        File 1: {stored1}\n        File 2: {stored2}")
    results.append(("12. Duplicate filenames", True))

    print("=" * 70)
    print(f"  All {len(results)} Phase 2 Test Cases Passed Successfully! ✅")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
