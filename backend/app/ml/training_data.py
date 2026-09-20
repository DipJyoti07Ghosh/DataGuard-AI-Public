"""
DataGuard AI — ML Column Domain Classification Bootstrap Training Data Generator

Generates a controlled, reproducible bootstrap dataset of labelled column metadata
spanning 12 semantic domains.

IMPORTANT:
This bootstrap dataset is synthetic and designed for initializing the Phase 7 scikit-learn
model pipeline. Production-grade deployment requires continuously collected, human-labelled
enterprise column metadata.
"""

import random
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Semantic Domain Taxonomy (12 Classes)
# ---------------------------------------------------------------------------
DOMAINS = [
    "Identifier",
    "Contact Information",
    "Personal Information",
    "Financial",
    "Demographic",
    "Location",
    "Temporal",
    "Numerical / Measurement",
    "Categorical",
    "Text",
    "Technical / System",
    "Other",
]

# ---------------------------------------------------------------------------
# Domain Prototype Templates
# ---------------------------------------------------------------------------
# Templates define canonical column names, token prefixes/suffixes, and characteristic
# statistical/PII profiles for each domain.
DOMAIN_TEMPLATES: Dict[str, Dict] = {
    "Identifier": {
        "names": [
            "id", "user_id", "customer_id", "account_id", "order_id", "transaction_id",
            "uuid", "guid", "session_id", "client_id", "patient_id", "employee_id",
            "product_id", "sku", "item_code", "record_id", "serial_number", "ssn",
            "tax_id", "device_id", "member_id", "token", "auth_key", "tracking_no",
        ],
        "types": ["int64", "object", "string"],
        "unique_pct_range": (85.0, 100.0),
        "missing_pct_range": (0.0, 5.0),
        "has_pii_prob": 0.35,
        "pii_types": ["US_SSN", "NONE"],
    },
    "Contact Information": {
        "names": [
            "email", "user_email", "customer_email", "contact_email", "work_email",
            "phone", "phone_number", "mobile", "cell", "telephone", "fax",
            "contact_no", "emergency_contact", "secondary_email", "billing_phone",
            "support_email", "alternate_phone", "sms_number", "pager", "contact",
        ],
        "types": ["object", "string"],
        "unique_pct_range": (40.0, 99.0),
        "missing_pct_range": (0.0, 20.0),
        "has_pii_prob": 0.95,
        "pii_types": ["EMAIL_ADDRESS", "PHONE_NUMBER"],
    },
    "Personal Information": {
        "names": [
            "name", "full_name", "first_name", "last_name", "fname", "lname",
            "surname", "customer_name", "user_name", "author_name", "patient_name",
            "client_name", "employee_name", "nickname", "alias", "middle_name",
            "maiden_name", "guardian_name", "beneficiary", "signature",
        ],
        "types": ["object", "string"],
        "unique_pct_range": (30.0, 95.0),
        "missing_pct_range": (0.0, 15.0),
        "has_pii_prob": 0.85,
        "pii_types": ["PERSON"],
    },
    "Financial": {
        "names": [
            "salary", "income", "monthly_spend", "annual_revenue", "price", "amount",
            "balance", "credit_limit", "cost", "total_spent", "credit_card", "card_number",
            "card_no", "cc_num", "iban", "account_balance", "tax_amount", "discount",
            "net_pay", "gross_pay", "fee", "budget", "invoice_amount", "profit",
        ],
        "types": ["float64", "int64", "object"],
        "unique_pct_range": (20.0, 98.0),
        "missing_pct_range": (0.0, 10.0),
        "has_pii_prob": 0.45,
        "pii_types": ["CREDIT_CARD", "IBAN_CODE", "NONE"],
    },
    "Demographic": {
        "names": [
            "age", "gender", "sex", "marital_status", "ethnicity", "race",
            "education_level", "household_size", "occupation", "employment_status",
            "citizenship", "nationality", "religion", "income_bracket", "age_group",
            "language", "native_tongue", "veteran_status", "disability",
        ],
        "types": ["int64", "object", "string", "category"],
        "unique_pct_range": (1.0, 35.0),
        "missing_pct_range": (0.0, 25.0),
        "has_pii_prob": 0.15,
        "pii_types": ["NONE", "PERSON"],
    },
    "Location": {
        "names": [
            "city", "state", "country", "country_code", "zip_code", "postal_code",
            "address", "home_address", "street", "street_address", "latitude", "longitude",
            "lat", "lon", "region", "province", "district", "metro_area", "timezone",
            "delivery_address", "billing_address", "shipping_city",
        ],
        "types": ["object", "string", "float64"],
        "unique_pct_range": (5.0, 85.0),
        "missing_pct_range": (0.0, 15.0),
        "has_pii_prob": 0.65,
        "pii_types": ["LOCATION", "NONE"],
    },
    "Temporal": {
        "names": [
            "created_at", "updated_at", "timestamp", "date", "start_date", "end_date",
            "birth_date", "dob", "expiry_date", "event_time", "login_time", "hire_date",
            "order_date", "payment_date", "deleted_at", "year", "month", "quarter",
            "last_active", "due_date", "scheduled_at",
        ],
        "types": ["datetime64[ns]", "object", "string", "int64"],
        "unique_pct_range": (10.0, 98.0),
        "missing_pct_range": (0.0, 10.0),
        "has_pii_prob": 0.20,
        "pii_types": ["DATE_TIME", "NONE"],
    },
    "Numerical / Measurement": {
        "names": [
            "quantity", "count", "weight", "height", "distance", "temperature",
            "speed", "duration_seconds", "score", "rating", "volume", "width",
            "length", "percentage", "ratio", "units_sold", "page_views", "clicks",
            "step_count", "bpm", "sensor_reading", "packet_loss", "latency_ms",
        ],
        "types": ["int64", "float64"],
        "unique_pct_range": (15.0, 95.0),
        "missing_pct_range": (0.0, 10.0),
        "has_pii_prob": 0.0,
        "pii_types": ["NONE"],
    },
    "Categorical": {
        "names": [
            "status", "category", "type", "tier", "subscription_type", "plan",
            "priority", "segment", "department", "payment_method", "role",
            "membership_level", "is_active", "flag", "stage", "risk_rating",
            "channel", "grade", "product_category", "order_status",
        ],
        "types": ["object", "string", "category", "bool"],
        "unique_pct_range": (0.1, 15.0),
        "missing_pct_range": (0.0, 10.0),
        "has_pii_prob": 0.05,
        "pii_types": ["NONE"],
    },
    "Text": {
        "names": [
            "description", "notes", "comment", "review", "feedback", "summary",
            "message", "body", "article", "bio", "details", "transcript",
            "memo", "instructions", "terms", "abstract", "query", "user_prompt",
        ],
        "types": ["object", "string"],
        "unique_pct_range": (50.0, 100.0),
        "missing_pct_range": (0.0, 30.0),
        "has_pii_prob": 0.25,
        "pii_types": ["NONE", "PERSON", "EMAIL_ADDRESS"],
    },
    "Technical / System": {
        "names": [
            "ip_address", "client_ip", "host", "hostname", "mac_address", "port",
            "endpoint", "url", "user_agent", "os", "browser", "stack_trace",
            "error_code", "http_status", "api_key_hash", "server_name", "request_id",
            "connection_id", "protocol", "dns_record",
        ],
        "types": ["object", "string", "int64"],
        "unique_pct_range": (10.0, 95.0),
        "missing_pct_range": (0.0, 10.0),
        "has_pii_prob": 0.70,
        "pii_types": ["IP_ADDRESS", "URL", "NONE"],
    },
    "Other": {
        "names": [
            "field_1", "custom_col", "unknown", "col_x", "data_val", "misc",
            "temp_var", "extra", "column_99", "var_a", "unspecified", "attribute_3",
            "generic_data", "raw_entry", "val", "x1", "x2", "y",
        ],
        "types": ["object", "float64", "int64"],
        "unique_pct_range": (5.0, 90.0),
        "missing_pct_range": (0.0, 50.0),
        "has_pii_prob": 0.10,
        "pii_types": ["NONE"],
    },
}


def generate_bootstrap_training_data(
    samples_per_domain: int = 150,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Generates a rich, synthetic bootstrap dataset for supervised ML domain classification.
    Produces varied combinations of column names, data types, statistical moments,
    cardinality, PII signals, and data quality failures.
    """
    random.seed(random_state)
    np.random.seed(random_state)

    rows = []

    prefixes = ["user_", "customer_", "client_", "patient_", "employee_", "account_", "global_", "tbl_", "raw_", ""]
    suffixes = ["_val", "_code", "_str", "_data", "_field", "_v2", "_info", "_num", ""]

    for domain, template in DOMAIN_TEMPLATES.items():
        base_names = template["names"]
        types = template["types"]
        u_min, u_max = template["unique_pct_range"]
        m_min, m_max = template["missing_pct_range"]
        pii_prob = template["has_pii_prob"]
        pii_types = template["pii_types"]

        for i in range(samples_per_domain):
            # 1. Column name generation (base + prefix/suffix combinations + slight noise)
            base_name = random.choice(base_names)
            prefix = random.choice(prefixes) if random.random() < 0.4 else ""
            suffix = random.choice(suffixes) if random.random() < 0.3 else ""
            
            # Form clean column name
            col_name = f"{prefix}{base_name}{suffix}".strip("_")
            if not col_name:
                col_name = base_name

            # 2. Data type
            dtype = random.choice(types)
            is_numeric = 1 if dtype in ("int64", "float64") else 0
            is_string = 1 if dtype in ("object", "string") else 0
            is_datetime = 1 if "datetime" in dtype else 0
            is_boolean = 1 if dtype == "bool" else 0
            is_categorical = 1 if dtype == "category" or (is_string and u_max <= 20.0) else 0

            # 3. Cardinality & Missingness
            unique_pct = round(random.uniform(u_min, u_max), 2)
            missing_pct = round(random.uniform(m_min, m_max), 2)
            row_count = random.choice([100, 250, 500, 1000, 5000, 10000, 50000])
            cardinality = max(1, int(row_count * (unique_pct / 100.0)))

            # 4. Statistical Moments (for numeric features or 0.0 for text)
            if is_numeric:
                mean_val = round(random.uniform(10.0, 5000.0), 2)
                std_val = round(mean_val * random.uniform(0.1, 1.5), 2)
                skewness = round(random.uniform(-2.5, 3.5), 2)
                kurtosis = round(random.uniform(-1.0, 8.0), 2)
            else:
                mean_val = 0.0
                std_val = 0.0
                skewness = 0.0
                kurtosis = 0.0

            # 5. String length characteristics
            if is_string:
                avg_str_len = round(random.uniform(3.0, 80.0), 1)
            else:
                avg_str_len = 0.0

            # 6. PII Signals (Phase 6 integration)
            has_pii_flag = 1 if random.random() < pii_prob else 0
            if has_pii_flag:
                pii_entity = random.choice(pii_types)
                if pii_entity == "NONE":
                    has_pii_flag = 0
                    pii_conf = 0.0
                    pii_det_rate = 0.0
                else:
                    pii_conf = round(random.uniform(0.70, 1.0), 2)
                    pii_det_rate = round(random.uniform(0.30, 1.0), 2)
            else:
                pii_entity = "NONE"
                pii_conf = 0.0
                pii_det_rate = 0.0

            # 7. Quality Failures (Phase 5 integration)
            quality_fail_prob = 0.15 if missing_pct > 10.0 or unique_pct < 10.0 else 0.05
            has_quality_issues = 1 if random.random() < quality_fail_prob else 0
            quality_failures = random.randint(1, 3) if has_quality_issues else 0

            rows.append({
                "column_name": col_name,
                "dtype": dtype,
                "is_numeric": is_numeric,
                "is_string": is_string,
                "is_datetime": is_datetime,
                "is_boolean": is_boolean,
                "is_categorical": is_categorical,
                "missing_pct": missing_pct,
                "unique_pct": unique_pct,
                "cardinality": cardinality,
                "row_count": row_count,
                "mean": mean_val,
                "std": std_val,
                "skewness": skewness,
                "kurtosis": kurtosis,
                "avg_str_len": avg_str_len,
                "has_pii": has_pii_flag,
                "pii_entity": pii_entity,
                "pii_confidence": pii_conf,
                "pii_detection_rate": pii_det_rate,
                "quality_failure_count": quality_failures,
                "has_quality_issues": has_quality_issues,
                "target_domain": domain,
            })

    df = pd.DataFrame(rows)
    # Shuffle dataset
    df = df.sample(frac=1.0, random_state=random_state).reset_index(drop=True)
    return df
