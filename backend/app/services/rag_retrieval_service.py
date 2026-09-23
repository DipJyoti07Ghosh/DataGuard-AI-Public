"""
DataGuard AI — Phase 11 Semantic Retrieval Service

Executes native pgvector cosine similarity search over RAG knowledge documents
with explicit retrieval scopes (VERSION, COMPARISON, DATASET) and SQL metadata filtering.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from app.models.rag import RAGDocument
from app.schemas.rag import RetrievalScope, RAGRetrieveRequest
from app.services.embedding_service import get_embedding_provider, EmbeddingProvider

logger = logging.getLogger(__name__)


def retrieve_rag_documents(
    dataset_id: UUID,
    query: str,
    scope: RetrievalScope,
    db: Session,
    version_id: Optional[UUID] = None,
    comparison_id: Optional[UUID] = None,
    top_k: int = 5,
    phases: Optional[List[str]] = None,
    include_comparisons: bool = False,
    embedding_provider: Optional[EmbeddingProvider] = None,
) -> List[Dict[str, Any]]:
    """
    Perform semantic vector search using pgvector cosine distance (<=>).
    Enforces strict dataset and version scoping.
    """
    provider = embedding_provider or get_embedding_provider()

    # 1. Generate query embedding
    query_vector = provider.embed_text(query)

    # 2. Build explicit scope filtering condition
    conditions = [RAGDocument.dataset_id == dataset_id]

    if scope == RetrievalScope.VERSION:
        if not version_id:
            raise ValueError("version_id is required when retrieval scope is 'VERSION'")
        if include_comparisons:
            # Include version documents OR comparison documents involving this version
            v_str = str(version_id)
            conditions.append(
                or_(
                    RAGDocument.version_id == version_id,
                    and_(
                        RAGDocument.comparison_id.isnot(None),
                        or_(
                            RAGDocument.doc_metadata["baseline_version_id"].astext == v_str,
                            RAGDocument.doc_metadata["current_version_id"].astext == v_str,
                        )
                    )
                )
            )
        else:
            conditions.append(RAGDocument.version_id == version_id)

    elif scope == RetrievalScope.COMPARISON:
        if not comparison_id:
            raise ValueError("comparison_id is required when retrieval scope is 'COMPARISON'")
        conditions.append(RAGDocument.comparison_id == comparison_id)

    elif scope == RetrievalScope.DATASET:
        # Scoped across dataset; preserves version_id on all returned records
        pass

    # 3. Optional phase filtering
    if phases and len(phases) > 0:
        valid_phases = [p.upper() for p in phases]
        conditions.append(RAGDocument.source_phase.in_(valid_phases))

    # 4. Native pgvector cosine distance calculation
    # pgvector provides the .cosine_distance() method in SQLAlchemy
    distance_expr = RAGDocument.embedding.cosine_distance(query_vector)

    stmt = (
        select(
            RAGDocument,
            distance_expr.label("distance")
        )
        .where(and_(*conditions))
        .order_by(distance_expr.asc())
        .limit(top_k)
    )

    results = db.execute(stmt).all()

    retrieved = []
    for doc, dist in results:
        # Cosine distance ranges from 0 (identical) to 2 (opposite)
        # Similarity score: 1.0 - distance (or max(0.0, 1.0 - distance))
        similarity = round(max(0.0, float(1.0 - dist)), 4)

        col_name = doc.doc_metadata.get("column_name") if doc.doc_metadata else None

        retrieved.append({
            "document_id": doc.id,
            "dataset_id": doc.dataset_id,
            "version_id": doc.version_id,
            "comparison_id": doc.comparison_id,
            "source_result_id": doc.source_result_id,
            "source_phase": doc.source_phase,
            "document_type": doc.document_type,
            "logical_document_id": doc.logical_document_id,
            "title": doc.title,
            "content": doc.content,
            "column_name": col_name,
            "doc_metadata": doc.doc_metadata or {},
            "similarity": similarity,
            "embedding_provider": doc.embedding_provider,
            "embedding_model": doc.embedding_model,
            "embedding_dimension": doc.embedding_dimension,
            "content_hash": doc.content_hash,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        })

    logger.info(
        f"Semantic Retrieval for query='{query[:40]}' (Scope={scope}, Dataset={dataset_id}): "
        f"Retrieved {len(retrieved)} chunks (Top similarity={retrieved[0]['similarity'] if retrieved else 'N/A'})"
    )

    return retrieved
