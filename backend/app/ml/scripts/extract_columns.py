"""
DataGuard AI — Phase B.3: Column Metadata Extractor

Walks through backend/data/kaggle_samples/, reads every CSV file, and
extracts per-column metadata:

  - column_name
  - dtype
  - missing_pct
  - unique_pct
  - cardinality
  - row_count
  - numeric moments (mean, std, skewness, kurtosis) when applicable
  - average string length when applicable
  - source_file

Output: app/ml/artifacts/column_metadata.json  (list of column dicts)

Usage (from backend/, in the dataguard env):

    python -m app.ml.scripts.extract_columns
"""

import json
import logging
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[3]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "kaggle_samples"
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
OUTPUT_FILE = ARTIFACTS_DIR / "column_metadata.json"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("dataguard.ml.extract_columns")

# Suppress noisy warnings from pandas on mixed-type columns
warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)
warnings.filterwarnings("ignore", category=UserWarning)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------
def _safe_float(v: Any) -> float:
    """Return a JSON-safe float. NaN/inf become 0.0."""
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return 0.0
        return round(f, 4)
    except Exception:
        return 0.0


def _column_features(series: pd.Series) -> Dict[str, Any]:
    """Compute per-column metadata. Does NOT include any raw values."""
    n_rows = len(series)
    n_missing = int(series.isna().sum())
    non_null = series.dropna()
    n_non_null = len(non_null)
    n_unique = int(non_null.nunique())

    missing_pct = round(n_missing / n_rows * 100, 2) if n_rows > 0 else 0.0
    unique_pct = round(n_unique / n_non_null * 100, 2) if n_non_null > 0 else 0.0
    cardinality = n_unique

    # Statistical moments for numeric columns
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

    # Average string length for text columns
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
        "cardinality": cardinality,
        "row_count": n_rows,
        "mean": mean_val,
        "std": std_val,
        "skewness": skew,
        "kurtosis": kurt,
        "avg_str_len": avg_len,
    }


def extract_from_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Read a CSV and return a list of per-column metadata dicts."""
    try:
        df = pd.read_csv(csv_path, nrows=5000, low_memory=False)
    except Exception as e:
        logger.warning(f"  SKIP {csv_path.name}: {type(e).__name__}: {str(e)[:80]}")
        return []

    if df.shape[1] == 0:
        return []

    records = []
    for col in df.columns:
        try:
            feats = _column_features(df[col])
        except Exception as e:
            logger.warning(f"  Column '{col}' in {csv_path.name} failed: {e}")
            continue
        records.append({
            "column_name": str(col),
            "source_file": csv_path.name,
            **feats,
        })

    return records


def extract_all() -> List[Dict[str, Any]]:
    """Walk DATA_DIR, extract from all CSVs."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Kafka samples dir not found: {DATA_DIR}")

    all_records: List[Dict[str, Any]] = []
    csv_paths = sorted(DATA_DIR.rglob("*.csv"))
    logger.info(f"Found {len(csv_paths)} CSV files")

    for i, csv_path in enumerate(csv_paths, 1):
        rel = csv_path.relative_to(DATA_DIR)
        logger.info(f"[{i}/{len(csv_paths)}] Reading {rel}")
        records = extract_from_csv(csv_path)
        all_records.extend(records)

    return all_records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    logger.info("=" * 60)
    logger.info("  Column Metadata Extractor (Phase B.3)")
    logger.info("=" * 60)
    logger.info(f"Source: {DATA_DIR}")

    records = extract_all()

    if not records:
        logger.error("No columns extracted. Check that CSVs exist under data/kaggle_samples/")
        return

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    # Summary
    sources = sorted({r["source_file"] for r in records})
    logger.info("=" * 60)
    logger.info(f"Extracted {len(records)} columns from {len(sources)} CSV files")
    logger.info(f"Saved to {OUTPUT_FILE}")
    logger.info(f"File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")
    logger.info("=" * 60)

    # Show top sources
    print()
    print("Columns per source file (top 15):")
    from collections import Counter
    counts = Counter(r["source_file"] for r in records)
    for src, n in counts.most_common(15):
        print(f"  {n:>5}  {src}")


if __name__ == "__main__":
    main()