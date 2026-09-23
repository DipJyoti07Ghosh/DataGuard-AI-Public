"""
DataGuard AI — PII & Sensitive Data Detection Engine (Microsoft Presidio)

Deterministic layered detection — NO LLM, NO Ollama:

  Layer 0  — Identifier column skip (customer_id, order_id, etc.)
  Layer 1  — Non-PII categorical column skip (program, degree, status, etc.)
  Layer 2  — Priority-ordered column-name heuristics
             (EDUCATIONAL_INSTITUTION before PERSON to catch "College Name")
  Layer 3  — Presidio on sample values with SPAN validation
  Layer 4  — Entity value-shape validators
  Layer 5  — Luhn-based credit card detection (independent of Presidio)
  Layer 6  — Heuristic dominance + final filtering

Latency budget: 5-20 seconds for typical datasets (200 rows × 16 cols).
"""

import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
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
            logger.info("Presidio AnalyzerEngine initialized.")
        except Exception as e:
            logger.error(f"Presidio init failed: {e}")
            from presidio_analyzer import AnalyzerEngine
            _analyzer_instance = AnalyzerEngine()
    return _analyzer_instance


# ---------------------------------------------------------------------------
# Column Name Normalization
# ---------------------------------------------------------------------------
def _normalize_col_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


# ---------------------------------------------------------------------------
# Priority-Ordered Column Heuristics
# ---------------------------------------------------------------------------
COLUMN_HEURISTICS: List[Tuple[str, re.Pattern, List[str], float]] = [
    # 1. EDUCATIONAL_INSTITUTION — before PERSON
    (
        "EDUCATIONAL_INSTITUTION",
        re.compile(
            r"^(?:"
            r"college_?name|university_?name|school_?name|"
            r"institute_?name|institution_?name|academy_?name|"
            r"alma_?mater|campus_?name|"
            r"college|university|school|institute|institution|academy|"
            r"educational_?institution"
            r")$"
        ),
        ["ORGANIZATION"],
        0.90,
    ),
    # 2. EMAIL
    (
        "EMAIL_ADDRESS",
        re.compile(r"^(?:[a-z0-9]+_)?(?:e_?mail|mail)(?:_?(?:address|addr|id))?$"),
        ["EMAIL_ADDRESS"],
        0.90,
    ),
    # 3. PHONE
    (
        "PHONE_NUMBER",
        re.compile(
            r"^(?:[a-z0-9]+_)?(?:phone|mobile|cell|telephone|tel|"
            r"contact_?no|contact_?num|msisdn)(?:_?(?:number|no|num))?$"
        ),
        ["PHONE_NUMBER"],
        0.90,
    ),
    # 4. CREDIT_CARD
    (
        "CREDIT_CARD",
        re.compile(
            r"^(?:credit_?|debit_?)?(?:card_?(?:number|no|num|digits)?|"
            r"cc_?(?:num|number)?|pan|primary_?account_?number)"
            r"(?:_?(?:number|no|num))?$"
        ),
        ["CREDIT_CARD"],
        0.90,
    ),
    # 5. US_SSN
    (
        "US_SSN",
        re.compile(
            r"^(?:ssn|social_?security(?:_?(?:number|no))?|"
            r"national_?id|tax_?id|tax_?number)$"
        ),
        ["US_SSN"],
        0.90,
    ),
    # 6. IP
    (
        "IP_ADDRESS",
        re.compile(r"^(?:[a-z0-9]+_)?ip(?:_?(?:address|addr))?$"),
        ["IP_ADDRESS"],
        0.90,
    ),
    # 7. URL
    (
        "URL",
        re.compile(
            r"^(?:[a-z0-9]+_)?(?:url|website|web_?address|link|uri|"
            r"homepage|profile_?url)$"
        ),
        ["URL"],
        0.90,
    ),
    # 8. ORGANIZATION
    (
        "ORGANIZATION",
        re.compile(
            r"^(?:company|org|organization|organisation|employer|"
            r"business|firm|corp|corporation|agency|institution)"
            r"(?:_?name)?$"
        ),
        ["ORGANIZATION"],
        0.85,
    ),
    # 9. LOCATION
    (
        "LOCATION",
        re.compile(
            r"^(?:[a-z0-9]+_)?(?:address|city|state|zip_?code|postal_?code|"
            r"country|province|district|street|location|region|county)$"
        ),
        ["LOCATION"],
        0.85,
    ),
    # 10. DATE_TIME
    (
        "DATE_TIME",
        re.compile(
            r"^(?:[a-z0-9]+_)?(?:at|date|time|timestamp|datetime|dob|"
            r"date_?of_?birth|birth_?date|created_?at|updated_?at|"
            r"modified_?at|deleted_?at|signup_?date|sign_?up_?date|"
            r"register_?date|event_?date|transaction_?date|order_?date|"
            r"payment_?date|invoice_?date)$"
        ),
        ["DATE_TIME"],
        0.85,
    ),
    # 11. PERSON — STRICT patterns (no generic prefix)
    (
        "PERSON",
        re.compile(
            r"^(?:"
            r"name|full_?name|first_?name|last_?name|middle_?name|"
            r"fname|lname|surname|forename|"
            r"username|user_?name|nick_?name|nickname|"
            r"contact_?name|customer_?name|employee_?name|"
            r"patient_?name|author_?name"
            r")$"
        ),
        ["PERSON"],
        0.90,
    ),
]


# ---------------------------------------------------------------------------
# Non-PII Categorical Keyword Blacklist
# ---------------------------------------------------------------------------
_NON_PII_COLUMN_KEYWORDS = re.compile(
    r"(?:^|_)(?:"
    r"program|programme|degree|course|curriculum|subject|stream|branch|"
    r"specialization|specialisation|major|minor|"
    r"qualification|education_?level|academic_?year|academic_?term|"
    r"category|subcategory|sub_?category|"
    r"type|kind|status|state_?code|stage|phase|"
    r"level|tier|grade_?level|class|section|track|"
    r"group|team|department|division|"
    r"mode|method|medium|channel|source|"
    r"description|notes|comment|remark"
    r")(?:_|$)",
    re.IGNORECASE,
)


_SUPPORTED_PRESIDIO_ENTITIES = {
    "EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "IP_ADDRESS",
    "CREDIT_CARD", "US_SSN", "US_PASSPORT", "US_DRIVER_LICENSE",
    "US_BANK_NUMBER", "IBAN_CODE", "CRYPTO", "MEDICAL_LICENSE",
    "LOCATION", "URL", "ORGANIZATION", "DATE_TIME",
}

_UNRELIABLE_ENTITIES = {
    "NRP", "UK_NHS", "UK_NINO", "ES_NIF", "IT_FISCAL_CODE",
    "IT_VAT_CODE", "IT_DRIVER_LICENSE", "IT_PHONE_NUMBER",
    "SG_NRIC_FIN", "AU_ABN", "AU_TFN", "AU_MEDICARE",
    "IN_PAN", "IN_AADHAAR", "IN_VEHICLE_REGISTRATION", "IN_PASSPORT",
}

_MIN_CONFIDENCE_NO_COLUMN_MATCH = {
    "PERSON": 0.70,
    "ORGANIZATION": 0.85,
    "EDUCATIONAL_INSTITUTION": 0.75,
    "LOCATION": 0.65,
    "DATE_TIME": 0.80,
    "URL": 0.65,
    "EMAIL_ADDRESS": 0.55,
    "PHONE_NUMBER": 0.60,
    "IP_ADDRESS": 0.60,
    "CREDIT_CARD": 0.50,
    "US_SSN": 0.50,
    "US_PASSPORT": 0.55,
    "US_DRIVER_LICENSE": 0.55,
    "US_BANK_NUMBER": 0.55,
    "IBAN_CODE": 0.50,
    "CRYPTO": 0.60,
    "MEDICAL_LICENSE": 0.55,
}


def _is_non_pii_column(col_name: str) -> bool:
    return bool(_NON_PII_COLUMN_KEYWORDS.search(_normalize_col_name(col_name)))


def detect_column_name_heuristic(
    column_name: str,
) -> Optional[Tuple[str, List[str], float]]:
    normalized = _normalize_col_name(column_name)
    for canonical, pattern, allowed, conf in COLUMN_HEURISTICS:
        if pattern.match(normalized):
            return canonical, allowed, conf
    return None


# ---------------------------------------------------------------------------
# Identifier & Date helpers
# ---------------------------------------------------------------------------
_IDENTIFIER_SUFFIX_PATTERN = re.compile(
    r"(?:^|_)(?:id|key|code|ref|ref_?no|number|no|num|index|idx|uuid|guid|hash|token)$"
)
_IDENTIFIER_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,32}$")

_DATE_VALUE_PATTERNS = [
    re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"),
    re.compile(r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"),
    re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}[T ]\d{1,2}"),
    re.compile(r"^[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}"),
    re.compile(r"^\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}"),
]


def _is_identifier_column(col_name: str, sample_values: List[str]) -> bool:
    normalized = _normalize_col_name(col_name)
    if _IDENTIFIER_SUFFIX_PATTERN.search(normalized):
        return True
    if not sample_values:
        return False
    sample = sample_values[:50]
    looks_like_id = 0
    considered = 0
    for val in sample:
        s = str(val).strip()
        if not s:
            continue
        considered += 1
        if _IDENTIFIER_VALUE_PATTERN.match(s) and len(s) <= 32:
            if "@" in s or "://" in s:
                continue
            looks_like_id += 1
    if considered == 0:
        return False
    return (looks_like_id / considered) >= 0.8


def _looks_like_true_date(values: List[str]) -> bool:
    if not values:
        return False
    matched = 0
    considered = 0
    for v in values[:30]:
        s = str(v).strip()
        if not s:
            continue
        considered += 1
        for pattern in _DATE_VALUE_PATTERNS:
            if pattern.match(s):
                matched += 1
                break
    if considered == 0:
        return False
    return (matched / considered) >= 0.6


# ---------------------------------------------------------------------------
# Credit Card Detection (Luhn + issuer prefix)
# ---------------------------------------------------------------------------
def _passes_luhn(number: str) -> bool:
    digits = re.sub(r"\D", "", number)
    if not (12 <= len(digits) <= 19):
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


_CARD_PREFIX_PATTERNS = [
    re.compile(r"^4\d{12}(?:\d{3})?(?:\d{3})?$"),
    re.compile(r"^(?:5[1-5]\d{14}|2(?:2[2-9]\d{12}|[3-6]\d{14}|7[01]\d{13}|720\d{12}))$"),
    re.compile(r"^3[47]\d{13}$"),
    re.compile(r"^6(?:011|5\d{2})\d{12}$"),
    re.compile(r"^(?:2131|1800|35\d{3})\d{11}$"),
    re.compile(r"^3(?:0[0-5]|[68]\d)\d{11}$"),
]


def _validate_credit_card(v: str) -> bool:
    digits = re.sub(r"\D", "", v)
    if not (12 <= len(digits) <= 19):
        return False
    if not _passes_luhn(digits):
        return False
    for pattern in _CARD_PREFIX_PATTERNS:
        if pattern.match(digits):
            return True
    return True


# ---------------------------------------------------------------------------
# Entity Value Validators
# ---------------------------------------------------------------------------
_ORG_SUFFIX_REGEX = re.compile(
    r"\b(Inc|Corp|Corporation|Ltd|LLC|Co|GmbH|AG|SA|NV|BV|PLC|LLP|"
    r"Foundation|Hospital|Bank|Group|Technologies|Solutions|Systems|"
    r"Services|Holdings|Partners|Industries|Ventures|Labs|Studio)\b\.?$",
    re.IGNORECASE,
)

_INSTITUTION_KEYWORDS_REGEX = re.compile(
    r"\b("
    r"University|Universität|Université|Universidad|"
    r"College|School|Institute|Institut|Institution|Academy|Polytechnic|"
    r"IIT|NIT|IIIT|BITS|AIIMS|IIM|IISc|IISER|ISI|NIFT|"
    r"MIT|Caltech|Stanford|Harvard|Oxford|Cambridge|Yale|Princeton|"
    r"Columbia|Cornell|Berkeley|"
    r"College of|School of|Institute of"
    r")\b",
    re.IGNORECASE,
)

_ACRONYM_PATTERN = re.compile(
    r"^("
    r"[A-Z](?:\.[A-Z])+\.?"
    r"|[A-Z]{2,6}"
    r"|[A-Z]\.[A-Za-z]{2,}"
    r")$"
)

_DEGREE_NAMES = {
    "b", "ba", "bs", "bsc", "bcom", "bca", "bba", "be", "btech", "barch",
    "m", "ma", "ms", "msc", "mcom", "mca", "mba", "me", "mtech", "march",
    "phd", "ph", "d", "llb", "llm", "md", "ms", "dnb", "mds", "bds",
    "bpharm", "mpharm", "bped", "mped", "bed", "med",
    "diploma", "pgdm", "pgdba",
}


def _validate_email_address(v: str) -> bool:
    if "@" not in v:
        return False
    local, _, domain = v.partition("@")
    return bool(local) and "." in domain


def _validate_phone_number(v: str) -> bool:
    return len(re.sub(r"\D", "", v)) >= 7


def _validate_person(v: str) -> bool:
    v = v.strip()
    if not v:
        return False
    if _INSTITUTION_KEYWORDS_REGEX.search(v):
        return False
    if "." in v and re.search(r"\.[A-Za-z]", v):
        if not re.search(r"\.\s", v):
            return False
    cleaned = v.strip(".,;:\"'()[]{}").strip()
    words = cleaned.split()
    if len(words) >= 2:
        for w in words:
            w_clean = w.strip(".,;:'\"")
            if not w_clean or not w_clean[0].isalpha():
                return False
            if _ACRONYM_PATTERN.match(w_clean):
                return False
            if w_clean.lower() in _DEGREE_NAMES:
                return False
        return True
    if len(words) == 1:
        w_clean = words[0].strip(".,;:'\"")
        if _ACRONYM_PATTERN.match(w_clean):
            return False
        if w_clean.lower() in _DEGREE_NAMES:
            return False
        if len(w_clean) < 4 or not w_clean.isalpha() or not w_clean[0].isupper():
            return False
        return True
    return False


def _validate_organization(v: str) -> bool:
    v = v.strip()
    if not v:
        return False
    if "@" in v or "://" in v:
        return False
    words = v.split()
    if len(words) >= 2:
        if any(not any(c.isalpha() for c in w) for w in words):
            return False
        return True
    if _ORG_SUFFIX_REGEX.search(v):
        return True
    if _INSTITUTION_KEYWORDS_REGEX.search(v):
        return True
    return False


def _validate_educational_institution(v: str) -> bool:
    v = v.strip()
    if not v:
        return False
    if "@" in v or "://" in v:
        return False
    if _INSTITUTION_KEYWORDS_REGEX.search(v):
        return True
    words = v.split()
    if len(words) >= 2:
        capital_words = sum(1 for w in words if w and w[0].isupper())
        if capital_words >= max(2, len(words) // 2):
            return True
    return False


def _validate_location(v: str) -> bool:
    v = v.strip()
    return len(v) >= 3 and any(c.isalpha() for c in v)


def _validate_date_time(v: str) -> bool:
    return bool(re.search(r"\d", v))


def _validate_url(v: str) -> bool:
    return "://" in v or v.lower().startswith("www.")


def _validate_ip_address(v: str) -> bool:
    return bool(re.match(r"^[\d.:a-fA-F]+$", v.strip()))


def _validate_us_ssn(v: str) -> bool:
    return bool(re.match(r"^\d{3}-?\d{2}-?\d{4}$", v.strip()))


_ENTITY_VALUE_VALIDATORS: Dict[str, Callable[[str], bool]] = {
    "EMAIL_ADDRESS": _validate_email_address,
    "PHONE_NUMBER": _validate_phone_number,
    "PERSON": _validate_person,
    "ORGANIZATION": _validate_organization,
    "EDUCATIONAL_INSTITUTION": _validate_educational_institution,
    "LOCATION": _validate_location,
    "DATE_TIME": _validate_date_time,
    "URL": _validate_url,
    "IP_ADDRESS": _validate_ip_address,
    "CREDIT_CARD": _validate_credit_card,
    "US_SSN": _validate_us_ssn,
}


def _validate_entity_value(entity_type: str, value: str) -> bool:
    validator = _ENTITY_VALUE_VALIDATORS.get(entity_type)
    if validator is None:
        return True
    try:
        return validator(value)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Masking Engine
# ---------------------------------------------------------------------------
def mask_pii_value(value: Any, entity_type: str) -> str:
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

    elif entity_type == "IP_ADDRESS":
        if "." in raw_str:
            octets = raw_str.split(".")
            if len(octets) == 4:
                return f"{octets[0]}.{octets[1]}.***.***"
        return "192.168.***.***"

    elif entity_type == "PERSON":
        words = raw_str.split()
        if words:
            return " ".join(
                (w[0] + "*" * min(len(w) - 1, 3)) if len(w) > 1 else (w[0] + "*")
                for w in words
            )
        return "J*** D**"

    elif entity_type in ("ORGANIZATION", "EDUCATIONAL_INSTITUTION"):
        if len(raw_str) <= 2:
            return raw_str[0] + "***" if raw_str else "***"
        return raw_str[0] + "******" + (raw_str[-1] if len(raw_str) > 3 else "")

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

    elif entity_type == "DATE_TIME":
        digits = re.sub(r"\D", "", raw_str)
        if len(digits) >= 4:
            return digits[:2] + "*" * (len(digits) - 4) + digits[-2:]
        return "*" * len(raw_str)

    if len(raw_str) <= 3:
        return "*" * len(raw_str)
    return raw_str[0] + "*" * min(len(raw_str) - 2, 6) + raw_str[-1]


# ---------------------------------------------------------------------------
# Risk Level Engine
# ---------------------------------------------------------------------------
HIGH_RISK_ENTITIES = {
    "CREDIT_CARD", "US_SSN", "IBAN_CODE", "CRYPTO",
    "US_PASSPORT", "US_DRIVER_LICENSE", "US_BANK_NUMBER", "MEDICAL_LICENSE",
}
MEDIUM_RISK_ENTITIES = {
    "EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON",
    "IP_ADDRESS", "LOCATION", "PASSPORT",
    "ORGANIZATION", "EDUCATIONAL_INSTITUTION",
}


def calculate_risk_level(entity_type: str, confidence: float, detection_rate: float) -> str:
    entity = entity_type.upper()
    if entity in HIGH_RISK_ENTITIES:
        return "HIGH" if (confidence >= 0.4 or detection_rate >= 0.2) else "MEDIUM"
    if entity in MEDIUM_RISK_ENTITIES:
        return "MEDIUM" if (confidence >= 0.5 or detection_rate >= 0.2) else "LOW"
    if confidence >= 0.8 and detection_rate >= 0.4:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Core Scanner — NO OLLAMA
# ---------------------------------------------------------------------------
def scan_dataframe_for_pii(
    df: pd.DataFrame,
    sample_size: int = 40,      # smaller sample = faster
    max_char_len: int = 500,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Deterministic PII scan. No LLM. Fast.
    """
    analyzer = get_analyzer_engine()
    total_columns = len(df.columns)
    findings_list: List[Dict[str, Any]] = []
    scanned_columns_info = []

    entity_counter: Dict[str, int] = {}
    risk_counter: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    pii_columns_set: Set[str] = set()

    # Entities we ask Presidio about
    _PRESIDIO_ENTITIES = [
        "EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "IP_ADDRESS",
        "CREDIT_CARD", "US_SSN", "US_PASSPORT", "US_DRIVER_LICENSE",
        "US_BANK_NUMBER", "IBAN_CODE", "CRYPTO", "MEDICAL_LICENSE",
        "LOCATION", "URL", "ORGANIZATION", "DATE_TIME",
    ]

    for col in df.columns:
        col_name = str(col)

        heuristic = detect_column_name_heuristic(col_name)
        heuristic_entity = heuristic[0] if heuristic else None
        allowed_entities = heuristic[1] if heuristic else None
        heuristic_conf = heuristic[2] if heuristic else None

        series = df[col].dropna()
        non_null_count = len(series)
        _pre_sample = series.head(50).astype(str).tolist() if non_null_count > 0 else []

        # Layer 1: Non-PII categorical skip
        if heuristic_entity is None and _is_non_pii_column(col_name):
            scanned_columns_info.append({
                "column_name": col_name, "has_pii": False, "sampled": 0,
                "skipped_reason": "non_pii_categorical",
            })
            continue

        # Layer 0: Identifier skip
        if heuristic_entity is None and non_null_count > 0:
            if _is_identifier_column(col_name, _pre_sample):
                scanned_columns_info.append({
                    "column_name": col_name, "has_pii": False, "sampled": 0,
                    "skipped_reason": "identifier_like_column",
                })
                continue

        # Skip numeric columns without heuristic
        if heuristic_entity is None and pd.api.types.is_numeric_dtype(series):
            scanned_columns_info.append({
                "column_name": col_name, "has_pii": False, "sampled": 0,
                "skipped_reason": "numeric_no_heuristic",
            })
            continue

        # Empty column
        if non_null_count == 0:
            if heuristic_entity:
                risk = calculate_risk_level(heuristic_entity, 0.65, 0.0)
                findings_list.append({
                    "column_name": col_name,
                    "entity_type": heuristic_entity,
                    "detection_source": "COLUMN_NAME",
                    "confidence": heuristic_conf or 0.65,
                    "sampled_count": 0, "detected_count": 0, "detection_rate": 0.0,
                    "risk_level": risk,
                    "masked_preview": "[Column Name Signal]",
                    "details": {"heuristic_match": True, "notes": "Empty column."},
                })
                pii_columns_set.add(col_name)
                entity_counter[heuristic_entity] = entity_counter.get(heuristic_entity, 0) + 1
                risk_counter[risk] = risk_counter.get(risk, 0) + 1

            scanned_columns_info.append({
                "column_name": col_name, "has_pii": col_name in pii_columns_set, "sampled": 0,
            })
            continue

        # Sample
        if non_null_count > sample_size:
            step = max(1, non_null_count // sample_size)
            sample_series = series.iloc[::step].head(sample_size)
        else:
            sample_series = series
        sampled_count = len(sample_series)

        # Prepare values
        values_list = []
        for raw_val in sample_series:
            s = str(raw_val)[:max_char_len].strip()
            if s:
                values_list.append(s)

        # BATCH Presidio analyze
        presidio_batch_results: List[List[Any]] = []
        try:
            if hasattr(analyzer, "analyze_batch"):
                presidio_batch_results = analyzer.analyze_batch(
                    texts=values_list,
                    language="en",
                    entities=_PRESIDIO_ENTITIES,
                )
            else:
                presidio_batch_results = [
                    analyzer.analyze(text=v, language="en", entities=_PRESIDIO_ENTITIES)
                    for v in values_list
                ]
        except Exception:
            presidio_batch_results = [
                analyzer.analyze(text=v, language="en", entities=_PRESIDIO_ENTITIES)
                for v in values_list
            ]

        col_entity_scores: Dict[str, List[float]] = {}
        col_entity_examples: Dict[str, str] = {}

        for val_str, presidio_results in zip(values_list, presidio_batch_results):
            seen_in_val = set()
            for res in presidio_results:
                ent_type = res.entity_type
                if ent_type in _UNRELIABLE_ENTITIES:
                    continue
                if ent_type not in _SUPPORTED_PRESIDIO_ENTITIES:
                    continue
                if allowed_entities is not None and ent_type not in allowed_entities:
                    continue
                if res.score < 0.5:
                    continue

                span_text = val_str[res.start:res.end] if res.start is not None else val_str
                if ent_type == "DATE_TIME" and not _looks_like_true_date(_pre_sample):
                    continue
                if not _validate_entity_value(ent_type, span_text):
                    continue

                if ent_type not in seen_in_val:
                    seen_in_val.add(ent_type)
                    col_entity_scores.setdefault(ent_type, []).append(res.score)
                    col_entity_examples.setdefault(ent_type, span_text)

        # Regex credit card fallback
        if "CREDIT_CARD" not in col_entity_scores:
            cc_matches = 0
            cc_example = ""
            for raw_val in sample_series:
                val_str = str(raw_val).strip()
                if _validate_credit_card(val_str):
                    cc_matches += 1
                    if not cc_example:
                        cc_example = val_str
            if cc_matches > 0 and cc_matches / max(sampled_count, 1) >= 0.30:
                col_entity_scores["CREDIT_CARD"] = [0.9] * cc_matches
                col_entity_examples["CREDIT_CARD"] = cc_example

        # Institution hint
        if heuristic_entity == "EDUCATIONAL_INSTITUTION":
            inst_matches = 0
            inst_example = ""
            for raw_val in sample_series:
                val_str = str(raw_val).strip()
                if _validate_educational_institution(val_str):
                    inst_matches += 1
                    if not inst_example:
                        inst_example = val_str
            if inst_matches > 0:
                existing = col_entity_scores.get("EDUCATIONAL_INSTITUTION", [])
                col_entity_scores["EDUCATIONAL_INSTITUTION"] = existing + [0.90] * inst_matches
                col_entity_examples.setdefault("EDUCATIONAL_INSTITUTION", inst_example)

        column_had_detection = False

        for ent_type, scores in col_entity_scores.items():
            detected_count = len(scores)
            detection_rate = round(detected_count / sampled_count, 3) if sampled_count > 0 else 0.0
            avg_score = sum(scores) / detected_count if detected_count > 0 else 0.0

            if heuristic_entity == ent_type:
                detection_source = "COLUMN_AND_VALUE"
                combined_conf = min(1.0, round(avg_score * 0.7 + 0.35, 3))
            else:
                detection_source = "VALUE"
                combined_conf = round(avg_score, 3)

            min_conf = _MIN_CONFIDENCE_NO_COLUMN_MATCH.get(ent_type, 0.7)
            if detection_source == "VALUE" and combined_conf < min_conf:
                continue
            if detection_source == "VALUE" and detection_rate < 0.30:
                continue
            if detection_rate < 0.05 and combined_conf < 0.7:
                continue
            if (
                ent_type == "DATE_TIME"
                and detection_source == "VALUE"
                and not _looks_like_true_date(_pre_sample)
            ):
                continue
            if (
                heuristic_entity is not None
                and ent_type != heuristic_entity
                and heuristic_conf and heuristic_conf >= 0.85
            ):
                continue

            risk = calculate_risk_level(ent_type, combined_conf, detection_rate)
            raw_ex = col_entity_examples.get(ent_type, "")
            masked_ex = mask_pii_value(raw_ex, ent_type)

            findings_list.append({
                "column_name": col_name,
                "entity_type": ent_type,
                "detection_source": detection_source,
                "confidence": combined_conf,
                "sampled_count": sampled_count,
                "detected_count": detected_count,
                "detection_rate": detection_rate,
                "risk_level": risk,
                "masked_preview": masked_ex,
                "details": {
                    "presidio_avg_score": round(avg_score, 3),
                    "heuristic_matched": (heuristic_entity == ent_type),
                    "sample_size": sampled_count,
                    "matched_sample_count": detected_count,
                },
            })
            column_had_detection = True
            pii_columns_set.add(col_name)
            entity_counter[ent_type] = entity_counter.get(ent_type, 0) + 1
            risk_counter[risk] = risk_counter.get(risk, 0) + 1

        # Fallback: heuristic only
        if not column_had_detection and heuristic_entity:
            risk = calculate_risk_level(heuristic_entity, heuristic_conf or 0.65, 0.0)
            sample_val = str(sample_series.iloc[0]) if len(sample_series) > 0 else ""
            masked_example = mask_pii_value(sample_val, heuristic_entity)
            findings_list.append({
                "column_name": col_name,
                "entity_type": heuristic_entity,
                "detection_source": "COLUMN_NAME",
                "confidence": heuristic_conf or 0.65,
                "sampled_count": sampled_count,
                "detected_count": 0,
                "detection_rate": 0.0,
                "risk_level": risk,
                "masked_preview": masked_example,
                "details": {"heuristic_match": True, "notes": "Heuristic only."},
            })
            pii_columns_set.add(col_name)
            entity_counter[heuristic_entity] = entity_counter.get(heuristic_entity, 0) + 1
            risk_counter[risk] = risk_counter.get(risk, 0) + 1

        scanned_columns_info.append({
            "column_name": col_name,
            "has_pii": col_name in pii_columns_set,
            "sampled": sampled_count,
        })

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
# Persistence
# ---------------------------------------------------------------------------
def generate_pii_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
    force_recompute: bool = False,
    sample_size: int = 40,
) -> PIIScanResult:
    stmt = (
        select(DatasetVersion)
        .join(Dataset)
        .where(DatasetVersion.id == version_id, Dataset.id == dataset_id)
    )
    version = db.scalar(stmt)
    if not version:
        raise ValueError(f"DatasetVersion '{version_id}' not found.")

    existing = db.scalar(
        select(PIIScanResult).where(PIIScanResult.dataset_version_id == version.id)
    )
    if existing and not force_recompute:
        logger.info(f"Returning cached PIIScanResult for '{version.dataset.name}' V{version.version_number}")
        return existing

    upload_dir = Path(settings.upload_path)
    file_path = upload_dir / version.stored_filename
    if not file_path.exists():
        raise FileNotFoundError(f"Stored file '{version.stored_filename}' not found.")

    file_content = file_path.read_bytes()
    if version.file_type == "csv":
        df, _, _ = parse_csv(file_content)
    elif version.file_type == "xlsx":
        df, _ = parse_excel(file_content)
    else:
        raise ValueError(f"Unsupported file type '{version.file_type}'.")

    logger.info(f"Executing PII scan for '{version.dataset.name}' V{version.version_number}...")

    findings_data, summary_data = scan_dataframe_for_pii(df=df, sample_size=sample_size)

    if existing:
        db.delete(existing)
        db.flush()

    scan_entity = PIIScanResult(
        dataset_version_id=version.id,
        scanned_at=datetime.now(timezone.utc),
        total_columns_scanned=summary_data["total_columns_scanned"],
        pii_columns_count=summary_data["pii_columns_count"],
        total_findings=summary_data["total_findings"],
        summary=summary_data,
    )
    db.add(scan_entity)
    db.flush()

    for fd in findings_data:
        db.add(PIIFinding(
            scan_id=scan_entity.id,
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
        ))

    try:
        db.commit()
        db.refresh(scan_entity)
        logger.info(
            f"Saved PIIScanResult (id={scan_entity.id}) with {len(findings_data)} findings for V{version.version_number}"
        )
        return scan_entity
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(PIIScanResult).where(PIIScanResult.dataset_version_id == version.id)
        )
        if existing:
            return existing
        raise


def get_pii_for_version(
    db: Session,
    dataset_id: UUID,
    version_id: UUID,
) -> Optional[PIIScanResult]:
    stmt = (
        select(PIIScanResult)
        .join(DatasetVersion)
        .join(Dataset)
        .where(DatasetVersion.id == version_id, Dataset.id == dataset_id)
    )
    return db.scalar(stmt)