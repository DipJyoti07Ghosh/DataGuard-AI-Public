"""
DataGuard AI — Phase 11 Knowledge Document Builder

Transforms authoritative Phase 4–10 stored analysis results into normalized,
privacy-scrubbed, deterministic, bounded semantic chunks ready for vector embedding.

STRICT PRIVACY RULES:
- Never includes raw cell values or raw text snippets.
- Removes Great Expectations 'observed values'.
- Omits raw PII strings (emails, phones, SSNs, credit cards).
- Omits raw anomaly outlier entries.
- Phrases Phase 9 remediation strictly as suggestions, never completed actions.
- Bounded document size (<= 1500 chars).
- Strict deterministic sorting across all entities.
"""

import hashlib
import re
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

# Regex to scrub any accidental raw email, phone, or SSN patterns
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CC_RE = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")


def sanitize_text(text: str) -> str:
    """Scrub potential raw PII patterns from text."""
    if not text:
        return ""
    s = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    s = _PHONE_RE.sub("[REDACTED_PHONE]", s)
    s = _SSN_RE.sub("[REDACTED_SSN]", s)
    s = _CC_RE.sub("[REDACTED_CARD]", s)
    return s.strip()


def compute_content_hash(content: str) -> str:
    """Generate deterministic SHA-256 hash of normalized content."""
    norm = " ".join(content.strip().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Phase 4 Profiling Document Builders
# ---------------------------------------------------------------------------
def build_profiling_documents(
    dataset_id: UUID,
    version_id: UUID,
    version_number: int,
    dataset_name: str,
    profiling_result: Any,
) -> List[Dict[str, Any]]:
    """Build dataset overview and column profiling knowledge documents."""
    docs = []
    if not profiling_result:
        return docs

    res_id = getattr(profiling_result, "id", None)
    upd_at = getattr(profiling_result, "created_at", None) or datetime.utcnow()
    profiles = getattr(profiling_result, "column_profiles", {}) or {}
    row_count = getattr(profiling_result, "row_count", 0)
    col_count = getattr(profiling_result, "column_count", len(profiles))
    missing_cells = getattr(profiling_result, "missing_cells_count", 0)
    dup_rows = getattr(profiling_result, "duplicate_rows_count", 0)

    # 1. Dataset Overview Chunk
    sorted_col_names = sorted(list(profiles.keys()))
    overview_content = (
        f"### Dataset Overview: {dataset_name} (Version V{version_number})\n"
        f"- Total Records: {row_count:,} rows\n"
        f"- Total Columns: {col_count} columns\n"
        f"- Total Missing Cells: {missing_cells:,}\n"
        f"- Duplicate Rows: {dup_rows:,}\n"
        f"- Schema Columns: {', '.join(sorted_col_names[:30])}\n"
    )
    docs.append({
        "dataset_id": dataset_id,
        "version_id": version_id,
        "comparison_id": None,
        "source_result_id": res_id,
        "source_result_updated_at": upd_at,
        "source_phase": "PHASE_4_PROFILING",
        "document_type": "dataset_overview",
        "logical_document_id": f"{dataset_id}:{version_id}:PHASE_4_PROFILING:dataset_overview:overview",
        "title": f"Overview of {dataset_name} V{version_number}",
        "content": sanitize_text(overview_content[:1500]),
        "doc_metadata": {
            "dataset_name": dataset_name,
            "version_number": version_number,
            "row_count": row_count,
            "column_count": col_count,
            "missing_cells_count": missing_cells,
        },
    })

    # 2. Per-Column Profiling Chunks
    for col_name in sorted_col_names:
        prof = profiles[col_name]
        dtype = prof.get("dtype", "unknown")
        type_cat = prof.get("type_category", "unknown")
        miss_pct = prof.get("missing_percentage", 0.0)
        uniq_pct = prof.get("unique_percentage", 0.0)
        miss_cnt = prof.get("missing_count", 0)
        uniq_cnt = prof.get("unique_count", 0)

        col_lines = [
            f"### Profiling for Column: '{col_name}' (Dataset: {dataset_name} V{version_number})",
            f"- Data Type: {dtype} ({type_cat})",
            f"- Missingness: {miss_cnt:,} values ({miss_pct:.2f}%)",
            f"- Uniqueness: {uniq_cnt:,} distinct values ({uniq_pct:.2f}%)",
        ]

        if type_cat == "numeric":
            min_v = prof.get("min")
            max_v = prof.get("max")
            mean_v = prof.get("mean")
            std_v = prof.get("std")
            mean_str = f"{mean_v:.2f}" if mean_v is not None else "N/A"
            std_str = f"{std_v:.2f}" if std_v is not None else "N/A"
            col_lines.append(f"- Statistics: min={min_v}, max={max_v}, mean={mean_str}, std={std_str}")
        elif type_cat in ["categorical", "text"]:
            top_cats = prof.get("top_categories", {})
            if isinstance(top_cats, dict) and top_cats:
                bounded_cats = sorted([str(c) for c in list(top_cats.keys())[:10]])
                col_lines.append(f"- Top Categories: {', '.join(bounded_cats)}")

        col_content = "\n".join(col_lines)
        docs.append({
            "dataset_id": dataset_id,
            "version_id": version_id,
            "comparison_id": None,
            "source_result_id": res_id,
            "source_result_updated_at": upd_at,
            "source_phase": "PHASE_4_PROFILING",
            "document_type": "profiling_column",
            "logical_document_id": f"{dataset_id}:{version_id}:PHASE_4_PROFILING:profiling_column:{col_name}",
            "title": f"Column Profile: {col_name} (V{version_number})",
            "content": sanitize_text(col_content[:1500]),
            "doc_metadata": {
                "column_name": col_name,
                "data_type": dtype,
                "type_category": type_cat,
                "missing_percentage": miss_pct,
                "unique_percentage": uniq_pct,
            },
        })

    return docs


# ---------------------------------------------------------------------------
# Phase 5 Quality Document Builders
# ---------------------------------------------------------------------------
def build_quality_documents(
    dataset_id: UUID,
    version_id: UUID,
    version_number: int,
    dataset_name: str,
    quality_result: Any,
) -> List[Dict[str, Any]]:
    """Build quality summary and failed expectation rule documents without raw observed values."""
    docs = []
    if not quality_result:
        return docs

    res_id = getattr(quality_result, "id", None)
    upd_at = getattr(quality_result, "created_at", None) or datetime.utcnow()
    q_score = getattr(quality_result, "overall_score", 0.0)
    q_grade = getattr(quality_result, "grade", "UNKNOWN")
    passed_cnt = getattr(quality_result, "passed_expectations_count", 0)
    failed_cnt = getattr(quality_result, "failed_expectations_count", 0)
    expectations = getattr(quality_result, "expectations", []) or []

    # 1. Quality Summary Chunk
    q_summary_content = (
        f"### Data Quality Summary: {dataset_name} (Version V{version_number})\n"
        f"- Overall Quality Score: {q_score:.1f}/100 (Grade: {q_grade})\n"
        f"- Total Rules Evaluated: {passed_cnt + failed_cnt}\n"
        f"- Passed Rules: {passed_cnt}\n"
        f"- Failed Rules: {failed_cnt}\n"
    )
    docs.append({
        "dataset_id": dataset_id,
        "version_id": version_id,
        "comparison_id": None,
        "source_result_id": res_id,
        "source_result_updated_at": upd_at,
        "source_phase": "PHASE_5_QUALITY",
        "document_type": "quality_summary",
        "logical_document_id": f"{dataset_id}:{version_id}:PHASE_5_QUALITY:quality_summary:summary",
        "title": f"Quality Summary: {dataset_name} V{version_number}",
        "content": sanitize_text(q_summary_content[:1500]),
        "doc_metadata": {
            "overall_score": q_score,
            "grade": q_grade,
            "passed_rules": passed_cnt,
            "failed_rules": failed_cnt,
        },
    })

    # 2. Failed Quality Rules Grouped by Column
    failed_exp = [e for e in expectations if not getattr(e, "success", True)]
    by_col: Dict[str, List[Any]] = {}
    for exp in failed_exp:
        col = getattr(exp, "column_name", None) or "_dataset_level_"
        by_col.setdefault(col, []).append(exp)

    for col_name in sorted(by_col.keys()):
        exp_list = sorted(
            by_col[col_name],
            key=lambda x: (getattr(x, "expectation_type", ""), getattr(x, "failure_message", ""))
        )
        lines = [
            f"### Quality Rule Failures: Column '{col_name}' (Dataset: {dataset_name} V{version_number})",
            f"- Total Violations: {len(exp_list)} failed expectation rule(s)",
        ]
        # Bound to top 10 failures per column
        for exp in exp_list[:10]:
            rule_type = getattr(exp, "expectation_type", "Quality Rule")
            msg = getattr(exp, "failure_message", None) or "Rule expectation failed"
            clean_msg = sanitize_text(msg)
            lines.append(f"- Rule [{rule_type}]: {clean_msg}")

        q_col_content = "\n".join(lines)
        docs.append({
            "dataset_id": dataset_id,
            "version_id": version_id,
            "comparison_id": None,
            "source_result_id": res_id,
            "source_result_updated_at": upd_at,
            "source_phase": "PHASE_5_QUALITY",
            "document_type": "quality_issue",
            "logical_document_id": f"{dataset_id}:{version_id}:PHASE_5_QUALITY:quality_issue:{col_name}",
            "title": f"Quality Violations: {col_name} (V{version_number})",
            "content": sanitize_text(q_col_content[:1500]),
            "doc_metadata": {
                "column_name": col_name,
                "failed_rules_count": len(exp_list),
            },
        })

    return docs


# ---------------------------------------------------------------------------
# Phase 6 PII Document Builders
# ---------------------------------------------------------------------------
def build_pii_documents(
    dataset_id: UUID,
    version_id: UUID,
    version_number: int,
    dataset_name: str,
    pii_result: Any,
) -> List[Dict[str, Any]]:
    """Build PII summary and column privacy exposure documents without any raw PII."""
    docs = []
    if not pii_result:
        return docs

    res_id = getattr(pii_result, "id", None)
    upd_at = getattr(pii_result, "created_at", None) or datetime.utcnow()
    findings = getattr(pii_result, "findings", []) or []

    # 1. PII Summary Chunk
    all_ents = sorted(list(set(getattr(f, "entity_type", "") for f in findings if getattr(f, "entity_type", ""))))
    pii_cols = sorted(list(set(getattr(f, "column_name", "") for f in findings if getattr(f, "column_name", ""))))
    pii_summary_content = (
        f"### Sensitive Data & Privacy Scan Summary: {dataset_name} (Version V{version_number})\n"
        f"- Total PII Findings: {len(findings)}\n"
        f"- Columns with PII: {len(pii_cols)} ({', '.join(pii_cols) if pii_cols else 'None'})\n"
        f"- Detected Entity Types: {', '.join(all_ents) if all_ents else 'None detected'}\n"
    )
    docs.append({
        "dataset_id": dataset_id,
        "version_id": version_id,
        "comparison_id": None,
        "source_result_id": res_id,
        "source_result_updated_at": upd_at,
        "source_phase": "PHASE_6_PII",
        "document_type": "pii_summary",
        "logical_document_id": f"{dataset_id}:{version_id}:PHASE_6_PII:pii_summary:summary",
        "title": f"Privacy Scan Summary: {dataset_name} V{version_number}",
        "content": sanitize_text(pii_summary_content[:1500]),
        "doc_metadata": {
            "total_findings": len(findings),
            "pii_columns_count": len(pii_cols),
            "entity_types": all_ents,
        },
    })

    # 2. Per-Column PII Findings (Strictly entity types and exposure, ZERO raw values)
    by_col: Dict[str, List[Any]] = {}
    for f in findings:
        col = getattr(f, "column_name", "unknown")
        by_col.setdefault(col, []).append(f)

    for col_name in sorted(by_col.keys()):
        f_list = by_col[col_name]
        col_ents = sorted(list(set(getattr(f, "entity_type", "") for f in f_list)))
        risk_lvl = max([getattr(f, "risk_level", "LOW") for f in f_list], default="LOW")
        col_content = (
            f"### Sensitive Column Privacy Exposure: Column '{col_name}' (Dataset: {dataset_name} V{version_number})\n"
            f"- Privacy Exposure Level: {risk_lvl}\n"
            f"- Detected Entity Types: {', '.join(col_ents)}\n"
            f"- Total Detected Findings in Column: {len(f_list)}\n"
            f"- Data Protection Guidance: Ensure column is redacted, masked, or pseudonymized before sharing.\n"
        )
        docs.append({
            "dataset_id": dataset_id,
            "version_id": version_id,
            "comparison_id": None,
            "source_result_id": res_id,
            "source_result_updated_at": upd_at,
            "source_phase": "PHASE_6_PII",
            "document_type": "pii_column",
            "logical_document_id": f"{dataset_id}:{version_id}:PHASE_6_PII:pii_column:{col_name}",
            "title": f"PII Exposure: {col_name} ({risk_lvl})",
            "content": sanitize_text(col_content[:1500]),
            "doc_metadata": {
                "column_name": col_name,
                "risk_level": risk_lvl,
                "entity_types": col_ents,
                "findings_count": len(f_list),
            },
        })

    return docs


# ---------------------------------------------------------------------------
# Phase 7 ML Risk Document Builders
# ---------------------------------------------------------------------------
def build_risk_documents(
    dataset_id: UUID,
    version_id: UUID,
    version_number: int,
    dataset_name: str,
    risk_predictions: List[Any],
) -> List[Dict[str, Any]]:
    """Build ML risk summary and column semantic risk documents."""
    docs = []
    if not risk_predictions:
        return docs

    sorted_risks = sorted(risk_predictions, key=lambda x: getattr(x, "column_name", ""))
    upd_at = getattr(sorted_risks[0], "created_at", None) or datetime.utcnow()
    high_risks = [r for r in sorted_risks if getattr(r, "risk_level", "").upper() in ["HIGH", "CRITICAL"]]
    med_risks = [r for r in sorted_risks if getattr(r, "risk_level", "").upper() == "MEDIUM"]

    # 1. Risk Summary Chunk
    mean_score = sum(getattr(r, "risk_score", 0.0) for r in sorted_risks) / len(sorted_risks)
    risk_summary_content = (
        f"### Machine Learning Semantic Risk Summary: {dataset_name} (Version V{version_number})\n"
        f"- Mean Column Risk Index: {mean_score:.1f}/100\n"
        f"- Total Evaluated Columns: {len(sorted_risks)}\n"
        f"- High/Critical Risk Columns: {len(high_risks)} ({', '.join(getattr(r, 'column_name', '') for r in high_risks) if high_risks else 'None'})\n"
        f"- Medium Risk Columns: {len(med_risks)}\n"
    )
    docs.append({
        "dataset_id": dataset_id,
        "version_id": version_id,
        "comparison_id": None,
        "source_result_id": getattr(sorted_risks[0], "id", None),
        "source_result_updated_at": upd_at,
        "source_phase": "PHASE_7_RISK",
        "document_type": "risk_summary",
        "logical_document_id": f"{dataset_id}:{version_id}:PHASE_7_RISK:risk_summary:summary",
        "title": f"ML Risk Summary: {dataset_name} V{version_number}",
        "content": sanitize_text(risk_summary_content[:1500]),
        "doc_metadata": {
            "mean_risk_score": round(mean_score, 1),
            "high_risk_columns_count": len(high_risks),
        },
    })

    # 2. Per-Column Risk Predictions
    for r in sorted_risks:
        col = getattr(r, "column_name", "unknown")
        domain = getattr(r, "predicted_domain", "General")
        score = getattr(r, "risk_score", 0.0)
        level = (getattr(r, "risk_level", "LOW") or "LOW").upper()
        col_content = (
            f"### Semantic Classification & Risk: Column '{col}' (Dataset: {dataset_name} V{version_number})\n"
            f"- Predicted Semantic Domain: '{domain}'\n"
            f"- Risk Classification: {level} (Risk Score: {score:.1f}/100)\n"
            f"- Governance Implication: Column contains domain attributes requiring appropriate handling controls.\n"
        )
        docs.append({
            "dataset_id": dataset_id,
            "version_id": version_id,
            "comparison_id": None,
            "source_result_id": getattr(r, "id", None),
            "source_result_updated_at": getattr(r, "created_at", upd_at),
            "source_phase": "PHASE_7_RISK",
            "document_type": "risk_column",
            "logical_document_id": f"{dataset_id}:{version_id}:PHASE_7_RISK:risk_column:{col}",
            "title": f"ML Risk: {col} ({level})",
            "content": sanitize_text(col_content[:1500]),
            "doc_metadata": {
                "column_name": col,
                "predicted_domain": domain,
                "risk_score": score,
                "risk_level": level,
            },
        })

    return docs


# ---------------------------------------------------------------------------
# Phase 8 Anomaly Document Builders
# ---------------------------------------------------------------------------
def build_anomaly_documents(
    dataset_id: UUID,
    version_id: UUID,
    version_number: int,
    dataset_name: str,
    anomaly_result: Any,
) -> List[Dict[str, Any]]:
    """Build anomaly summary and column outlier concentration documents without raw outlier rows."""
    docs = []
    if not anomaly_result:
        return docs

    res_id = getattr(anomaly_result, "id", None)
    upd_at = getattr(anomaly_result, "created_at", None) or datetime.utcnow()
    a_score = getattr(anomaly_result, "dataset_anomaly_score", 0.0)
    findings = getattr(anomaly_result, "findings", []) or []
    sorted_findings = sorted(findings, key=lambda x: getattr(x, "column_name", ""))

    # 1. Anomaly Summary Chunk
    anom_cols = [getattr(f, "column_name", "") for f in sorted_findings if getattr(f, "severity", "").upper() in ["HIGH", "CRITICAL"]]
    anom_summary_content = (
        f"### Multi-Method Outlier & Anomaly Summary: {dataset_name} (Version V{version_number})\n"
        f"- Dataset Anomaly Index: {a_score:.1f}/100\n"
        f"- Anomalous Columns Detected: {len(sorted_findings)}\n"
        f"- High Outlier Concentration Columns: {', '.join(anom_cols) if anom_cols else 'None'}\n"
        f"- Detection Ensemble: IsolationForest + IQR + Z-Score\n"
    )
    docs.append({
        "dataset_id": dataset_id,
        "version_id": version_id,
        "comparison_id": None,
        "source_result_id": res_id,
        "source_result_updated_at": upd_at,
        "source_phase": "PHASE_8_ANOMALY",
        "document_type": "anomaly_summary",
        "logical_document_id": f"{dataset_id}:{version_id}:PHASE_8_ANOMALY:anomaly_summary:summary",
        "title": f"Anomaly Summary: {dataset_name} V{version_number}",
        "content": sanitize_text(anom_summary_content[:1500]),
        "doc_metadata": {
            "dataset_anomaly_score": a_score,
            "anomalous_columns_count": len(sorted_findings),
        },
    })

    # 2. Per-Column Anomaly Findings
    for f in sorted_findings:
        col = getattr(f, "column_name", "unknown")
        sev = (getattr(f, "severity", "LOW") or "LOW").upper()
        rate = getattr(f, "anomaly_rate", 0.0)
        methods = getattr(f, "detection_methods", ["Ensemble"])
        col_content = (
            f"### Outlier Concentration: Column '{col}' (Dataset: {dataset_name} V{version_number})\n"
            f"- Anomaly Severity: {sev} (Outlier Rate: {rate:.2f}%)\n"
            f"- Triggered Detectors: {', '.join(sorted(methods)) if isinstance(methods, list) else str(methods)}\n"
            f"- Finding Note: Column contains statistical outlier concentrations outside standard expectation intervals.\n"
        )
        docs.append({
            "dataset_id": dataset_id,
            "version_id": version_id,
            "comparison_id": None,
            "source_result_id": res_id,
            "source_result_updated_at": upd_at,
            "source_phase": "PHASE_8_ANOMALY",
            "document_type": "anomaly_column",
            "logical_document_id": f"{dataset_id}:{version_id}:PHASE_8_ANOMALY:anomaly_column:{col}",
            "title": f"Outliers in {col} ({sev})",
            "content": sanitize_text(col_content[:1500]),
            "doc_metadata": {
                "column_name": col,
                "severity": sev,
                "anomaly_rate": rate,
            },
        })

    return docs


# ---------------------------------------------------------------------------
# Phase 9 Health & Remediation Document Builders
# ---------------------------------------------------------------------------
def build_health_documents(
    dataset_id: UUID,
    version_id: UUID,
    version_number: int,
    dataset_name: str,
    health_result: Any,
) -> List[Dict[str, Any]]:
    """Build holistic health summary and prioritized issue remediation documents."""
    docs = []
    if not health_result:
        return docs

    res_id = getattr(health_result, "id", None)
    upd_at = getattr(health_result, "calculated_at", None) or getattr(health_result, "created_at", None) or datetime.utcnow()
    h_score = getattr(health_result, "health_score", 0.0)
    h_grade = getattr(health_result, "health_grade", "UNKNOWN")
    issues = getattr(health_result, "issues", []) or []
    sorted_issues = sorted(
        issues,
        key=lambda x: (
            -getattr(x, "priority_score", 0.0),
            getattr(x, "column_name", "") or "",
            getattr(x, "issue_type", "") or "",
            str(getattr(x, "id", ""))
        )
    )

    # 1. Health Summary Chunk
    crit_issues = [i for i in sorted_issues if getattr(i, "severity", "").upper() == "CRITICAL"]
    high_issues = [i for i in sorted_issues if getattr(i, "severity", "").upper() == "HIGH"]
    health_summary_content = (
        f"### Holistic Data Health Summary: {dataset_name} (Version V{version_number})\n"
        f"- Holistic Health Score: {h_score:.1f}/100 (Grade: {h_grade})\n"
        f"- Total Prioritized Issues: {len(sorted_issues)}\n"
        f"- Critical Severity Issues: {len(crit_issues)}\n"
        f"- High Severity Issues: {len(high_issues)}\n"
    )
    docs.append({
        "dataset_id": dataset_id,
        "version_id": version_id,
        "comparison_id": None,
        "source_result_id": res_id,
        "source_result_updated_at": upd_at,
        "source_phase": "PHASE_9_HEALTH",
        "document_type": "health_summary",
        "logical_document_id": f"{dataset_id}:{version_id}:PHASE_9_HEALTH:health_summary:summary",
        "title": f"Health Score: {dataset_name} V{version_number}",
        "content": sanitize_text(health_summary_content[:1500]),
        "doc_metadata": {
            "health_score": h_score,
            "health_grade": h_grade,
            "total_issues": len(sorted_issues),
        },
    })

    # 2. Individual Prioritized Issues (Remediation is STRICTLY suggested recommendations)
    for idx, issue in enumerate(sorted_issues):
        rank = idx + 1
        issue_id = getattr(issue, "id", None)
        cat = getattr(issue, "issue_type", None) or getattr(issue, "category", "Quality")
        sev = (getattr(issue, "severity", "MEDIUM") or "MEDIUM").upper()
        col = getattr(issue, "column_name", None) or getattr(issue, "affected_column", "dataset") or "dataset"
        pct = getattr(issue, "affected_percentage", 0.0)
        p_score = getattr(issue, "priority_score", 0.0)
        
        rec_obj = getattr(issue, "recommendation", None)
        if isinstance(rec_obj, dict):
            remed = rec_obj.get("action") or rec_obj.get("suggested_action") or rec_obj.get("summary") or "Review data pipeline"
        elif isinstance(rec_obj, str) and rec_obj:
            remed = rec_obj
        else:
            remed = getattr(issue, "remediation_suggestion", "Review data pipeline")
        
        issue_content = (
            f"### Prioritized Issue #{rank}: {cat} ({sev}) in Column '{col}' (Dataset: {dataset_name} V{version_number})\n"
            f"- Issue Category: {cat}\n"
            f"- Priority Score: {p_score:.1f}/100 (Rank #{rank})\n"
            f"- Severity Level: {sev}\n"
            f"- Affected Data Proportion: {pct:.1f}%\n"
            f"- Suggested Remediation Action: {remed}\n"
        )
        docs.append({
            "dataset_id": dataset_id,
            "version_id": version_id,
            "comparison_id": None,
            "source_result_id": getattr(issue, "id", res_id),
            "source_result_updated_at": upd_at,
            "source_phase": "PHASE_9_HEALTH",
            "document_type": "issue_detail",
            "logical_document_id": f"{dataset_id}:{version_id}:PHASE_9_HEALTH:issue_detail:{issue_id or f'{rank}_{col}_{cat}'}",
            "title": f"Issue #{rank}: {cat} in {col} ({sev})",
            "content": sanitize_text(issue_content[:1500]),
            "doc_metadata": {
                "priority_rank": rank,
                "priority_score": p_score,
                "category": cat,
                "severity": sev,
                "column_name": col,
                "affected_percentage": pct,
            },
        })

    return docs


# ---------------------------------------------------------------------------
# Phase 10 Version Comparison Document Builders
# ---------------------------------------------------------------------------
def build_comparison_documents(
    dataset_id: UUID,
    comparison: Any,
    dataset_name: str,
    base_version_num: int,
    curr_version_num: int,
) -> List[Dict[str, Any]]:
    """Build version comparison summary and column drift evidence documents."""
    docs = []
    if not comparison:
        return docs

    comp_id = getattr(comparison, "id", None)
    upd_at = getattr(comparison, "compared_at", None) or datetime.utcnow()
    overall_drift = getattr(comparison, "overall_drift_status", "NO_DRIFT")
    drivers = getattr(comparison, "drift_drivers", []) or []
    schema_sum = getattr(comparison, "schema_drift_summary", {}) or {}
    col_drifts = getattr(comparison, "column_drifts", []) or []
    sorted_col_drifts = sorted(col_drifts, key=lambda x: getattr(x, "column_name", ""))

    # 1. Comparison Summary Chunk
    comp_summary_content = (
        f"### Dataset Version Comparison: {dataset_name} (V{base_version_num} ➔ V{curr_version_num})\n"
        f"- Overall Drift Status: {overall_drift}\n"
        f"- Schema Evolution: +{len(schema_sum.get('added_columns', []))} added, -{len(schema_sum.get('removed_columns', []))} removed, {len(schema_sum.get('type_changed_columns', []))} type changed\n"
        f"- Primary Drift Drivers:\n"
    )
    for d in drivers[:5]:
        comp_summary_content += f"  * {d}\n"

    docs.append({
        "dataset_id": dataset_id,
        "version_id": None,
        "comparison_id": comp_id,
        "source_result_id": comp_id,
        "source_result_updated_at": upd_at,
        "source_phase": "PHASE_10_DRIFT",
        "document_type": "comparison_summary",
        "logical_document_id": f"{dataset_id}:{comp_id}:PHASE_10_DRIFT:comparison_summary:summary",
        "title": f"Drift Summary: {dataset_name} (V{base_version_num} ➔ V{curr_version_num})",
        "content": sanitize_text(comp_summary_content[:1500]),
        "doc_metadata": {
            "overall_drift_status": overall_drift,
            "baseline_version_number": base_version_num,
            "current_version_number": curr_version_num,
            "baseline_version_id": str(getattr(comparison, "baseline_version_id", "")),
            "current_version_id": str(getattr(comparison, "current_version_id", "")),
        },
    })

    # 2. Per-Column Drift Evidence Chunks
    for cd in sorted_col_drifts:
        col = getattr(cd, "column_name", "unknown")
        drift_stat = getattr(cd, "drift_status", "NO_DRIFT")
        schema_stat = getattr(cd, "schema_status", "UNCHANGED")
        evidence = getattr(cd, "drift_evidence", []) or []
        stat_comp = getattr(cd, "statistical_comparison", {}) or {}
        miss_comp = getattr(cd, "missingness_comparison", {}) or {}

        cd_lines = [
            f"### Column Drift Analysis: Column '{col}' ({dataset_name} V{base_version_num} ➔ V{curr_version_num})",
            f"- Column Drift Status: {drift_stat}",
            f"- Schema Status: {schema_stat}",
        ]

        if miss_comp:
            pp = miss_comp.get("percentage_point_change", 0.0)
            cd_lines.append(f"- Missingness Shift: {pp:+} percentage points ({miss_comp.get('baseline_pct', 0)}% ➔ {miss_comp.get('current_pct', 0)}%)")

        if stat_comp:
            test_type = stat_comp.get("test_type", "Statistical Test")
            if stat_comp.get("status") == "EXECUTED":
                stat_val = stat_comp.get("statistic")
                p_val = stat_comp.get("p_value")
                cd_lines.append(f"- Statistical Test [{test_type}]: Statistic={stat_val}, p-value={p_val}")
            else:
                cd_lines.append(f"- Statistical Test [{test_type}]: {stat_comp.get('reason', 'Test unavailable')}")

        if evidence:
            cd_lines.append("- Documented Drift Evidence:")
            for ev in evidence[:4]:
                cd_lines.append(f"  * {sanitize_text(ev)}")

        cd_content = "\n".join(cd_lines)
        docs.append({
            "dataset_id": dataset_id,
            "version_id": None,
            "comparison_id": comp_id,
            "source_result_id": getattr(cd, "id", comp_id),
            "source_result_updated_at": upd_at,
            "source_phase": "PHASE_10_DRIFT",
            "document_type": "comparison_column",
            "logical_document_id": f"{dataset_id}:{comp_id}:PHASE_10_DRIFT:comparison_column:{col}",
            "title": f"Column Drift: {col} ({drift_stat})",
            "content": sanitize_text(cd_content[:1500]),
            "doc_metadata": {
                "column_name": col,
                "drift_status": drift_stat,
                "schema_status": schema_stat,
                "baseline_version_number": base_version_num,
                "current_version_number": curr_version_num,
                "baseline_version_id": str(getattr(comparison, "baseline_version_id", "")),
                "current_version_id": str(getattr(comparison, "current_version_id", "")),
            },
        })

    return docs
