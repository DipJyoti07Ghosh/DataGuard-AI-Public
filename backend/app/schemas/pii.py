"""
DataGuard AI — PII Detection Pydantic Schemas

Defines request/response data contracts for PII scan results,
detected sensitive entity findings, masked previews, and filtering responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class PIIFindingResponse(BaseModel):
    """Schema representing an individual PII entity detection finding in a column."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scan_id: UUID
    column_name: str
    entity_type: str
    detection_source: str
    confidence: float
    sampled_count: int
    detected_count: int
    detection_rate: float
    risk_level: str
    masked_preview: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class PIIScanSummaryResponse(BaseModel):
    """High-level summary of a PII scan execution."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_version_id: UUID
    scanned_at: datetime
    total_columns_scanned: int
    pii_columns_count: int
    total_findings: int
    summary: Dict[str, Any] = Field(default_factory=dict)


class PIIScanResultResponse(BaseModel):
    """Full PII scan response including all detected findings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_version_id: UUID
    scanned_at: datetime
    total_columns_scanned: int
    pii_columns_count: int
    total_findings: int
    summary: Dict[str, Any] = Field(default_factory=dict)
    findings: List[PIIFindingResponse] = Field(default_factory=list)


class PIIDetailsResponse(BaseModel):
    """Detailed response for PII inspection with applied query filters."""

    model_config = ConfigDict(from_attributes=True)

    scan: PIIScanSummaryResponse
    findings: List[PIIFindingResponse] = Field(default_factory=list)
    total_findings: int
    filtered_count: int
    filters_applied: Dict[str, Any] = Field(default_factory=dict)
