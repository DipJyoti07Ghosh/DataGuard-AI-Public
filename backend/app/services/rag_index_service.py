"""
DataGuard AI — Phase 11 RAG Indexing Service

Orchestrates knowledge extraction from stored Phase 4–10 results,
SHA-256 content hashing, embedding lifecycle management, and idempotent
persistence in PostgreSQL with native pgvector.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetVersion
from app.models.comparison import DatasetComparison
from app.models.rag import RAGDocument
from app.services.embedding_service import get_embedding_provider, EmbeddingProvider
from app.services.rag_document_builder import (
    build_profiling_documents,
    build_quality_documents,
    build_pii_documents,
    build_risk_documents,
    build_anomaly_documents,
    build_health_documents,
    build_comparison_documents,
    compute_content_hash,
)
from app.schemas.rag import RAGIndexResponse

logger = logging.getLogger(__name__)


def index_version_rag(
    dataset_id: UUID,
    version_id: UUID,
    db: Session,
    force_reindex: bool = False,
    embedding_provider: Optional[EmbeddingProvider] = None,
) -> RAGIndexResponse:
    """
    Index all stored analytical results (Phases 4–9) for a single dataset version.
    Applies deterministic SHA-256 hashing and Embedding Identity checks to skip redundant embeddings.
    """
    provider = embedding_provider or get_embedding_provider()

    # 1. Fetch Version and Dataset entities
    dataset = db.execute(select(Dataset).where(Dataset.id == dataset_id)).scalar_one_or_none()
    if not dataset:
        raise ValueError(f"Dataset '{dataset_id}' not found")

    version = db.execute(
        select(DatasetVersion).where(
            DatasetVersion.id == version_id,
            DatasetVersion.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()
    if not version:
        raise ValueError(f"DatasetVersion '{version_id}' not found for dataset '{dataset_id}'")

    dataset_name = dataset.name
    v_num = version.version_number

    # 2. Build Candidate Documents from Stored Results
    candidates: List[Dict[str, Any]] = []

    # Phase 4 Profiling
    candidates.extend(build_profiling_documents(dataset_id, version_id, v_num, dataset_name, version.profiling_result))
    # Phase 5 Quality
    candidates.extend(build_quality_documents(dataset_id, version_id, v_num, dataset_name, version.quality_result))
    # Phase 6 PII
    candidates.extend(build_pii_documents(dataset_id, version_id, v_num, dataset_name, version.pii_result))
    # Phase 7 ML Risk
    candidates.extend(build_risk_documents(dataset_id, version_id, v_num, dataset_name, version.risk_predictions))
    # Phase 8 Anomalies
    candidates.extend(build_anomaly_documents(dataset_id, version_id, v_num, dataset_name, version.anomaly_result))
    # Phase 9 Health
    candidates.extend(build_health_documents(dataset_id, version_id, v_num, dataset_name, version.health_result))

    # 3. Retrieve Existing RAG Documents for this version
    existing_docs = {
        doc.logical_document_id: doc
        for doc in db.execute(
            select(RAGDocument).where(
                and_(
                    RAGDocument.dataset_id == dataset_id,
                    RAGDocument.version_id == version_id,
                )
            )
        ).scalars().all()
    }

    # 4. Process Candidates with Embedding Lifecycle
    new_count = 0
    updated_count = 0
    skipped_count = 0
    phase_counts: Dict[str, int] = {}
    active_logical_ids = set()

    for cand in candidates:
        logical_id = cand["logical_document_id"]
        content = cand["content"]
        c_hash = compute_content_hash(content)
        cand["content_hash"] = c_hash
        phase = cand["source_phase"]
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
        active_logical_ids.add(logical_id)

        existing = existing_docs.get(logical_id)

        if existing and not force_reindex:
            # Check Embedding Identity and Content Hash
            is_same_content = (existing.content_hash == c_hash)
            is_same_identity = (
                existing.embedding_provider == provider.provider_name
                and existing.embedding_model == provider.model_name
                and existing.embedding_dimension == provider.dimension
                and existing.embedding_model_version == provider.model_version
            )
            if is_same_content and is_same_identity:
                skipped_count += 1
                continue

        # Needs embedding generation
        emb_vector = provider.embed_text(content)
        now_utc = datetime.now(timezone.utc)

        if existing:
            # Update existing document
            existing.title = cand["title"]
            existing.content = content
            existing.doc_metadata = cand["doc_metadata"]
            existing.embedding = emb_vector
            existing.embedding_provider = provider.provider_name
            existing.embedding_model = provider.model_name
            existing.embedding_dimension = provider.dimension
            existing.embedding_model_version = provider.model_version
            existing.content_hash = c_hash
            existing.source_result_id = cand["source_result_id"]
            existing.source_result_updated_at = cand["source_result_updated_at"]
            existing.updated_at = now_utc
            updated_count += 1
        else:
            # Create new document
            new_doc = RAGDocument(
                dataset_id=dataset_id,
                version_id=version_id,
                comparison_id=None,
                source_result_id=cand["source_result_id"],
                source_result_updated_at=cand["source_result_updated_at"],
                source_phase=cand["source_phase"],
                document_type=cand["document_type"],
                logical_document_id=logical_id,
                title=cand["title"],
                content=content,
                doc_metadata=cand["doc_metadata"],
                embedding=emb_vector,
                embedding_provider=provider.provider_name,
                embedding_model=provider.model_name,
                embedding_dimension=provider.dimension,
                embedding_model_version=provider.model_version,
                content_hash=c_hash,
                created_at=now_utc,
                updated_at=now_utc,
            )
            db.add(new_doc)
            new_count += 1

    # 5. Delete Stale Documents that are no longer present in source
    deleted_stale = 0
    for old_logical_id, old_doc in existing_docs.items():
        if old_logical_id not in active_logical_ids:
            db.delete(old_doc)
            deleted_stale += 1

    db.commit()
    logger.info(
        f"RAG Indexing complete for Dataset '{dataset_name}' V{v_num}: "
        f"Total={len(candidates)}, New={new_count}, Updated={updated_count}, Skipped={skipped_count}, StaleDeleted={deleted_stale}"
    )

    return RAGIndexResponse(
        dataset_id=dataset_id,
        version_id=version_id,
        comparison_id=None,
        status="COMPLETED",
        total_indexed=len(candidates),
        new_documents=new_count,
        updated_documents=updated_count,
        skipped_unchanged=skipped_count,
        deleted_stale=deleted_stale,
        documents_by_phase=phase_counts,
        indexed_at=datetime.now(timezone.utc),
    )


def index_comparison_rag(
    dataset_id: UUID,
    comparison_id: UUID,
    db: Session,
    force_reindex: bool = False,
    embedding_provider: Optional[EmbeddingProvider] = None,
) -> RAGIndexResponse:
    """
    Index stored Phase 10 version comparison results for a dataset comparison.
    """
    provider = embedding_provider or get_embedding_provider()

    dataset = db.execute(select(Dataset).where(Dataset.id == dataset_id)).scalar_one_or_none()
    if not dataset:
        raise ValueError(f"Dataset '{dataset_id}' not found")

    comparison = db.execute(
        select(DatasetComparison).where(
            DatasetComparison.id == comparison_id,
            DatasetComparison.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()
    if not comparison:
        raise ValueError(f"DatasetComparison '{comparison_id}' not found for dataset '{dataset_id}'")

    b_num = comparison.baseline_version.version_number if comparison.baseline_version else 1
    c_num = comparison.current_version.version_number if comparison.current_version else 2

    candidates = build_comparison_documents(
        dataset_id=dataset_id,
        comparison=comparison,
        dataset_name=dataset.name,
        base_version_num=b_num,
        curr_version_num=c_num,
    )

    existing_docs = {
        doc.logical_document_id: doc
        for doc in db.execute(
            select(RAGDocument).where(
                and_(
                    RAGDocument.dataset_id == dataset_id,
                    RAGDocument.comparison_id == comparison_id,
                )
            )
        ).scalars().all()
    }

    new_count = 0
    updated_count = 0
    skipped_count = 0
    active_logical_ids = set()

    for cand in candidates:
        logical_id = cand["logical_document_id"]
        content = cand["content"]
        c_hash = compute_content_hash(content)
        cand["content_hash"] = c_hash
        active_logical_ids.add(logical_id)

        existing = existing_docs.get(logical_id)

        if existing and not force_reindex:
            is_same_content = (existing.content_hash == c_hash)
            is_same_identity = (
                existing.embedding_provider == provider.provider_name
                and existing.embedding_model == provider.model_name
                and existing.embedding_dimension == provider.dimension
                and existing.embedding_model_version == provider.model_version
            )
            if is_same_content and is_same_identity:
                skipped_count += 1
                continue

        emb_vector = provider.embed_text(content)
        now_utc = datetime.now(timezone.utc)

        if existing:
            existing.title = cand["title"]
            existing.content = content
            existing.doc_metadata = cand["doc_metadata"]
            existing.embedding = emb_vector
            existing.embedding_provider = provider.provider_name
            existing.embedding_model = provider.model_name
            existing.embedding_dimension = provider.dimension
            existing.embedding_model_version = provider.model_version
            existing.content_hash = c_hash
            existing.source_result_id = cand["source_result_id"]
            existing.source_result_updated_at = cand["source_result_updated_at"]
            existing.updated_at = now_utc
            updated_count += 1
        else:
            new_doc = RAGDocument(
                dataset_id=dataset_id,
                version_id=None,
                comparison_id=comparison_id,
                source_result_id=cand["source_result_id"],
                source_result_updated_at=cand["source_result_updated_at"],
                source_phase=cand["source_phase"],
                document_type=cand["document_type"],
                logical_document_id=logical_id,
                title=cand["title"],
                content=content,
                doc_metadata=cand["doc_metadata"],
                embedding=emb_vector,
                embedding_provider=provider.provider_name,
                embedding_model=provider.model_name,
                embedding_dimension=provider.dimension,
                embedding_model_version=provider.model_version,
                content_hash=c_hash,
                created_at=now_utc,
                updated_at=now_utc,
            )
            db.add(new_doc)
            new_count += 1

    deleted_stale = 0
    for old_logical_id, old_doc in existing_docs.items():
        if old_logical_id not in active_logical_ids:
            db.delete(old_doc)
            deleted_stale += 1

    db.commit()

    return RAGIndexResponse(
        dataset_id=dataset_id,
        version_id=None,
        comparison_id=comparison_id,
        status="COMPLETED",
        total_indexed=len(candidates),
        new_documents=new_count,
        updated_documents=updated_count,
        skipped_unchanged=skipped_count,
        deleted_stale=deleted_stale,
        documents_by_phase={"PHASE_10_DRIFT": len(candidates)},
        indexed_at=datetime.now(timezone.utc),
    )


def index_dataset_rag(
    dataset_id: UUID,
    db: Session,
    force_reindex: bool = False,
    embedding_provider: Optional[EmbeddingProvider] = None,
) -> RAGIndexResponse:
    """Index all versions and comparisons for an entire dataset."""
    dataset = db.execute(select(Dataset).where(Dataset.id == dataset_id)).scalar_one_or_none()
    if not dataset:
        raise ValueError(f"Dataset '{dataset_id}' not found")

    total_indexed = 0
    new_docs = 0
    upd_docs = 0
    skip_docs = 0
    del_docs = 0
    phase_counts: Dict[str, int] = {}

    for version in dataset.versions:
        res = index_version_rag(dataset_id, version.id, db, force_reindex, embedding_provider)
        total_indexed += res.total_indexed
        new_docs += res.new_documents
        upd_docs += res.updated_documents
        skip_docs += res.skipped_unchanged
        del_docs += res.deleted_stale
        for p, cnt in res.documents_by_phase.items():
            phase_counts[p] = phase_counts.get(p, 0) + cnt

    # Index comparisons
    comparisons = db.execute(
        select(DatasetComparison).where(DatasetComparison.dataset_id == dataset_id)
    ).scalars().all()
    for comp in comparisons:
        res = index_comparison_rag(dataset_id, comp.id, db, force_reindex, embedding_provider)
        total_indexed += res.total_indexed
        new_docs += res.new_documents
        upd_docs += res.updated_documents
        skip_docs += res.skipped_unchanged
        del_docs += res.deleted_stale
        for p, cnt in res.documents_by_phase.items():
            phase_counts[p] = phase_counts.get(p, 0) + cnt

    return RAGIndexResponse(
        dataset_id=dataset_id,
        version_id=None,
        comparison_id=None,
        status="COMPLETED",
        total_indexed=total_indexed,
        new_documents=new_docs,
        updated_documents=upd_docs,
        skipped_unchanged=skip_docs,
        deleted_stale=del_docs,
        documents_by_phase=phase_counts,
        indexed_at=datetime.now(timezone.utc),
    )
