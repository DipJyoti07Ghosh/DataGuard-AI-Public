"""
DataGuard AI — ML Feature Extractor & Preprocessing Pipeline

Transforms column metadata, statistical moments, PII findings, and quality signals
into structured feature representations for scikit-learn models.
Enforces identical feature schemas for both training and real-time inference.
"""

import re
from typing import Any, Dict, List
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

NUMERIC_FEATURE_COLS = [
    "is_numeric",
    "is_string",
    "is_datetime",
    "is_boolean",
    "is_categorical",
    "missing_pct",
    "unique_pct",
    "cardinality",
    "mean",
    "std",
    "skewness",
    "kurtosis",
    "avg_str_len",
    "has_pii",
    "pii_confidence",
    "pii_detection_rate",
    "pii_is_email",
    "pii_is_phone",
    "pii_is_person",
    "pii_is_ip",
    "pii_is_card",
    "pii_is_ssn",
    "pii_is_location",
    "pii_is_url",
    "quality_failure_count",
    "has_quality_issues",
]

TEXT_FEATURE_COL = "clean_column_name"


def normalize_column_name(column_name: str) -> str:
    """
    Normalizes a column name into clean whitespace-separated sub-tokens.
    e.g., 'customer_email_address' -> 'customer email address'
          'userMonthlyIncome' -> 'user monthly income'
    """
    if not column_name:
        return "unknown"

    # CamelCase splitting
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(column_name))
    # Replace non-alphanumeric with spaces
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s)
    return s.strip().lower() or "unknown"


def extract_column_feature_dict(
    col_name: str,
    col_profile: Dict[str, Any] = None,
    pii_findings: List[Dict[str, Any]] = None,
    quality_expectations: List[Dict[str, Any]] = None,
    row_count: int = 100,
) -> Dict[str, Any]:
    """
    Constructs a standardized feature dictionary for a single dataset column
    by merging Phase 4 profiling, Phase 5 quality, and Phase 6 PII results.
    NEVER extracts or includes raw sensitive values.
    """
    col_profile = col_profile or {}
    pii_findings = pii_findings or []
    quality_expectations = quality_expectations or []

    # 1. Normalized text tokens
    clean_name = normalize_column_name(col_name)

    # 2. Data type indicators
    dtype = str(col_profile.get("dtype", "object")).lower()
    is_numeric = 1 if any(t in dtype for t in ("int", "float", "number")) else 0
    is_string = 1 if any(t in dtype for t in ("object", "string", "str")) else 0
    is_datetime = 1 if any(t in dtype for t in ("datetime", "timestamp", "date")) else 0
    is_boolean = 1 if "bool" in dtype else 0

    # 3. Statistical moments & cardinality
    missing_pct = float(col_profile.get("missing_percentage", 0.0) or 0.0)
    unique_pct = float(col_profile.get("unique_percentage", 0.0) or 0.0)
    distinct_count = int(col_profile.get("distinct_count", 0) or 0)
    if distinct_count == 0 and row_count > 0:
        distinct_count = max(1, int(row_count * (unique_pct / 100.0)))

    is_categorical = 1 if is_boolean or (is_string and distinct_count <= 20) or "category" in dtype else 0

    mean_val = float(col_profile.get("mean", 0.0) or 0.0) if is_numeric else 0.0
    std_val = float(col_profile.get("std", 0.0) or 0.0) if is_numeric else 0.0
    skew_val = float(col_profile.get("skewness", 0.0) or 0.0) if is_numeric else 0.0
    kurt_val = float(col_profile.get("kurtosis", 0.0) or 0.0) if is_numeric else 0.0

    # 4. String length estimates
    avg_len = 0.0
    if is_string:
        avg_len = float(col_profile.get("avg_length", 15.0) or 15.0)

    # 5. PII Signals (Phase 6)
    # Find findings matching this column
    col_pii = [f for f in pii_findings if f.get("column_name") == col_name]
    has_pii = 1 if len(col_pii) > 0 else 0
    max_conf = max([float(f.get("confidence", 0.0) or 0.0) for f in col_pii], default=0.0)
    max_rate = max([float(f.get("detection_rate", 0.0) or 0.0) for f in col_pii], default=0.0)

    pii_entities = {str(f.get("entity_type", "")).upper() for f in col_pii}
    pii_is_email = 1 if "EMAIL_ADDRESS" in pii_entities else 0
    pii_is_phone = 1 if "PHONE_NUMBER" in pii_entities else 0
    pii_is_person = 1 if "PERSON" in pii_entities else 0
    pii_is_ip = 1 if "IP_ADDRESS" in pii_entities else 0
    pii_is_card = 1 if any(e in pii_entities for e in ("CREDIT_CARD", "IBAN_CODE", "CRYPTO")) else 0
    pii_is_ssn = 1 if any(e in pii_entities for e in ("US_SSN", "PASSPORT", "US_DRIVER_LICENSE")) else 0
    pii_is_location = 1 if "LOCATION" in pii_entities else 0
    pii_is_url = 1 if "URL" in pii_entities else 0

    # 6. Quality Signals (Phase 5)
    col_failures = [e for e in quality_expectations if e.get("column_name") == col_name and not e.get("success", True)]
    failure_count = len(col_failures)
    has_quality_issues = 1 if failure_count > 0 else 0

    return {
        "clean_column_name": clean_name,
        "is_numeric": is_numeric,
        "is_string": is_string,
        "is_datetime": is_datetime,
        "is_boolean": is_boolean,
        "is_categorical": is_categorical,
        "missing_pct": missing_pct,
        "unique_pct": unique_pct,
        "cardinality": distinct_count,
        "mean": mean_val,
        "std": std_val,
        "skewness": skew_val,
        "kurtosis": kurt_val,
        "avg_str_len": avg_len,
        "has_pii": has_pii,
        "pii_confidence": max_conf,
        "pii_detection_rate": max_rate,
        "pii_is_email": pii_is_email,
        "pii_is_phone": pii_is_phone,
        "pii_is_person": pii_is_person,
        "pii_is_ip": pii_is_ip,
        "pii_is_card": pii_is_card,
        "pii_is_ssn": pii_is_ssn,
        "pii_is_location": pii_is_location,
        "pii_is_url": pii_is_url,
        "quality_failure_count": failure_count,
        "has_quality_issues": has_quality_issues,
    }


def prepare_training_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Processes the raw bootstrap generator DataFrame into the exact training feature format.
    """
    df = df_raw.copy()
    df["clean_column_name"] = df["column_name"].apply(normalize_column_name)

    # One-hot PII indicators if not already present
    for ent_type, col_key in [
        ("EMAIL_ADDRESS", "pii_is_email"),
        ("PHONE_NUMBER", "pii_is_phone"),
        ("PERSON", "pii_is_person"),
        ("IP_ADDRESS", "pii_is_ip"),
        ("CREDIT_CARD", "pii_is_card"),
        ("US_SSN", "pii_is_ssn"),
        ("LOCATION", "pii_is_location"),
        ("URL", "pii_is_url"),
    ]:
        if col_key not in df.columns:
            df[col_key] = df["pii_entity"].apply(lambda e: 1 if str(e).upper() == ent_type else 0)

    return df


def build_preprocessor() -> ColumnTransformer:
    """
    Constructs the scikit-learn ColumnTransformer combining text vectorization
    and numerical standardization.
    """
    text_pipe = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            max_features=500,
        ))
    ])

    numeric_pipe = Pipeline([
        ("scaler", StandardScaler())
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("text", text_pipe, TEXT_FEATURE_COL),
            ("num", numeric_pipe, NUMERIC_FEATURE_COLS),
        ],
        remainder="drop",
    )

    return preprocessor
