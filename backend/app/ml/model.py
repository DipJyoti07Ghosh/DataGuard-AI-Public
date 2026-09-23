# app/ml/model.py

from pathlib import Path

MODEL_VERSION = "column-risk-v4"          # fallback if discovery fails
FEATURE_SCHEMA_VERSION = "1.0.0"

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


def discover_latest_model_version() -> str:
    """
    Return the highest-numbered column-risk-vN that has BOTH a .joblib
    and a matching metadata JSON present in artifacts/.
    Falls back to MODEL_VERSION if nothing is found.
    """
    candidates = []
    for jb in ARTIFACTS_DIR.glob("column-risk-v*.joblib"):
        # "column-risk-v4.joblib" -> 4
        try:
            n = int(jb.stem.rsplit("-v", 1)[-1])
        except (ValueError, IndexError):
            continue
        meta = ARTIFACTS_DIR / f"metadata_{jb.stem}.json"
        if meta.exists():
            candidates.append((n, jb.stem))
    if not candidates:
        return MODEL_VERSION
    return max(candidates)[1]