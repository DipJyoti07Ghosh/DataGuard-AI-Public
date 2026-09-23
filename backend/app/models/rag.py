"""
DataGuard AI — Phase 11 RAG Document Models

SQLAlchemy models for persisting vectorized semantic chunks generated from Phase 4–10 analysis results.
Uses native pgvector VECTOR(384) for fast cosine similarity search.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class RAGDocument(Base):
    """
    RAG Knowledge Document chunk.
    Represents a privacy-scrubbed, semantic chunk of analytical evidence
    indexed from Phases 4–10 results with native 384-d pgvector embedding.
    """
    __tablename__ = "rag_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    comparison_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_comparisons.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Originating record reference for traceability
    source_result_id = Column(UUID(as_uuid=True), nullable=True)
    source_result_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Classification & Provenance
    source_phase = Column(String(50), nullable=False)  # PHASE_4_PROFILING, PHASE_5_QUALITY, etc.
    document_type = Column(String(50), nullable=False)  # dataset_overview, quality_issue, etc.
    logical_document_id = Column(String(255), nullable=False, index=True)  # {dataset_id}:{version_id|comparison_id}:{phase}:{type}:{target}

    # Content
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    doc_metadata = Column(JSONB, nullable=False, default=dict)

    # Embedding & Vector Identity
    embedding = Column(Vector(384), nullable=False)
    embedding_provider = Column(String(50), nullable=False, default="fastembed")
    embedding_model = Column(String(100), nullable=False, default="BAAI/bge-small-en-v1.5")
    embedding_dimension = Column(Integer, nullable=False, default=384)
    embedding_model_version = Column(String(50), nullable=False, default="1.5")
    content_hash = Column(String(64), nullable=False, index=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    dataset = relationship("Dataset", back_populates="rag_documents")
    version = relationship("DatasetVersion", back_populates="rag_documents")
    comparison = relationship("DatasetComparison", back_populates="rag_documents")

    __table_args__ = (
        Index("ix_rag_documents_dataset_version", "dataset_id", "version_id"),
    )

    def __repr__(self) -> str:
        return f"<RAGDocument(id={self.id}, phase={self.source_phase}, type={self.document_type}, title='{self.title[:30]}')>"
