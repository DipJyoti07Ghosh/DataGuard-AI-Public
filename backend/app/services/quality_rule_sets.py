"""
DataGuard AI — Predefined Rule Sets for Common Dataset Domains

Each rule set is a list of (template_fn, column, kwargs) tuples.
The pipeline picks the best-matching set based on column overlap.
"""

from typing import Callable, List, Tuple, Any, Dict
from . import quality_rules as rules

RuleSpec = Tuple[Callable, str, Dict[str, Any]]


# ---- Retail transactions ------------------------------------------------
RETAIL_RULES: List[RuleSpec] = [
    (rules.not_be_null,          "customer_email",   {}),
    (rules.not_be_null,          "phone_number",     {}),
    (rules.be_between,           "purchase_amount",  {"min_value": 0, "max_value": 100000}),
    (rules.match_strftime_format,"purchase_date",    {"fmt": "%Y-%m-%d"}),
    (rules.be_of_type,           "purchase_amount",  {"expected_type": "numeric"}),
    (rules.be_in_set,            "category",         {"allowed": [
        "Electronics", "Clothing", "Home", "Grocery", "Toys", "Books", "Sports"
    ], "mostly": 0.95}),
]
RETAIL_COMPOUND = [(["order_id", "customer_id"], rules.compound_columns_unique)]


# ---- Banking transactions -----------------------------------------------
BANKING_RULES: List[RuleSpec] = [
    (rules.not_be_null,  "branch_code",         {}),
    (rules.not_be_null,  "transaction_amount",  {}),
    (rules.be_between,   "transaction_amount",  {"min_value": 0.01, "max_value": 1_000_000}),
    (rules.be_of_type,   "branch_code",         {"expected_type": "string"}),
]
BANKING_TABLE_RULES = [rules.table_row_count_between]  # uses defaults


# ---- Manufacturing sensor logs ------------------------------------------
MANUFACTURING_RULES: List[RuleSpec] = [
    (rules.not_be_null, "pressure_reading", {}),
    (rules.be_between,  "pressure_reading", {"min_value": 0.0, "max_value": 500.0}),
    (rules.not_be_null, "temp_reading",     {}),
    (rules.be_between,  "temp_reading",     {"min_value": -50.0, "max_value": 200.0}),
    (rules.be_of_type,  "vibration_reading",{"expected_type": "numeric"}),
]


# ---- Insurance claims ---------------------------------------------------
INSURANCE_RULES: List[RuleSpec] = [
    (rules.not_be_null,     "claimant_email", {}),
    (rules.be_between,      "claim_amount",   {"min_value": 0, "max_value": 500_000}),
    (rules.not_be_in_set,   "claim_amount",   {"forbidden": [-999, 9999, -1, 0]}),
    (rules.not_be_null,     "adjuster_notes", {}),
    (rules.be_of_type,      "claim_amount",   {"expected_type": "numeric"}),
]


ALL_RULE_SETS = {
    "retail":        (RETAIL_RULES, RETAIL_COMPOUND, []),
    "banking":       (BANKING_RULES, [], BANKING_TABLE_RULES),
    "manufacturing": (MANUFACTURING_RULES, [], []),
    "insurance":     (INSURANCE_RULES, [], []),
}


def pick_best_rule_set(columns: List[str]):
    """
    Pick the rule set whose columns overlap most with the dataset's columns.
    Returns (name, rules, compound_rules, table_rules) or None.
    """
    cols_lower = {c.lower() for c in columns}
    best = None
    best_score = 0

    for name, (rule_specs, compound_specs, table_specs) in ALL_RULE_SETS.items():
        referenced = set()
        for _, col, _ in rule_specs:
            referenced.add(col.lower())
        for cols, _ in compound_specs:
            referenced.update(c.lower() for c in cols)
        score = len(referenced & cols_lower)
        if score > best_score:
            best_score = score
            best = (name, rule_specs, compound_specs, table_specs)

    # Require a minimum overlap so we don't apply retail rules to an unrelated dataset
    if best and best_score >= 2:
        return best
    return None