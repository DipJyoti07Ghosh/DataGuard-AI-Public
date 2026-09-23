"""
DataGuard AI — Phase 11 RAG Schemas

Pydantic models for indexing, semantic retrieval, grounded context assembly,
and document inspection.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class RetrievalScope(str, Enum):
    VERSION = "VERSION"        # Scoped to exact dataset_id + version_id
    COMPARISON = "COMPARISON"  # Scoped to exact dataset_id + comparison_id
    DATASET = "DATASET"        # Scoped to dataset-level documents across versions


class RAGIndexRequest(BaseModel):
    """Request parameters for indexing stored analysis results into RAG vector space."""
    force_reindex: bool = Field(
        default=False,
        description="If True, bypasses content hash check and forces re-embedding of all documents.",
    )


class RAGIndexResponse(BaseModel):
    """Summary of RAG indexing operation."""
    dataset_id: UUID
    version_id: Optional[UUID] = None
    comparison_id: Optional[UUID] = None
    status: str = "COMPLETED"
    total_indexed: int
    new_documents: int
    updated_documents: int
    skipped_unchanged: int
    deleted_stale: int
    documents_by_phase: Dict[str, int] = Field(default_factory=dict)
    indexed_at: datetime


class RAGRetrieveRequest(BaseModel):
    """Parameters for executing a semantic retrieval query over RAG knowledge documents."""
    query: str = Field(..., min_length=1, max_length=1000, description="Natural language search query")
    scope: RetrievalScope = Field(
        default=RetrievalScope.VERSION,
        description="Explicit retrieval scope: VERSION, COMPARISON, or DATASET",
    )
    version_id: Optional[UUID] = Field(
        default=None,
        description="Target dataset version ID (required when scope=VERSION)",
    )
    comparison_id: Optional[UUID] = Field(
        default=None,
        description="Target dataset comparison ID (required when scope=COMPARISON)",
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Number of top relevant chunks to retrieve")
    phases: Optional[List[str]] = Field(
        default=None,
        description="Optional filter by source phase (e.g. ['PHASE_5_QUALITY', 'PHASE_10_DRIFT'])",
    )
    include_comparisons: bool = Field(
        default=False,
        description="When scope=VERSION, optionally include comparison chunks involving this version",
    )


class RAGDocumentResponse(BaseModel):
    """Detailed view of a single indexed RAG document chunk."""
    document_id: UUID = Field(alias="id")
    dataset_id: UUID
    version_id: Optional[UUID] = None
    comparison_id: Optional[UUID] = None
    source_result_id: Optional[UUID] = None
    source_phase: str
    document_type: str
    logical_document_id: str
    title: str
    content: str
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)
    similarity: Optional[float] = Field(
        default=None,
        description="Semantic cosine similarity relevance score (0.0 to 1.0)",
    )
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    content_hash: str
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        from_attributes = True


class GroundedSource(BaseModel):
    """Traceable individual source evidence chunk inside grounded context."""
    document_id: UUID
    source_phase: str
    document_type: str
    column_name: Optional[str] = None
    version_id: Optional[UUID] = None
    comparison_id: Optional[UUID] = None
    similarity: float = Field(description="Cosine similarity relevance ranking score")
    title: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GroundedContextResponse(BaseModel):
    """
    Complete grounded context payload assembled from semantic retrieval.
    Designed for downstream Phase 12 LLM prompt ingestion with complete factual grounding.
    """
    query: str
    dataset_id: UUID
    scope: RetrievalScope
    version_id: Optional[UUID] = None
    comparison_id: Optional[UUID] = None
    retrieved_count: int
    sources: List[GroundedSource] = Field(default_factory=list)
    grounded_context_text: str = Field(
        description="Sanitized formatted markdown text containing factual source evidence for LLM prompt"
    )
    warnings: List[str] = Field(default_factory=list)


class RAGDocumentListResponse(BaseModel):
    """Paginated or listed RAG documents summary."""
    dataset_id: UUID
    total_count: int
    documents: List[RAGDocumentResponse]
