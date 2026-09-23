"""
DataGuard AI — Phase B.4: Rule-Based Auto-Labeler

Reads the column_metadata.json produced by Phase B.3, applies deterministic
name-based rules to assign each column to one of the 12 semantic domains,
and writes:

  - app/ml/artifacts/training_data_kaggle.csv

The rules are intentionally conservative: when no rule fires, the column is
dropped (rather than dumped into "Other"). This keeps the Phase B training
signal clean.

Usage (from backend/, in the dataguard env):

    python -m app.ml.scripts.label_with_rules
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[3]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
INPUT_FILE = ARTIFACTS_DIR / "column_metadata.json"
OUTPUT_FILE = ARTIFACTS_DIR / "training_data_kaggle.csv"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("dataguard.ml.label_with_rules")


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------
def normalize(name: str) -> str:
    """
    'customerID'           -> 'customer_id'
    'TotalCharges'         -> 'total_charges'
    'Street Address'       -> 'street_address'
    'PJMW_MW'              -> 'pjmw_mw'
    """
    if not name:
        return ""
    # Insert underscore between lower→upper and letter→digit
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(name))
    # Replace all non-alphanumerics with underscore
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
    return s.strip("_").lower()


# ---------------------------------------------------------------------------
# Rule definitions (order matters: more specific first)
# ---------------------------------------------------------------------------
RULES = [
    # ---------- Identifier ----------
    (r"(^|_)(id|uuid|guid|key|identifier|token|serial|ref|reference|no|number)$", "Identifier"),
    (r"^(id|_id|uuid|guid)$", "Identifier"),

    # ---------- Contact Information ----------
    (r"email|e_?mail|mail_id|mail$", "Contact Information"),
    (r"phone|mobile|cell|telephone|tel$|contact_no|fax|whatsapp|sms", "Contact Information"),

    # ---------- Financial ----------
    (r"salary|income|revenue|price|amount|balance|cost|spend|charge|payment|fee|tax|profit|budget|invoice|discount|credit|debit|loan|interest|transaction_amount|total_charges|monthly_charges", "Financial"),
    (r"(^|_)amt($|_)|(^|_)amount($|_)|(^|_)usd($|_)|(^|_)eur($|_)|(^|_)inr($|_)", "Financial"),

    # ---------- Demographic ----------
    (r"(^|_)(age|gender|sex|race|ethnicity|nationality|religion|marital|education|occupation|employment|household|family_size|children|senior|adult|citizen)", "Demographic"),

    # ---------- Location ----------
    (r"(^|_)(city|state|country|province|region|district|address|street|zip|postal|latitude|longitude|lat$|lon$|lng|geo|location|area|neighborhood)", "Location"),

    # ---------- Temporal ----------
    (r"(^|_)(date|time|timestamp|year|month|quarter|day|hour|created|updated|modified|deleted|start|end|expiry|dob|birth)", "Temporal"),
    (r"(_at$|_on$|_dt$)", "Temporal"),

    # ---------- Numerical / Measurement ----------
    (r"(^|_)(count|quantity|qty|weight|height|length|width|depth|distance|duration|speed|temperature|pressure|volume|density|frequency|amplitude|intensity|score|rating|percentage|percent|pct|ratio|latency|mw|kw|kwh|load|consumption)", "Numerical / Measurement"),

    # ---------- Technical / System ----------
    (r"(^|_)(ip|ip_address|host|hostname|mac|port|endpoint|url|uri|user_agent|browser|os|version|build|server|protocol|http|api|log|error|stack|trace|session|device|client_id|environment|container|pod|namespace|service)", "Technical / System"),

    # ---------- Categorical ----------
    (r"(^|_)(status|category|type|tier|plan|segment|channel|priority|stage|flag|is_|has_|role|level|grade|tier|subscription|membership|payment_method|product_category)", "Categorical"),

    # ---------- Text ----------
    (r"(^|_)(description|desc|notes|comment|review|feedback|summary|message|body|content|text|transcript|article|bio|memo|abstract)", "Text"),

    # ---------- Personal Information ----------
    # Note: applied AFTER Contact/Financial so it doesn't over-capture
    (r"(^|_)(name|first_name|last_name|full_name|fname|lname|surname|nickname|title|person)", "Personal Information"),
]


# ---------------------------------------------------------------------------
# Special overrides for columns we know the answer to from the sample data
# (helps catch domain-specific patterns the rules above missed)
# ---------------------------------------------------------------------------
EXPLICIT_MATCHES = {
    # Credit card fraud dataset — V1..V28 are anonymized PCA features
    "v1": "Other", "v2": "Other", "v3": "Other", "v4": "Other", "v5": "Other",
    "v6": "Other", "v7": "Other", "v8": "Other", "v9": "Other", "v10": "Other",
    "v11": "Other", "v12": "Other", "v13": "Other", "v14": "Other", "v15": "Other",
    "v16": "Other", "v17": "Other", "v18": "Other", "v19": "Other", "v20": "Other",
    "v21": "Other", "v22": "Other", "v23": "Other", "v24": "Other", "v25": "Other",
    "v26": "Other", "v27": "Other", "v28": "Other",
    # Time/Amount in credit card dataset — these ARE temporal/financial
    # (but leave them for the rules)
    # Iris dataset species is categorical
    "species": "Categorical",
    # Reviews dataset
    "productid": "Identifier",
    "userid": "Identifier",
    "profileName": "Personal Information",
    "helpfulnessNumerator": "Numerical / Measurement",
    "helpfulnessDenominator": "Numerical / Measurement",
    "score": "Numerical / Measurement",
    # Wine reviews
    "points": "Numerical / Measurement",
    "price": "Financial",
    "variety": "Categorical",
    "winery": "Other",
    "designation": "Text",
    "region_1": "Location", "region_2": "Location",
    "taster_name": "Personal Information",
    "taster_twitter_handle": "Contact Information",
    "province": "Location", "country": "Location",
    "title": "Text",
}


def label_column(column_name: str, source_file: str, metadata: Dict) -> Optional[str]:
    """
    Return the semantic domain label for a column, or None if no rule matches.
    """
    normalized = normalize(column_name)

    # 1. Check explicit matches first
    if normalized in EXPLICIT_MATCHES:
        return EXPLICIT_MATCHES[normalized]

    # 2. Apply ordered rules
    for pattern, label in RULES:
        if re.search(pattern, normalized, re.IGNORECASE):
            return label

    # 3. Fallbacks based on dtype and stats (only when no name-based rule matched)

    # Very low uniqueness + string + short avg length -> Categorical
    if (
        metadata.get("dtype", "").startswith("object")
        and metadata.get("unique_pct", 100) < 15.0
        and metadata.get("avg_str_len", 0) < 30
    ):
        return "Categorical"

    # Very long strings (avg > 50 chars) -> Text
    if (
        metadata.get("dtype", "").startswith("object")
        and metadata.get("avg_str_len", 0) > 50
    ):
        return "Text"

    # 100% unique strings -> Identifier
    if (
        metadata.get("dtype", "").startswith("object")
        and metadata.get("unique_pct", 0) > 95.0
    ):
        return "Identifier"

    # High-entropy numeric with skewness -> Numerical
    if (
        metadata.get("dtype", "").startswith(("int", "float"))
        and metadata.get("unique_pct", 0) > 20.0
    ):
        return "Numerical / Measurement"

    # No confident label
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    logger.info("=" * 60)
    logger.info("  Rule-Based Auto-Labeler (Phase B.4)")
    logger.info("=" * 60)

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}\n"
            f"Run `python -m app.ml.scripts.extract_columns` first."
        )

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw_columns = json.load(f)

    logger.info(f"Loaded {len(raw_columns)} columns from {INPUT_FILE.name}")

    # Apply rules
    labeled_rows = []
    unlabeled_count = 0

    for rec in raw_columns:
        col_name = rec.get("column_name", "")
        source_file = rec.get("source_file", "")

        label = label_column(col_name, source_file, rec)
        if label is None:
            unlabeled_count += 1
            continue

        # Skip the "Other" fallback — too noisy for training
        if label == "Other":
            unlabeled_count += 1
            continue

        # Build the row in the same format as the synthetic CSV
        labeled_rows.append({
            "column_name": col_name,
            "dtype": rec.get("dtype", "object"),
            "is_numeric": 1 if rec.get("dtype", "").startswith(("int", "float")) else 0,
            "is_string": 1 if rec.get("dtype", "").startswith("object") else 0,
            "is_datetime": 1 if "datetime" in rec.get("dtype", "") else 0,
            "is_boolean": 1 if rec.get("dtype", "") == "bool" else 0,
            "is_categorical": 1 if rec.get("unique_pct", 100) < 15.0 else 0,
            "missing_pct": rec.get("missing_pct", 0.0),
            "unique_pct": rec.get("unique_pct", 0.0),
            "cardinality": rec.get("cardinality", 0),
            "row_count": rec.get("row_count", 100),
            "mean": rec.get("mean", 0.0),
            "std": rec.get("std", 0.0),
            "skewness": rec.get("skewness", 0.0),
            "kurtosis": rec.get("kurtosis", 0.0),
            "avg_str_len": rec.get("avg_str_len", 0.0),
            "has_pii": 0,
            "pii_entity": "NONE",
            "pii_confidence": 0.0,
            "pii_detection_rate": 0.0,
            "quality_failure_count": 0,
            "has_quality_issues": 0,
            "target_domain": label,
        })

    df = pd.DataFrame(labeled_rows)

    if df.empty:
        logger.error("No columns were labeled. Check the rules.")
        return

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    logger.info("=" * 60)
    logger.info(f"Labeled {len(df)} columns")
    logger.info(f"Dropped (unlabeled/Other): {unlabeled_count}")
    logger.info(f"Saved to {OUTPUT_FILE}")
    logger.info(f"File size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")
    logger.info("=" * 60)

    # Show domain distribution
    print()
    print("Labeled domain distribution:")
    print(df["target_domain"].value_counts().to_string())
    print()
    print("Sample labeled columns:")
    print(df[["column_name", "dtype", "target_domain"]].head(20).to_string(index=False))


if __name__ == "__main__":
    main()