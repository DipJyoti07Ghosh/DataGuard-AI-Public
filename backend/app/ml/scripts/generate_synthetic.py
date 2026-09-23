"""
DataGuard AI — Phase A: Synthetic Training Data Generator (Standalone Script)

Generates the synthetic bootstrap training CSV for the column domain
classifier and writes it to the ML artifacts directory.

Usage (from backend/ folder, with `dataguard` conda env active):

    python -m app.ml.scripts.generate_synthetic

    # or with a custom sample count:
    python -m app.ml.scripts.generate_synthetic --samples 500

Output:
    backend/app/ml/artifacts/training_data_synthetic.csv
"""

import argparse
import logging
import sys
from pathlib import Path

# Add backend root to sys.path so `app.ml...` imports work when run as script
backend_root = Path(__file__).resolve().parents[3]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.ml.training_data import generate_bootstrap_training_data, DOMAINS


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
OUTPUT_FILE = ARTIFACTS_DIR / "training_data_synthetic.csv"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("dataguard.ml.generate_synthetic")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(samples_per_domain: int = 300, random_state: int = 42) -> None:
    logger.info("=" * 60)
    logger.info("  Synthetic Training Data Generator (Phase A)")
    logger.info("=" * 60)
    logger.info(f"Samples per domain: {samples_per_domain}")
    logger.info(f"Total expected rows: {samples_per_domain * len(DOMAINS)}")
    logger.info(f"Output: {OUTPUT_FILE}")

    # Ensure artifacts directory exists
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate
    df = generate_bootstrap_training_data(
        samples_per_domain=samples_per_domain,
        random_state=random_state,
    )

    # Persist
    df.to_csv(OUTPUT_FILE, index=False)

    logger.info("-" * 60)
    logger.info(f"Generated {len(df)} rows across {df['target_domain'].nunique()} domains")
    logger.info(f"Saved to {OUTPUT_FILE}")
    logger.info(f"File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")
    logger.info("=" * 60)

    # Print a compact preview
    print()
    print("Domain distribution:")
    print(df["target_domain"].value_counts().sort_index().to_string())
    print()
    print("Sample rows:")
    print(df[["column_name", "dtype", "target_domain"]].head(10).to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate synthetic bootstrap training data for the ML column classifier."
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=300,
        help="Samples per domain (default: 300)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()
    main(samples_per_domain=args.samples, random_state=args.seed)