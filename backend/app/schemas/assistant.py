"""
DataGuard AI — Phase 12 Assistant Schemas

Pydantic schemas for the grounded AI Assistant:
- AssistantScope: Retrieval contexts (VERSION, COMPARISON, DATASET)
- AssistantAskRequest: Request payload with question, scope, and filters
- AssistantSource: Provenance metadata built server-side from Phase 11 retrieval
- AssistantAskResponse: Structured answer with grounded sources and warnings
- AssistantHealthResponse: Ollama connectivity and model availability status
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


class AssistantScope(str, Enum):
    """Supported scoping modes for assistant queries."""
    VERSION = "VERSION"
    COMPARISON = "COMPARISON"
    DATASET = "DATASET"


class AssistantAskRequest(BaseModel):
    """User question payload submitted to the Assistant."""
    question: str = Field(..., min_length=1, max_length=2000, description="Natural-language question")
    scope: AssistantScope = Field(default=AssistantScope.VERSION, description="Context scope")
    version_id: Optional[UUID] = Field(default=None, description="Target version UUID (required if scope=VERSION)")
    comparison_id: Optional[UUID] = Field(default=None, description="Target comparison UUID (required if scope=COMPARISON)")
    top_k: int = Field(default=8, ge=3, le=15, description="Number of evidence chunks to retrieve (bounded 3-15)")
    phase_filters: Optional[List[str]] = Field(default=None, description="Optional analytical phase filters")
    min_similarity: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Optional override for minimum RAG similarity threshold")

    @field_validator("question")
    @classmethod
    def validate_question_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Question cannot be empty or whitespace only")
        return s


class AssistantSource(BaseModel):
    """
    Authoritative server-side source provenance derived directly from Phase 11 RAG.
    Guarantees that the LLM cannot hallucinate or mutate document IDs and metadata.
    """
    document_id: UUID = Field(..., description="Unique UUID of the RAG document")
    source_phase: str = Field(..., description="Analytical phase (PHASE_4_PROFILING, etc.)")
    document_type: str = Field(..., description="Document type (profiling_column, quality_issue, etc.)")
    column_name: Optional[str] = Field(default=None, description="Associated column name if column-scoped")
    version_id: Optional[UUID] = Field(default=None, description="Version UUID if version-scoped")
    version_number: Optional[int] = Field(default=None, description="Version number (e.g. 1, 2)")
    comparison_id: Optional[UUID] = Field(default=None, description="Comparison UUID if comparison-scoped")
    similarity: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    source_result_id: Optional[UUID] = Field(default=None, description="Underlying phase result entity UUID")
    title: str = Field(..., description="Human-readable title of the knowledge chunk")
    content_snippet: str = Field(..., description="Privacy-sanitized content snippet used as grounding evidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe structured metadata")


class AssistantAskResponse(BaseModel):
    """Structured response returned by the Assistant API."""
    answer: str = Field(..., description="Natural-language response grounded in retrieved evidence")
    scope: AssistantScope = Field(..., description="Applied query scope")
    dataset_id: UUID = Field(..., description="Dataset UUID")
    version_id: Optional[UUID] = Field(default=None, description="Version UUID if applicable")
    comparison_id: Optional[UUID] = Field(default=None, description="Comparison UUID if applicable")
    sources: List[AssistantSource] = Field(default_factory=list, description="Authoritative sources from Phase 11")
    warnings: List[str] = Field(default_factory=list, description="Diagnostic warnings (e.g. low evidence, missing phases)")
    grounded: bool = Field(default=True, description="True if answer is backed by retrieved evidence")
    model: str = Field(..., description="Ollama LLM model name used for generation")
    response_time_ms: float = Field(..., description="Total processing time in milliseconds")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp of generation")


class AssistantHealthResponse(BaseModel):
    """Health check and model status response for the Ollama inference subsystem."""
    status: str = Field(..., description="'HEALTHY', 'DEGRADED', or 'UNAVAILABLE'")
    ollama_reachable: bool = Field(..., description="True if local Ollama daemon responded to ping")
    ollama_base_url: str = Field(..., description="Configured Ollama base URL")
    configured_model: str = Field(..., description="Model name configured in settings")
    model_available: bool = Field(..., description="True if configured model is downloaded and ready in Ollama")
    available_models: List[str] = Field(default_factory=list, description="List of locally installed model tags")
    message: str = Field(..., description="Human-readable status or troubleshooting instruction")
