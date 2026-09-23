"""
DataGuard AI — Phase B.5: Merge Training Data Sources

Concatenates all available training CSVs into a single merged dataset
for the final training step:

  - training_data_synthetic.csv (Phase A)
  - training_data_kaggle.csv    (Phase B)

The merge is column-aligned (all sources must have the same schema).

Usage (from backend/, in the dataguard env):

    python -m app.ml.scripts.merge_datasets
"""

import logging
import sys
from pathlib import Path
from typing import List

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[3]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
OUTPUT_FILE = ARTIFACTS_DIR / "training_data_merged.csv"

SOURCES: List[Path] = [
    ARTIFACTS_DIR / "training_data_synthetic.csv",
    ARTIFACTS_DIR / "training_data_kaggle.csv",
    ARTIFACTS_DIR / "training_data_gittables.csv",
]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("dataguard.ml.merge_datasets")


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------
def main():
    logger.info("=" * 60)
    logger.info("  Merge Training Data Sources (Phase B.5)")
    logger.info("=" * 60)

    frames = []
    for src in SOURCES:
        if not src.exists():
            logger.warning(f"SKIP (missing): {src.name}")
            continue
        df = pd.read_csv(src)
        logger.info(f"Loaded {len(df):>5} rows from {src.name}")
        frames.append(df)

    if not frames:
        logger.error("No sources available to merge.")
        return

    # Concatenate — pandas aligns columns by name
    merged = pd.concat(frames, ignore_index=True, sort=False)

    # Validate the domain labels match the 12-class taxonomy
    valid_domains = {
        "Identifier", "Contact Information", "Personal Information", "Financial",
        "Demographic", "Location", "Temporal", "Numerical / Measurement",
        "Categorical", "Text", "Technical / System", "Other",
    }
    invalid = set(merged["target_domain"].unique()) - valid_domains
    if invalid:
        logger.error(f"INVALID domain labels detected: {invalid}")
        logger.error("Fix the source data before training.")
        return

    # Shuffle so sources are interleaved
    merged = merged.sample(frac=1.0, random_state=42).reset_index(drop=True)

    # Save
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT_FILE, index=False)

    logger.info("=" * 60)
    logger.info(f"Merged total: {len(merged)} rows")
    logger.info(f"Saved to {OUTPUT_FILE}")
    logger.info(f"File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")
    logger.info("=" * 60)

    # Domain distribution
    print()
    print("Merged domain distribution:")
    print(merged["target_domain"].value_counts().sort_index().to_string())
    print()
    print("Row counts by source:")
    for src in SOURCES:
        if src.exists():
            n = pd.read_csv(src).shape[0]
            print(f"  {n:>5}  {src.name}")


if __name__ == "__main__":
    main()