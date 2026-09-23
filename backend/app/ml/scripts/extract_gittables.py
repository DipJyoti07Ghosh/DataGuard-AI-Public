"""
DataGuard AI — Phase C.3: Extract GitTables Benchmark Columns

Reads the GitTables benchmark and produces a labeled training CSV from:
  - 1,101 tables under data/gittables_benchmark/tables/
  - 2,533 DBpedia ground truth annotations
  - 721 Schema.org ground truth annotations

Each GitTables column is annotated with a DBpedia or Schema.org type.
We map those types to our 12-domain taxonomy and emit one row per column.

Output: app/ml/artifacts/training_data_gittables.csv

Usage (from backend/, in the dataguard env):

    python -m app.ml.scripts.extract_gittables
"""

import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[3]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "gittables_benchmark"
TABLES_DIR = DATA_DIR / "tables"
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
OUTPUT_FILE = ARTIFACTS_DIR / "training_data_gittables.csv"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("dataguard.ml.extract_gittables")


# ===========================================================================
# DBpedia → 12-domain mapping
# ===========================================================================
DBPEDIA_TO_DOMAIN: Dict[str, str] = {
    # Identifier
    "id": "Identifier",
    "identifier": "Identifier",
    "isbn": "Identifier",
    "issn": "Identifier",
    "code": "Identifier",
    "reference": "Identifier",
    "number": "Identifier",
    "key": "Identifier",
    "uuid": "Identifier",
    "symbol": "Identifier",

    # Contact Information
    "email": "Contact Information",
    "emailaddress": "Contact Information",
    "phone": "Contact Information",
    "phonenumber": "Contact Information",
    "fax": "Contact Information",
    "mobile": "Contact Information",
    "website": "Contact Information",
    "homepage": "Contact Information",
    "url": "Contact Information",

    # Personal Information
    "name": "Personal Information",
    "givenname": "Personal Information",
    "surname": "Personal Information",
    "familyname": "Personal Information",
    "firstname": "Personal Information",
    "lastname": "Personal Information",
    "author": "Personal Information",
    "editor": "Personal Information",
    "director": "Personal Information",
    "producer": "Personal Information",
    "writer": "Personal Information",
    "artist": "Personal Information",
    "composer": "Personal Information",
    "person": "Personal Information",
    "actor": "Personal Information",

    # Financial
    "price": "Financial",
    "salary": "Financial",
    "cost": "Financial",
    "amount": "Financial",
    "revenue": "Financial",
    "currency": "Financial",
    "money": "Financial",
    "budget": "Financial",
    "fee": "Financial",
    "tax": "Financial",
    "income": "Financial",
    "profit": "Financial",
    "debt": "Financial",
    "expenditure": "Financial",
    "capital": "Financial",
    "assets": "Financial",
    "interest": "Financial",
    "loan": "Financial",
    "payment": "Financial",
    "transaction": "Financial",

    # Demographic
    "age": "Demographic",
    "gender": "Demographic",
    "sex": "Demographic",
    "nationality": "Demographic",
    "ethnicity": "Demographic",
    "religion": "Demographic",
    "language": "Demographic",
    "occupation": "Demographic",
    "education": "Demographic",
    "profession": "Demographic",
    "maritalstatus": "Demographic",

    # Location
    "location": "Location",
    "place": "Location",
    "country": "Location",
    "city": "Location",
    "town": "Location",
    "village": "Location",
    "state": "Location",
    "province": "Location",
    "region": "Location",
    "district": "Location",
    "address": "Location",
    "postalcode": "Location",
    "zipcode": "Location",
    "latitude": "Location",
    "longitude": "Location",
    "coordinates": "Location",
    "area": "Location",
    "populatedplace": "Location",
    "settlement": "Location",

    # Temporal
    "date": "Temporal",
    "time": "Temporal",
    "year": "Temporal",
    "month": "Temporal",
    "day": "Temporal",
    "hour": "Temporal",
    "minute": "Temporal",
    "second": "Temporal",
    "duration": "Temporal",
    "created": "Temporal",
    "modified": "Temporal",
    "updated": "Temporal",
    "timestamp": "Temporal",
    "birthdate": "Temporal",
    "deathdate": "Temporal",
    "startdate": "Temporal",
    "enddate": "Temporal",
    "publicationdate": "Temporal",

    # Numerical / Measurement
    "min": "Numerical / Measurement",
    "max": "Numerical / Measurement",
    "mean": "Numerical / Measurement",
    "median": "Numerical / Measurement",
    "sum": "Numerical / Measurement",
    "count": "Numerical / Measurement",
    "size": "Numerical / Measurement",
    "length": "Numerical / Measurement",
    "width": "Numerical / Measurement",
    "height": "Numerical / Measurement",
    "weight": "Numerical / Measurement",
    "mass": "Numerical / Measurement",
    "volume": "Numerical / Measurement",
    "capacity": "Numerical / Measurement",
    "speed": "Numerical / Measurement",
    "temperature": "Numerical / Measurement",
    "distance": "Numerical / Measurement",
    "altitude": "Numerical / Measurement",
    "depth": "Numerical / Measurement",
    "rank": "Numerical / Measurement",
    "rating": "Numerical / Measurement",
    "score": "Numerical / Measurement",
    "percentage": "Numerical / Measurement",
    "ratio": "Numerical / Measurement",
    "frequency": "Numerical / Measurement",

    # Categorical
    "type": "Categorical",
    "category": "Categorical",
    "class": "Categorical",
    "kind": "Categorical",
    "status": "Categorical",
    "species": "Categorical",
    "genre": "Categorical",
    "colour": "Categorical",
    "color": "Categorical",
    "style": "Categorical",
    "format": "Categorical",
    "level": "Categorical",
    "grade": "Categorical",
    "tier": "Categorical",
    "flag": "Categorical",

    # Text
    "comment": "Text",
    "note": "Text",
    "abstract": "Text",
    "description": "Text",
    "summary": "Text",
    "text": "Text",
    "content": "Text",
    "title": "Text",
    "subject": "Text",
    "caption": "Text",
    "label": "Text",
    "slogan": "Text",
    "motto": "Text",
    "biography": "Text",
    "quote": "Text",
    "album": "Text",

    # Technical / System
    "ip": "Technical / System",
    "ipaddress": "Technical / System",
    "host": "Technical / System",
    "hostname": "Technical / System",
    "port": "Technical / System",
    "protocol": "Technical / System",
    "version": "Technical / System",
    "build": "Technical / System",
    "server": "Technical / System",
    "endpoint": "Technical / System",
    "api": "Technical / System",
    "session": "Technical / System",
    "device": "Technical / System",
    "os": "Technical / System",
    "browser": "Technical / System",
    "useragent": "Technical / System",

    # Other / fallbacks
    "other": "Other",
    "misc": "Other",
    "unknown": "Other",
    "miscellaneous": "Other",
    "abbreviation": "Categorical",
    "access": "Categorical",
    "activity": "Categorical",
    "alias": "Identifier",
    "award": "Categorical",
    "block": "Identifier",
}


# ===========================================================================
# Schema.org → 12-domain mapping
# ===========================================================================
SCHEMA_TO_DOMAIN: Dict[str, str] = {
    # Identifier
    "id": "Identifier",
    "code": "Identifier",
    "identifier": "Identifier",
    "sku": "Identifier",
    "gtin": "Identifier",
    "isbn": "Identifier",
    "product id": "Identifier",

    # Contact
    "url": "Contact Information",
    "email": "Contact Information",
    "telephone": "Contact Information",
    "faxNumber": "Contact Information",

    # Personal
    "author": "Personal Information",
    "name": "Personal Information",
    "givenName": "Personal Information",
    "familyName": "Personal Information",
    "person": "Personal Information",
    "publisher": "Personal Information",

    # Financial
    "price": "Financial",
    "amount": "Financial",
    "payment": "Financial",

    # Location
    "address": "Location",
    "city": "Location",
    "country": "Location",
    "region": "Location",
    "postalCode": "Location",
    "latitude": "Location",
    "longitude": "Location",

    # Temporal
    "start time": "Temporal",
    "end time": "Temporal",
    "date": "Temporal",
    "year": "Temporal",
    "duration": "Temporal",

    # Numerical
    "width": "Numerical / Measurement",
    "height": "Numerical / Measurement",
    "depth": "Numerical / Measurement",
    "weight": "Numerical / Measurement",
    "line": "Numerical / Measurement",
    "size": "Numerical / Measurement",
    "quantity": "Numerical / Measurement",
    "numberOfItems": "Numerical / Measurement",

    # Categorical
    "category": "Categorical",
    "type": "Categorical",
    "color": "Categorical",
    "content type": "Categorical",
    "class": "Categorical",

    # Text
    "title": "Text",
    "description": "Text",
    "abstract": "Text",
    "comment": "Text",
    "text": "Text",
    "parent": "Text",

    # Technical
    "port": "Technical / System",
    "protocol": "Technical / System",
    "version": "Technical / System",

    # Other
    "other": "Other",
    "action": "Other",
}


# ===========================================================================
# Metadata extraction
# ===========================================================================
def _safe_float(v: Any) -> float:
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return 0.0
        return round(f, 4)
    except Exception:
        return 0.0


def extract_column_features(series: pd.Series) -> Dict[str, Any]:
    """Compute per-column metadata. Never includes raw values."""
    n_rows = len(series)
    n_missing = int(series.isna().sum())
    non_null = series.dropna()
    n_non_null = len(non_null)
    n_unique = int(non_null.nunique())

    missing_pct = round(n_missing / n_rows * 100, 2) if n_rows > 0 else 0.0
    unique_pct = round(n_unique / n_non_null * 100, 2) if n_non_null > 0 else 0.0

    is_numeric = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
    if is_numeric and n_non_null > 1:
        try:
            clean = pd.to_numeric(non_null, errors="coerce").dropna()
        except Exception:
            clean = pd.Series(dtype=float)
        if len(clean) > 1:
            mean_val = _safe_float(clean.mean())
            std_val = _safe_float(clean.std())
            skew = _safe_float(clean.skew()) if len(clean) > 2 else 0.0
            kurt = _safe_float(clean.kurt()) if len(clean) > 3 else 0.0
        else:
            mean_val = std_val = skew = kurt = 0.0
    else:
        mean_val = std_val = skew = kurt = 0.0

    if not is_numeric and n_non_null > 0:
        try:
            avg_len = _safe_float(non_null.astype(str).str.len().mean())
        except Exception:
            avg_len = 0.0
    else:
        avg_len = 0.0

    return {
        "dtype": str(series.dtype),
        "missing_pct": missing_pct,
        "unique_pct": unique_pct,
        "cardinality": n_unique,
        "row_count": n_rows,
        "mean": mean_val,
        "std": std_val,
        "skewness": skew,
        "kurtosis": kurt,
        "avg_str_len": avg_len,
    }


# ===========================================================================
# Column lookup
# ===========================================================================
def find_column(df: pd.DataFrame, column_index: int) -> Optional[pd.Series]:
    """Return the Series for column index `column_index` (0-based)."""
    actual_col_name = f"col{column_index}"
    if actual_col_name in df.columns:
        return df[actual_col_name]
    return None


# ===========================================================================
# Main
# ===========================================================================
def main():
    logger.info("=" * 60)
    logger.info("  GitTables Extractor (Phase C.3)")
    logger.info("=" * 60)

    dbpedia_gt_path = DATA_DIR / "dbpedia_gt.csv"
    schema_gt_path = DATA_DIR / "schema_gt.csv"

    if not dbpedia_gt_path.exists() or not schema_gt_path.exists():
        logger.error("Ground truth files missing. Run the download script first.")
        return

    dbpedia_gt = pd.read_csv(dbpedia_gt_path)
    schema_gt = pd.read_csv(schema_gt_path)

    logger.info(f"DBpedia ground truth rows: {len(dbpedia_gt)}")
    logger.info(f"Schema.org ground truth rows: {len(schema_gt)}")

    all_annotations = pd.concat([
        dbpedia_gt.assign(source="dbpedia"),
        schema_gt.assign(source="schema"),
    ], ignore_index=True)

    rows: List[Dict[str, Any]] = []
    tables_missing = 0
    columns_missing = 0
    domains_dropped_other = 0
    columns_extracted = 0

    for ann_idx, ann in all_annotations.iterrows():
        raw_table_id = str(ann["table_id"])
        table_id = re.sub(r"_(dbpedia|schema)$", "", raw_table_id)
        column_index = int(ann["target_column"])
        annotation_label = str(ann["annotation_label"]).strip()
        source = ann["source"]

        if source == "dbpedia":
            domain = DBPEDIA_TO_DOMAIN.get(annotation_label.lower())
        else:
            domain = SCHEMA_TO_DOMAIN.get(annotation_label)

        if domain is None:
            continue

        if domain == "Other":
            domains_dropped_other += 1
            continue

        table_path = TABLES_DIR / f"{table_id}.csv"
        if not table_path.exists():
            tables_missing += 1
            continue

        try:
            df = pd.read_csv(table_path, nrows=5000, low_memory=False)
        except Exception:
            continue

        series = find_column(df, column_index)
        if series is None:
            columns_missing += 1
            continue

        feats = extract_column_features(series)

        rows.append({
            "column_name": f"col{column_index}",
            "dtype": feats["dtype"],
            "is_numeric": 1 if feats["dtype"].startswith(("int", "float")) else 0,
            "is_string": 1 if feats["dtype"].startswith("object") else 0,
            "is_datetime": 1 if "datetime" in feats["dtype"] else 0,
            "is_boolean": 1 if feats["dtype"] == "bool" else 0,
            "is_categorical": 1 if feats["unique_pct"] < 15.0 else 0,
            "missing_pct": feats["missing_pct"],
            "unique_pct": feats["unique_pct"],
            "cardinality": feats["cardinality"],
            "row_count": feats["row_count"],
            "mean": feats["mean"],
            "std": feats["std"],
            "skewness": feats["skewness"],
            "kurtosis": feats["kurtosis"],
            "avg_str_len": feats["avg_str_len"],
            "has_pii": 0,
            "pii_entity": "NONE",
            "pii_confidence": 0.0,
            "pii_detection_rate": 0.0,
            "quality_failure_count": 0,
            "has_quality_issues": 0,
            "target_domain": domain,
        })
        columns_extracted += 1

        if (ann_idx + 1) % 500 == 0:
            logger.info(f"Processed {ann_idx + 1}/{len(all_annotations)} annotations ({columns_extracted} columns extracted)")

    df_out = pd.DataFrame(rows)

    if df_out.empty:
        logger.error("No columns extracted. Check table paths and annotation format.")
        return

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(OUTPUT_FILE, index=False)

    logger.info("=" * 60)
    logger.info(f"Tables missing: {tables_missing}")
    logger.info(f"Columns missing in tables: {columns_missing}")
    logger.info(f"Dropped as 'Other': {domains_dropped_other}")
    logger.info(f"Extracted: {columns_extracted} labeled columns")
    logger.info(f"Saved to {OUTPUT_FILE}")
    logger.info(f"File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")
    logger.info("=" * 60)

    print()
    print("Domain distribution:")
    print(df_out["target_domain"].value_counts().to_string())


if __name__ == "__main__":
    main()