"""
DataGuard AI — Phase C.1: Fetch GitTables Benchmark

Downloads the GitTables benchmark from Zenodo (record 5706316):
  - 1101 tables (tables.zip)
  - DBpedia ontology labels, targets, and ground truth
  - Schema.org ontology labels, targets, and ground truth

This is hand-curated gold data for column type detection. It will be
mapped to our 12-domain taxonomy in Phase C.2.

Source: https://zenodo.org/records/5706316

Output: backend/app/ml/artifacts/gittables_benchmark/

Usage (from backend/, in the dataguard env):

    python -m app.ml.scripts.fetch_gittables_benchmark
"""

import logging
import sys
import zipfile
from pathlib import Path

import httpx

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[3]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ZENODO_BASE = "https://zenodo.org/records/5706316/files"

# Files we need (by their Zenodo download names)
FILES_TO_DOWNLOAD = [
    "tables.zip",
    "dbpedia_targets.csv",
    "dbpedia_gt.csv",
    "dbpedia_labels.csv",
    "schema.org_targets.csv",
    "schema.org_gt.csv",
    "schema.org_labels.csv",
]

# Raw external downloads live under backend/data/
# scripts/ is at backend/app/ml/scripts/, so parents[3] = backend/
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
TARGET_DIR = DATA_DIR / "gittables_benchmark"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("dataguard.ml.fetch_gittables")


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------
def download_file(client: httpx.Client, filename: str, dest: Path) -> bool:
    """Download a single file from Zenodo. Returns True on success."""
    # Zenodo URL structure: /records/{id}/files/{filename}?download=1
    url = f"{ZENODO_BASE}/{filename}?download=1"

    if dest.exists() and dest.stat().st_size > 0:
        logger.info(f"SKIP (exists): {filename} ({dest.stat().st_size / 1024:.1f} KB)")
        return True

    logger.info(f"Downloading {filename}...")
    try:
        with client.stream("GET", url, follow_redirects=True) as r:
            if r.status_code != 200:
                logger.warning(f"  ❌ HTTP {r.status_code} for {filename}")
                return False
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(8192):
                    f.write(chunk)
                    downloaded += len(chunk)
            logger.info(f"  ✅ Saved {filename} ({downloaded / 1024:.1f} KB)")
            return True
    except Exception as e:
        logger.warning(f"  ❌ Failed: {type(e).__name__}: {e}")
        if dest.exists():
            dest.unlink()
        return False


def extract_tables(tables_zip: Path, target_dir: Path) -> bool:
    """Extract tables.zip into a subdirectory."""
    extract_dir = target_dir / "tables"
    if extract_dir.exists() and any(extract_dir.iterdir()):
        logger.info(f"SKIP (exists): tables/ already has files")
        return True

    logger.info(f"Extracting {tables_zip.name}...")
    try:
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tables_zip, "r") as z:
            z.extractall(extract_dir)
        n = len(list(extract_dir.glob("*.csv")))
        logger.info(f"  ✅ Extracted {n} tables")
        return True
    except Exception as e:
        logger.warning(f"  ❌ Extraction failed: {type(e).__name__}: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    logger.info("=" * 60)
    logger.info("  GitTables Benchmark Fetcher (Phase C.1)")
    logger.info("=" * 60)
    logger.info(f"Target: {TARGET_DIR}")

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = []

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for filename in FILES_TO_DOWNLOAD:
            dest = TARGET_DIR / filename
            if download_file(client, filename, dest):
                success += 1
            else:
                failed.append(filename)

    # Extract tables.zip if present
    tables_zip = TARGET_DIR / "tables.zip"
    if tables_zip.exists():
        extract_tables(tables_zip, TARGET_DIR)

    logger.info("=" * 60)
    logger.info(f"Downloaded: {success}/{len(FILES_TO_DOWNLOAD)}")
    if failed:
        logger.warning(f"Failed: {', '.join(failed)}")
    logger.info("=" * 60)

    # List what we have
    print()
    print("Files in target directory:")
    for p in sorted(TARGET_DIR.iterdir()):
        if p.is_file():
            print(f"  {p.stat().st_size / 1024:>8.1f} KB  {p.name}")
        else:
            n = len(list(p.iterdir()))
            print(f"  {'<dir>':>8}      {p.name}/  ({n} files)")


if __name__ == "__main__":
    main()