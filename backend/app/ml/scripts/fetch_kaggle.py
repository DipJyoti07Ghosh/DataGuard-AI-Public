"""
DataGuard AI — Phase B.2: Kaggle Dataset Fetcher

Downloads a curated list of small-to-medium Kaggle datasets that
collectively provide ~2,000–3,000 real-world column names across
diverse domains (finance, healthcare, e-commerce, HR, location,
temporal, technical logs, etc.).

Raw CSVs are saved to: backend/data/kaggle_samples/

Usage (from backend/, in the dataguard env):

    python -m app.ml.scripts.fetch_kaggle
    python -m app.ml.scripts.fetch_kaggle --max-datasets 10
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[3]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "kaggle_samples"

# A curated list of datasets chosen for DIVERSITY of column names.
# Each entry: (kaggle_slug, approx_size_mb)
# We avoid huge files (>100 MB) to keep downloads fast.
DATASETS = [
    # --- Baseline classics ---
    ("uciml/iris", 1),
    ("uciml/adult-census-income", 5),
    ("c/titanic", 1),

    # --- Financial / banking ---
    ("blastchar/telco-customer-churn", 1),
    ("jsmastery/spotify", 5),
    ("ranja7/vehicle-insurance-customer-data", 5),
    ("arunp77/loan-prediction-dataset", 1),
    ("mrmorj/bank-marketing-dataset", 3),
    ("shantanudhakadd/credit-card-fraud-detection-dataset", 25),
    ("aakashbommidi/airbnb-nyc-2019", 20),

    # --- Healthcare / medical ---
    ("mirichoi0218/insurance", 1),
    ("kaggle/medical-cost-personal-dataset", 1),
    ("programmer3/heart-disease-dataset", 1),
    ("rashikrahmanpritom/heart-attack-analysis-prediction-dataset", 1),

    # --- Location / geospatial ---
    ("rohan0301/unsupervised-learning-on-country-data", 1),
    ("thedevastator/us-baby-names-by-state", 15),
    ("dataworld/airbnb-listings", 5),

    # --- Temporal / time series ---
    ("robikscube/hourly-energy-consumption", 5),
    ("olivierg13/human-development-indexes", 5),
    ("neuromusic/avocado-prices", 1),

    # --- E-commerce / retail / text ---
    ("zynicide/wine-reviews", 40),
    ("snap/amazon-fine-food-reviews", 30),
    ("manjeetsingh/spotify-tracks-dataset", 10),
    ("promptcloud/the-books-dataset", 5),

    # --- HR / marketing / categorical ---
    ("kmldas/employee-attrition", 1),
    ("pavansanagapati/advertising-dataset", 1),
    ("sahistapatel9689/online-retail", 5),

    # --- Technical / logs / system ---
    ("unanimad/web-server-access-logs", 10),
    ("mlg-ulb/creditcardfraud", 25),
    ("nih-chest-xrays/sample", 30),

    # --- Mixed demographic / surveys ---
    ("censusdata/census-education", 5),
    ("harlfoxem/housesalesprediction", 2),
]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("dataguard.ml.fetch_kaggle")


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------
def fetch_datasets(max_datasets: int = None, quiet: bool = False) -> dict:
    """
    Download all configured Kaggle datasets into DATA_DIR.
    Returns a summary dict {downloaded, skipped, failed}.
    """
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    logger.info("Kaggle API authenticated")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Download target: {DATA_DIR}")

    targets = DATASETS if max_datasets is None else DATASETS[:max_datasets]
    logger.info(f"Datasets to download: {len(targets)}")

    summary = {"downloaded": [], "skipped": [], "failed": []}

    for i, (slug, approx_mb) in enumerate(targets, 1):
        # Sanitize slug to a folder-safe name
        folder = slug.replace("/", "__")
        target = DATA_DIR / folder

        if target.exists() and any(target.iterdir()):
            logger.info(f"[{i}/{len(targets)}] SKIP (already exists): {slug}")
            summary["skipped"].append(slug)
            continue

        logger.info(f"[{i}/{len(targets)}] Downloading {slug} (~{approx_mb} MB)...")
        start = time.time()
        try:
            api.dataset_download_files(
                slug,
                path=str(target),
                unzip=True,
                quiet=quiet,
            )
            elapsed = time.time() - start
            logger.info(f"  ✅ Done in {elapsed:.1f}s")
            summary["downloaded"].append(slug)
        except Exception as e:
            logger.warning(f"  ❌ FAILED: {type(e).__name__}: {str(e)[:200]}")
            summary["failed"].append((slug, str(e)[:100]))

    logger.info("=" * 60)
    logger.info(f"Downloaded: {len(summary['downloaded'])}")
    logger.info(f"Skipped:    {len(summary['skipped'])}")
    logger.info(f"Failed:     {len(summary['failed'])}")
    logger.info("=" * 60)

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Download Kaggle datasets for Phase B training data enrichment."
    )
    parser.add_argument(
        "--max-datasets",
        type=int,
        default=None,
        help="Limit to first N datasets (useful for quick testing)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress download progress output",
    )
    args = parser.parse_args()

    summary = fetch_datasets(
        max_datasets=args.max_datasets,
        quiet=args.quiet,
    )

    if summary["failed"]:
        print()
        print("Failed datasets:")
        for slug, err in summary["failed"]:
            print(f"  - {slug}: {err}")


if __name__ == "__main__":
    main()