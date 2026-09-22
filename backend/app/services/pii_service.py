"""
DataGuard AI — PII & Sensitive Data Detection Engine (Microsoft Presidio)

Performs automated sensitive data discovery across DatasetVersions using:
1. Column-name heuristic signal detection
2. Bounded sample value extraction and Presidio Analyzer recognition
3. Evidence combination (column + value) with confidence calculation
4. Strict, irreversible masking before persistence and API responses
5. Transparent risk-level classification (HIGH / MEDIUM / LOW)
"""

import re
import math
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.dataset import Dataset, DatasetVersion
from app.models.pii import PIIScanResult, PIIFinding
from app.services.ingestion import parse_csv, parse_excel

logger = logging.getLogger("dataguard.services.pii")

# ---------------------------------------------------------------------------
# Presidio Engine Lazy Singleton
# ---------------------------------------------------------------------------
_analyzer_instance = None


def get_analyzer_engine():
    """
    Returns a configured singleton instance of Presidio AnalyzerEngine.
    Uses the lightweight 'en_core_web_sm' spaCy model.
    """
    global _analyzer_instance
    if _analyzer_instance is None:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            provider = NlpEngineProvider(
                nlp_configuration={
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
                }
            )
            nlp_engine = provider.create_engine()
            _analyzer_instance = AnalyzerEngine(nlp_engine=nlp_engine)
            logger.info("Presidio AnalyzerEngine initialized successfully with en_core_web_sm.")
        except Exception as e:
            logger.error(f"Failed to initialize Presidio AnalyzerEngine with spaCy model: {e}")
            # Fallback to standard AnalyzerEngine if custom provider encounters an issue
            try:
                from presidio_analyzer import AnalyzerEngine
                _analyzer_instance = AnalyzerEngine()
                logger.info("Presidio AnalyzerEngine initialized with default fallback.")
            except Exception as ex:
                logger.critical(f"Presidio AnalyzerEngine is unavailable: {ex}")
                raise RuntimeError(f"Presidio AnalyzerEngine is not available: {ex}")

    return _analyzer_instance


# ---------------------------------------------------------------------------
# Column Name Heuristic Patterns & Contextual Guardrails
# ---------------------------------------------------------------------------
COLUMN_HEURISTICS: List[Tuple[str, re.Pattern]] = [
    (
        "EMAIL_ADDRESS",
        re.compile(
            r"^(?:user_?|customer_?|client_?|contact_?|work_?|personal_?)?email(?:_address|_id)?$|^(?:e_?mail)$",
            re.IGNORECASE,
        ),
    ),
    (
        "PHONE_NUMBER",
        re.compile(
            r"^(?:user_?|customer_?|client_?|contact_?|work_?|home_?|cell_?)?(?:phone|mobile|cell|telephone|tel|contact_no|contact_num)(?:_number|_no)?$",
            re.IGNORECASE,
        ),
    ),
    (
        "PERSON",
        re.compile(
            r"^(?:user_?|customer_?|client_?|author_?|patient_?|employee_?|member_?|contact_?)?(?:name|full_name|first_name|last_name|fname|lname|surname|username|user_name)$",
            re.IGNORECASE,
        ),
    ),
    (
        "IP_ADDRESS",
        re.compile(
            r"^(?:client_?|host_?|remote_?|server_?|source_?|dest_?|user_?)?ip(?:_address|_addr)?$",
            re.IGNORECASE,
        ),
    ),
    (
        "CREDIT_CARD",
        re.compile(
            r"^(?:credit_?card|debit_?card|card_?number|card_?no|cc_?num|cc_?number|card_?digits|pan|cvv|cvc)$",
            re.IGNORECASE,
        ),
    ),
    (
        "US_SSN",
        re.compile(
            r"^(?:ssn|social_?security|social_?security_?number|national_?id|tax_?id|tax_?number)$",
            re.IGNORECASE,
        ),
    ),
    (
        "US_DRIVER_LICENSE",
        re.compile(
            r"^(?:user_?|customer_?|client_?|driver_?|member_?|employee_?)?(?:driver_?license|drivers_?license|driving_?license|dl|dl_?number|dl_?no|license_?number|license_?no)(?:_num|_number|_no)?$",
            re.IGNORECASE,
        ),
    ),
    (
        "ORGANIZATION",
        re.compile(
            r"^(?:user_?|customer_?|client_?|member_?|employee_?)?(?:company|organization|org|employer|vendor|business|corporation|firm|agency|institution|carrier)(?:_name|_title)?$",
            re.IGNORECASE,
        ),
    ),
    (
        "DATE_TIME",
        re.compile(
            r"^(?:user_?|customer_?|patient_?|client_?|member_?|employee_?)?(?:dob|date_?of_?birth|birth_?date|birthdate|born_?date|birth_?dt|date_?of_?death|deceased_?date)$",
            re.IGNORECASE,
        ),
    ),
    (
        "LOCATION",
        re.compile(
            r"^(?:home_?|street_?|work_?|billing_?|shipping_?|residential_?)?address$|^(?:city|state|zip_?code|postal_?code|country|province|street|location)$",
            re.IGNORECASE,
        ),
    ),
    (
        "URL",
        re.compile(
            r"^(?:url|website|web_?address|link|uri|homepage|profile_?url)$",
            re.IGNORECASE,
        ),
    ),
]

SENSITIVE_DATE_PATTERN = re.compile(
    r"^(?:user_?|customer_?|patient_?|client_?|member_?|employee_?)?(?:dob|date_?of_?birth|birth_?date|birthdate|born_?date|birth_?dt|date_?of_?death|deceased_?date)$",
    re.IGNORECASE,
)

OPERATIONAL_DATE_PATTERN = re.compile(
    r"(?:effective_?to|effective_?from|created|updated|modified|timestamp|transaction_?date|purchase_?date|start_?date|end_?date|expiry|expiration|due_?date|ship_?date|order_?date|event_?date|run_?date|effective_?date|report_?date)",
    re.IGNORECASE,
)

BUSINESS_DIMENSION_PATTERN = re.compile(
    r"^(?:id|.*_id|.*_num|.*_number|.*_code|customer|policy|claim|account|order|transaction|invoice|product|plan|category|tier|type|status|state_code|clv|lifetime_value|customer_lifetime_value|premium|amount|balance|rate|score|cost|price|revenue|sales|quantity|volume|count|coverage|marital|response)$",
    re.IGNORECASE,
)

METRIC_OR_TECHNICAL_PATTERN = re.compile(
    r"(?:pressure|ratio|read|write|call|rate|load|speed|temp|temperature|voltage|current|freq|frequency|utilization|usage|metric|stat|stats|counter|duration|latency|delay|throughput|bandwidth|packet|error|loss|offset|delta|avg|mean|median|min|max|std|var|score|weight|height|depth|width|dim|val|value|index|pct|percent|percentage|cpu|gpu|mem|memory|disk|io|sys|net|network|swap|cache|buffer|rpm|power|energy|consumption|quota|capacity|allocation|qps|tps|iops|latency_ms|duration_ms|time_taken|elapsed|runtime)",
    re.IGNORECASE,
)

DIMENSION_OR_TYPE_PATTERN = re.compile(
    r"(?:.*_type|.*_category|.*_class|.*_mode|.*_status|.*_state|.*_kind|.*_group|.*_tier|.*_tier_name|.*_segment|.*_flag|.*_code|type|category|mode|status|class|kind|tier|segment|flag|label|workload|protocol|method|algorithm|format|env|environment|stage|phase|action|event|device|service|job|task|node|cluster)",
    re.IGNORECASE,
)

DRIVER_LICENSE_COLUMN_PATTERN = re.compile(
    r"^(?:user_?|customer_?|client_?|driver_?|member_?|employee_?)?(?:driver_?license|drivers_?license|driving_?license|dl|dl_?number|dl_?no|license_?number|license_?no)(?:_num|_number|_no)?$",
    re.IGNORECASE,
)

ORGANIZATION_COLUMN_PATTERN = re.compile(
    r"^(?:user_?|customer_?|client_?|member_?|employee_?)?(?:company|organization|org|employer|vendor|business|corporation|firm|agency|institution|carrier)(?:_name|_title)?$",
    re.IGNORECASE,
)


def detect_column_name_heuristic(column_name: str) -> Optional[str]:
    """Check if a column name matches known PII patterns."""
    clean_name = column_name.strip().lower()
    for entity_type, pattern in COLUMN_HEURISTICS:
        if pattern.match(clean_name):
            return entity_type
    return None


# ---------------------------------------------------------------------------
# Strict Masking Engine (NEVER leaks raw PII)
# ---------------------------------------------------------------------------
def mask_pii_value(value: Any, entity_type: str) -> str:
    """
    Produce a safe masked sample representation of a sensitive value.
    This function is executed strictly before persistence and API responses.
    """
    if value is None:
        return "[MASKED]"

    raw_str = str(value).strip()
    if not raw_str:
        return ""

    if entity_type == "EMAIL_ADDRESS":
        if "@" in raw_str:
            parts = raw_str.split("@", 1)
            local, domain = parts[0], parts[1]
            masked_local = (local[0] + "***") if len(local) > 0 else "***"
            if "." in domain:
                dom_parts = domain.split(".", 1)
                dom_name, ext = dom_parts[0], dom_parts[1]
                masked_dom = (dom_name[0] + "******." + ext) if len(dom_name) > 0 else "******." + ext
            else:
                masked_dom = (domain[0] + "******") if len(domain) > 0 else "******"
            return f"{masked_local}@{masked_dom}"
        return "j***@e******.com"

    elif entity_type in ("PHONE_NUMBER", "US_BANK_NUMBER"):
        digits_only = re.sub(r"\D", "", raw_str)
        if len(digits_only) >= 4:
            return "*" * min(len(digits_only) - 4, 6) + digits_only[-4:]
        return "******" + (raw_str[-2:] if len(raw_str) >= 2 else "")

    elif entity_type == "CREDIT_CARD":
        digits_only = re.sub(r"\D", "", raw_str)
        if len(digits_only) >= 4:
            return "****-****-****-" + digits_only[-4:]
        return "****-****-****-3456"

    elif entity_type == "US_SSN":
        digits_only = re.sub(r"\D", "", raw_str)
        if len(digits_only) >= 4:
            return "***-**-" + digits_only[-4:]
        return "***-**-6789"

    elif entity_type == "US_DRIVER_LICENSE":
        if len(raw_str) >= 4:
            return raw_str[0] + "*" * min(len(raw_str) - 2, 6) + raw_str[-1]
        return "D*****1"

    elif entity_type == "DATE_TIME":
        if re.search(r"\d{4}", raw_str):
            return re.sub(r"\d{4}", "****", raw_str)
        return "****-**-**"

    elif entity_type == "ORGANIZATION":
        words = raw_str.split()
        if words:
            return (words[0][0] + "*** Org") if len(words[0]) > 0 else "[MASKED_ORG]"
        return "[MASKED_ORG]"

    elif entity_type == "IP_ADDRESS":
        if "." in raw_str:
            octets = raw_str.split(".")
            if len(octets) == 4:
                return f"{octets[0]}.{octets[1]}.***.***"
        elif ":" in raw_str:
            parts = raw_str.split(":")
            if len(parts) > 2:
                return f"{parts[0]}:{parts[1]}:****:****"
        return "192.168.***.***"

    elif entity_type == "PERSON":
        words = raw_str.split()
        if words:
            masked_words = []
            for w in words:
                if len(w) > 1:
                    masked_words.append(w[0] + "*" * min(len(w) - 1, 3))
                else:
                    masked_words.append(w[0] + "*")
            return " ".join(masked_words)
        return "J*** D**"

    elif entity_type == "LOCATION":
        words = raw_str.split()
        if len(words) > 1:
            return words[0] + " " + " ".join(w[0] + "***" for w in words[1:])
        elif len(raw_str) > 2:
            return raw_str[:2] + "***"
        return "[MASKED_LOCATION]"

    elif entity_type == "URL":
        if "://" in raw_str:
            proto, rest = raw_str.split("://", 1)
            host = rest.split("/", 1)[0]
            if "." in host:
                hparts = host.split(".", 1)
                return f"{proto}://{hparts[0][0]}******.{hparts[1]}/***"
            return f"{proto}://{host[0]}******/***"
        return "https://w******.com/***"

    # Generic string masking
    if len(raw_str) <= 3:
        return "*" * len(raw_str)
    return raw_str[0] + "*" * min(len(raw_str) - 2, 6) + raw_str[-1]


# ---------------------------------------------------------------------------
# Transparent Risk Level Engine
# ---------------------------------------------------------------------------
HIGH_RISK_ENTITIES = {
    "CREDIT_CARD",
    "US_SSN",
    "IBAN_CODE",
    "CRYPTO",
    "US_PASSPORT",
    "US_DRIVER_LICENSE",
    "US_BANK_NUMBER",
    "MEDICAL_LICENSE",
}

MEDIUM_RISK_ENTITIES = {
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "PERSON",
    "IP_ADDRESS",
    "LOCATION",
    "PASSPORT",
}


def calculate_risk_level(entity_type: str, confidence: float, detection_rate: float) -> str:
    """
    Transparent application-level risk classification:
    - HIGH: Direct financial identifiers, government SSNs/Passports, or critical secrets
    - MEDIUM: Personal contact details (emails, phone, IP, names, location) with standard confidence
    - LOW: Weak/ambiguous detections, low detection rates, or non-critical entities (URL, DATE_TIME)
    """
    entity = entity_type.upper()

    if entity in HIGH_RISK_ENTITIES:
        if confidence >= 0.4 or detection_rate >= 0.2:
            return "HIGH"
        return "MEDIUM"

    if entity in MEDIUM_RISK_ENTITIES:
        if confidence >= 0.5 or detection_rate >= 0.2:
            return "MEDIUM"
        return "LOW"

    # Default / URL / generic entities
    if confidence >= 0.8 and detection_rate >= 0.4:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Contextual Profile & Entity Validation Layer
# ---------------------------------------------------------------------------
def _analyze_column_sample_profile(sample_series: pd.Series) -> Dict[str, Any]:
    """Profile non-null sample values to inform entity validation."""
    total = len(sample_series)
    if total == 0:
        return {"is_mostly_numeric": False, "has_decimals": False, "samples": []}

    num_count = 0
    decimal_count = 0
    str_samples: List[str] = []

    for val in sample_series:
        s = str(val).strip()
        str_samples.append(s)
        try:
            float(s)
            num_count += 1
            if "." in s and not s.endswith(".0"):
                decimal_count += 1
        except (ValueError, TypeError):
            pass

    is_mostly_numeric = (num_count / total) >= 0.75
    has_decimals = (decimal_count / max(1, num_count)) >= 0.15 if num_count > 0 else False

    return {
        "is_mostly_numeric": is_mostly_numeric,
        "has_decimals": has_decimals,
        "samples": str_samples,
    }


def validate_entity_finding(
    ent_type: str,
    scores: List[float],
    sampled_count: int,
    col_name: str,
    heuristic_entity: Optional[str],
    col_profile: Dict[str, Any],
    examples: List[str],
) -> Tuple[bool, float, str]:
    """
    Evaluates multi-dimensional evidence for a detected entity type:
    - column context (heuristic, business dimensions, metrics, telemetry, operational date patterns)
    - value structure (data type, delimiters, decimals, Luhn / format checks)
    - recognizer scores & match rate consistency

    Returns (is_valid, calibrated_confidence, detection_source).
    """
    detected_count = len(scores)
    if detected_count == 0 or sampled_count == 0:
        return False, 0.0, "NONE"

    detection_rate = detected_count / sampled_count
    avg_presidio_score = sum(scores) / detected_count
    is_numeric = col_profile.get("is_mostly_numeric", False)
    has_decimals = col_profile.get("has_decimals", False)

    clean_col = col_name.strip().lower()
    is_biz_col = bool(BUSINESS_DIMENSION_PATTERN.match(clean_col))
    is_metric_col = bool(METRIC_OR_TECHNICAL_PATTERN.search(clean_col))
    is_dim_col = bool(DIMENSION_OR_TYPE_PATTERN.search(clean_col))
    is_non_pii_col = is_biz_col or is_metric_col or is_dim_col
    is_sens_date = bool(SENSITIVE_DATE_PATTERN.match(clean_col))
    is_oper_date = bool(OPERATIONAL_DATE_PATTERN.search(clean_col))
    is_dl_col = bool(DRIVER_LICENSE_COLUMN_PATTERN.match(clean_col))
    is_org_col = bool(ORGANIZATION_COLUMN_PATTERN.match(clean_col))

    # Determine base detection source
    if heuristic_entity == ent_type:
        detection_source = "COLUMN_AND_VALUE"
        confidence = min(1.0, round(avg_presidio_score * 0.7 + 0.35, 3))
    else:
        detection_source = "VALUE"
        confidence = round(avg_presidio_score, 3)

    # 1. CREDIT_CARD
    if ent_type == "CREDIT_CARD":
        # If values contain decimal points (floats, metrics, CPU/IO ratios), they are never credit cards
        if has_decimals or any("." in s for s in examples if re.search(r"\d+\.\d+", s)):
            return False, 0.0, "NONE"
        # If column is telemetry, metric, ratio, or technical system column without card heuristic
        if (is_non_pii_col or is_numeric) and heuristic_entity != "CREDIT_CARD":
            return False, 0.0, "NONE"
        if heuristic_entity == "CREDIT_CARD":
            return True, confidence, detection_source
        # Generic column: require reasonable consistency and genuine standalone 13-19 digit card tokens
        if detection_rate < 0.20 or avg_presidio_score < 0.75:
            return False, 0.0, "NONE"
        return True, confidence, detection_source

    # 2. US_DRIVER_LICENSE
    if ent_type == "US_DRIVER_LICENSE":
        if is_dl_col or heuristic_entity == "US_DRIVER_LICENSE":
            return True, confidence, detection_source
        if heuristic_entity is not None and heuristic_entity != "US_DRIVER_LICENSE":
            return False, 0.0, "NONE"
        # Suppress weak Presidio regex on business IDs, metrics, telemetry, or numeric columns
        if is_non_pii_col or is_numeric or has_decimals:
            return False, 0.0, "NONE"
        if avg_presidio_score <= 0.5 or detection_rate < 0.2:
            return False, 0.0, "NONE"
        return True, confidence, detection_source

    # 3. DATE_TIME
    if ent_type == "DATE_TIME":
        if is_sens_date or heuristic_entity == "DATE_TIME":
            return True, confidence, detection_source
        if heuristic_entity is not None and heuristic_entity != "DATE_TIME":
            return False, 0.0, "NONE"
        # Operational dates and business/system metrics are not sensitive PII
        if is_oper_date or is_non_pii_col or is_numeric or has_decimals:
            return False, 0.0, "NONE"
        return False, 0.0, "NONE"

    # 4. ORGANIZATION
    if ent_type == "ORGANIZATION":
        if is_org_col or heuristic_entity == "ORGANIZATION":
            return True, confidence, detection_source
        if heuristic_entity is not None and heuristic_entity != "ORGANIZATION":
            return False, 0.0, "NONE"
        if any("@" in s for s in examples):
            return False, 0.0, "NONE"
        # Suppress spaCy token matches on metric, dimension, numeric, or system columns
        if is_non_pii_col or is_numeric or has_decimals or is_oper_date or is_sens_date:
            return False, 0.0, "NONE"
        if avg_presidio_score < 0.8 or detection_rate < 0.2:
            return False, 0.0, "NONE"
        return True, confidence, detection_source

    # 5. PHONE_NUMBER
    if ent_type == "PHONE_NUMBER":
        if has_decimals or is_oper_date:
            return False, 0.0, "NONE"
        if heuristic_entity == "PHONE_NUMBER":
            return True, confidence, detection_source
        if heuristic_entity is not None and heuristic_entity not in ("PHONE_NUMBER", None):
            return False, 0.0, "NONE"
        # In metric, technical, or business columns without phone context, require explicit phone formatting
        formatted_phone_regex = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
        has_phone_format = any(formatted_phone_regex.search(s) for s in examples)
        if is_non_pii_col and not has_phone_format:
            return False, 0.0, "NONE"
        if not has_phone_format and (is_numeric or detection_rate < 0.15):
            return False, 0.0, "NONE"
        return True, confidence, detection_source

    # 6. PERSON
    if ent_type == "PERSON":
        if is_numeric or has_decimals:
            return False, 0.0, "NONE"
        if heuristic_entity == "PERSON":
            return True, confidence, detection_source
        if heuristic_entity is not None and heuristic_entity != "PERSON":
            return False, 0.0, "NONE"
        if is_non_pii_col:
            return False, 0.0, "NONE"
        if avg_presidio_score < 0.6 or detection_rate < 0.15:
            return False, 0.0, "NONE"
        return True, confidence, detection_source

    # 7. EMAIL_ADDRESS
    if ent_type == "EMAIL_ADDRESS":
        has_email_pattern = any(
            re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", s) for s in examples
        )
        if not has_email_pattern and heuristic_entity != "EMAIL_ADDRESS":
            return False, 0.0, "NONE"
        return True, confidence, detection_source

    # 8. US_SSN
    if ent_type == "US_SSN":
        if has_decimals:
            return False, 0.0, "NONE"
        if heuristic_entity == "US_SSN":
            return True, confidence, detection_source
        if (is_non_pii_col or is_numeric) and not any(re.search(r"^\d{3}-\d{2}-\d{4}$", s) for s in examples):
            return False, 0.0, "NONE"
        return True, confidence, detection_source

    # 9. IP_ADDRESS
    if ent_type == "IP_ADDRESS":
        if has_decimals or is_metric_col:
            if heuristic_entity != "IP_ADDRESS":
                return False, 0.0, "NONE"
        # Validate IPv4 format
        ipv4_regex = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
        has_valid_ip = any(ipv4_regex.match(s) or ":" in s for s in examples)
        if not has_valid_ip and heuristic_entity != "IP_ADDRESS":
            return False, 0.0, "NONE"
        return True, confidence, detection_source

    # 10. LOCATION
    if ent_type == "LOCATION":
        if (is_numeric or has_decimals or is_non_pii_col) and heuristic_entity != "LOCATION":
            return False, 0.0, "NONE"
        return True, confidence, detection_source

    # 11. URL
    if ent_type == "URL":
        if any("@" in s for s in examples) and not any(re.search(r"(?:https?://|www\.)", s) for s in examples):
            return False, 0.0, "NONE"
        if is_numeric or has_decimals or is_non_pii_col:
            if heuristic_entity != "URL":
                return False, 0.0, "NONE"
        return True, confidence, detection_source

    # 12. Generic / Regional / Government IDs (NRP, PASSPORT, BANK_NUMBER, etc.)
    if is_non_pii_col and heuristic_entity != ent_type:
        return False, 0.0, "NONE"
    if is_numeric and ent_type not in ("US_BANK_NUMBER", "IBAN_CODE", "CREDIT_CARD", "US_SSN"):
        return False, 0.0, "NONE"
    if detection_rate < 0.20 and avg_presidio_score < 0.85 and heuristic_entity != ent_type:
        return False, 0.0, "NONE"

    return True, confidence, detection_source


# ---------------------------------------------------------------------------
# PII Scanner Core Logic
# ---------------------------------------------------------------------------
def scan_dataframe_for_pii(
    df: pd.DataFrame,
    sample_size: int = 100,
    max_char_len: int = 500,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Inspects columns and bounded value samples of a pandas DataFrame for PII.
    Returns:
      - List of finding dictionaries ready for PIIFinding persistence
      - Summary dictionary ready for PIIScanResult persistence
    """
    analyzer = get_analyzer_engine()
    total_columns = len(df.columns)
    findings_list: List[Dict[str, Any]] = []
    scanned_columns_info = []

    entity_counter: Dict[str, int] = {}
    risk_counter: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    pii_columns_set = set()

    for col in df.columns:
        col_name = str(col)
        heuristic_entity = detect_column_name_heuristic(col_name)

        # Extract bounded non-null sample
        series = df[col].dropna()
        non_null_count = len(series)

        if non_null_count == 0:
            # Empty column — check if column name itself suggests PII
            if heuristic_entity:
                risk = calculate_risk_level(heuristic_entity, 0.65, 0.0)
                finding = {
                    "column_name": col_name,
                    "entity_type": heuristic_entity,
                    "detection_source": "COLUMN_NAME",
                    "confidence": 0.65,
                    "sampled_count": 0,
                    "detected_count": 0,
                    "detection_rate": 0.0,
                    "risk_level": risk,
                    "masked_preview": "[Column Name Signal]",
                    "details": {
                        "heuristic_match": True,
                        "notes": "Detected exclusively from column name pattern; column had no non-null values.",
                    },
                }
                findings_list.append(finding)
                pii_columns_set.add(col_name)
                entity_counter[heuristic_entity] = entity_counter.get(heuristic_entity, 0) + 1
                risk_counter[risk] = risk_counter.get(risk, 0) + 1

            scanned_columns_info.append({
                "column_name": col_name,
                "has_pii": col_name in pii_columns_set,
                "sampled": 0,
            })
            continue

        # Deterministic sample extraction
        if non_null_count > sample_size:
            step = max(1, non_null_count // sample_size)
            sample_series = series.iloc[::step].head(sample_size)
        else:
            sample_series = series

        sampled_count = len(sample_series)
        col_profile = _analyze_column_sample_profile(sample_series)

        # Run Presidio Analyzer on string representations
        col_entity_scores: Dict[str, List[float]] = {}
        col_entity_examples: Dict[str, List[str]] = {}

        for raw_val in sample_series:
            val_str = str(raw_val)[:max_char_len].strip()
            if not val_str:
                continue

            try:
                presidio_results = analyzer.analyze(text=val_str, language="en")
                seen_in_val = set()
                for res in presidio_results:
                    ent_type = res.entity_type
                    if res.score < 0.3:
                        continue

                    if ent_type not in seen_in_val:
                        seen_in_val.add(ent_type)
                        col_entity_scores.setdefault(ent_type, []).append(res.score)
                        if ent_type not in col_entity_examples:
                            col_entity_examples[ent_type] = []
                        if len(col_entity_examples[ent_type]) < 5:
                            col_entity_examples[ent_type].append(val_str)
            except Exception as e:
                logger.warning(f"Presidio error on column '{col_name}': {e}")
                continue

        # Aggregate and validate findings for this column
        column_had_detection = False

        for ent_type, scores in col_entity_scores.items():
            examples = col_entity_examples.get(ent_type, [])
            is_valid, combined_conf, detection_source = validate_entity_finding(
                ent_type=ent_type,
                scores=scores,
                sampled_count=sampled_count,
                col_name=col_name,
                heuristic_entity=heuristic_entity,
                col_profile=col_profile,
                examples=examples,
            )

            if not is_valid:
                continue

            detected_count = len(scores)
            detection_rate = round(detected_count / sampled_count, 3) if sampled_count > 0 else 0.0
            avg_presidio_score = sum(scores) / detected_count if detected_count > 0 else 0.0

            risk = calculate_risk_level(ent_type, combined_conf, detection_rate)
            raw_sample_example = examples[0] if examples else ""
            masked_example = mask_pii_value(raw_sample_example, ent_type)

            finding = {
                "column_name": col_name,
                "entity_type": ent_type,
                "detection_source": detection_source,
                "confidence": combined_conf,
                "sampled_count": sampled_count,
                "detected_count": detected_count,
                "detection_rate": detection_rate,
                "risk_level": risk,
                "masked_preview": masked_example,
                "details": {
                    "presidio_avg_score": round(avg_presidio_score, 3),
                    "heuristic_matched": (heuristic_entity == ent_type),
                    "sample_size": sampled_count,
                    "matched_sample_count": detected_count,
                },
            }
            findings_list.append(finding)
            column_had_detection = True
            pii_columns_set.add(col_name)
            entity_counter[ent_type] = entity_counter.get(ent_type, 0) + 1
            risk_counter[risk] = risk_counter.get(risk, 0) + 1

        # If values did not produce confirmed Presidio detections but column name strongly matches sensitive PII
        if not column_had_detection and heuristic_entity:
            risk = calculate_risk_level(heuristic_entity, 0.65, 0.0)
            sample_val = str(sample_series.iloc[0]) if len(sample_series) > 0 else ""
            masked_example = mask_pii_value(sample_val, heuristic_entity)

            finding = {
                "column_name": col_name,
                "entity_type": heuristic_entity,
                "detection_source": "COLUMN_NAME",
                "confidence": 0.65,
                "sampled_count": sampled_count,
                "detected_count": 0,
                "detection_rate": 0.0,
                "risk_level": risk,
                "masked_preview": masked_example,
                "details": {
                    "heuristic_match": True,
                    "notes": "Column name matched sensitive pattern; sample values had ambiguous or masked formatting.",
                },
            }
            findings_list.append(finding)
            pii_columns_set.add(col_name)
            entity_counter[heuristic_entity] = entity_counter.get(heuristic_entity, 0) + 1
            risk_counter[risk] = risk_counter.get(risk, 0) + 1

        scanned_columns_info.append({
            "column_name": col_name,
            "has_pii": col_name in pii_columns_set,
            "sampled": sampled_count,
        })

    # Overall dataset risk
    if risk_counter["HIGH"] > 0:
        overall_risk = "HIGH"
    elif risk_counter["MEDIUM"] > 0:
        overall_risk = "MEDIUM"
    elif risk_counter["LOW"] > 0:
        overall_risk = "LOW"
    else:
        overall_risk = "NONE"

    summary_data = {
        "overall_risk": overall_risk,
        "risk_breakdown": risk_counter,
        "entity_breakdown": entity_counter,
        "total_columns_scanned": total_columns,
        "pii_columns_count": len(pii_columns_set),
        "total_findings": len(findings_list),
        "has_pii": len(pii_columns_set) > 0,
        "scanned_columns": scanned_columns_info,
    }

    return findings_list, summary_data


# ---------------------------------------------------------------------------
# Database Service Workflows
# ---------------------------------------------------------------------------
def generate_pii_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = False,
    sample_size: int = 100,
) -> PIIScanResult:
    """
    Performs PII discovery for the specified DatasetVersion and persists results in PostgreSQL.
    If cached scan exists and force_recompute is False, returns existing scan result.
    """
    # 1. Fetch Dataset & DatasetVersion
    stmt = (
        select(DatasetVersion)
        .join(Dataset)
        .where(
            DatasetVersion.id == version_id,
            Dataset.id == dataset_id,
        )
    )
    version = db.scalar(stmt)
    if not version:
        raise ValueError(
            f"DatasetVersion with id='{version_id}' not found for dataset='{dataset_id}'."
        )

    # 2. Check for existing cached scan
    stmt_scan = select(PIIScanResult).where(
        PIIScanResult.dataset_version_id == version.id
    )
    existing_scan = db.scalar(stmt_scan)

    if existing_scan and not force_recompute:
        logger.info(
            f"Returning cached PIIScanResult for '{version.dataset.name}' V{version.version_number}"
        )
        return existing_scan

    # 3. Load dataset file
    upload_dir = Path(settings.upload_path)
    file_path = upload_dir / version.stored_filename
    if not file_path.exists():
        raise FileNotFoundError(
            f"Stored file '{version.stored_filename}' for version V{version.version_number} not found on disk."
        )

    file_content = file_path.read_bytes()
    if version.file_type == "csv":
        df, _, _ = parse_csv(file_content)
    elif version.file_type == "xlsx":
        df, _ = parse_excel(file_content)
    else:
        raise ValueError(f"Unsupported file type '{version.file_type}' for PII detection.")

    logger.info(
        f"Executing Presidio PII scan for '{version.dataset.name}' V{version.version_number} (cols={len(df.columns)})..."
    )

    # 4. Perform PII Scan
    findings_data, summary_data = scan_dataframe_for_pii(df=df, sample_size=sample_size)

    # 5. Persist to PostgreSQL gracefully without unique constraint race conditions
    if existing_scan:
        existing_scan.scanned_at = datetime.now(timezone.utc)
        existing_scan.total_columns_scanned = summary_data["total_columns_scanned"]
        existing_scan.pii_columns_count = summary_data["pii_columns_count"]
        existing_scan.total_findings = summary_data["total_findings"]
        existing_scan.summary = summary_data
        existing_scan.findings.clear()
        scan_entity = existing_scan
    else:
        scan_entity = PIIScanResult(
            dataset_version_id=version.id,
            scanned_at=datetime.now(timezone.utc),
            total_columns_scanned=summary_data["total_columns_scanned"],
            pii_columns_count=summary_data["pii_columns_count"],
            total_findings=summary_data["total_findings"],
            summary=summary_data,
        )
        db.add(scan_entity)

    for fd in findings_data:
        finding_entity = PIIFinding(
            column_name=fd["column_name"],
            entity_type=fd["entity_type"],
            detection_source=fd["detection_source"],
            confidence=fd["confidence"],
            sampled_count=fd["sampled_count"],
            detected_count=fd["detected_count"],
            detection_rate=fd["detection_rate"],
            risk_level=fd["risk_level"],
            masked_preview=fd["masked_preview"],
            details=fd["details"],
        )
        scan_entity.findings.append(finding_entity)

    try:
        db.commit()
        db.refresh(scan_entity)
        logger.info(
            f"Saved PIIScanResult (id={scan_entity.id}) with {len(findings_data)} findings for V{version.version_number}"
        )
        return scan_entity
    except IntegrityError:
        db.rollback()
        logger.info(f"Concurrent PII scan write detected for version {version.id}; fetching existing record.")
        existing = db.scalar(
            select(PIIScanResult).where(PIIScanResult.dataset_version_id == version.id)
        )
        if existing:
            if force_recompute:
                try:
                    existing.scanned_at = datetime.now(timezone.utc)
                    existing.total_columns_scanned = summary_data["total_columns_scanned"]
                    existing.pii_columns_count = summary_data["pii_columns_count"]
                    existing.total_findings = summary_data["total_findings"]
                    existing.summary = summary_data
                    existing.findings.clear()
                    for fd in findings_data:
                        finding_entity = PIIFinding(
                            column_name=fd["column_name"],
                            entity_type=fd["entity_type"],
                            detection_source=fd["detection_source"],
                            confidence=fd["confidence"],
                            sampled_count=fd["sampled_count"],
                            detected_count=fd["detected_count"],
                            detection_rate=fd["detection_rate"],
                            risk_level=fd["risk_level"],
                            masked_preview=fd["masked_preview"],
                            details=fd["details"],
                        )
                        existing.findings.append(finding_entity)
                    db.commit()
                    db.refresh(existing)
                except Exception:
                    db.rollback()
            return existing
        raise


def get_pii_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
) -> Optional[PIIScanResult]:
    """
    Retrieve existing PII scan result for a DatasetVersion.
    """
    stmt = (
        select(PIIScanResult)
        .join(DatasetVersion)
        .join(Dataset)
        .where(
            DatasetVersion.id == version_id,
            Dataset.id == dataset_id,
        )
    )
    return db.scalar(stmt)
