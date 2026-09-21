"""
DataGuard AI — Phase 11 RAG API Router

Endpoints for indexing Phase 4–10 results, semantic retrieval, document inspection,
and grounded context assembly.
"""

import logging
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.rag import RAGDocument
from app.schemas.rag import (
    RAGIndexRequest,
    RAGIndexResponse,
    RAGRetrieveRequest,
    RAGDocumentResponse,
    RAGDocumentListResponse,
    GroundedContextResponse,
    RetrievalScope,
)
from app.services.rag_index_service import (
    index_version_rag,
    index_comparison_rag,
    index_dataset_rag,
)
from app.services.rag_retrieval_service import retrieve_rag_documents
from app.services.rag_context_service import build_grounded_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["rag"])


@router.post(
    "/{dataset_id}/versions/{version_id}/rag/index",
    response_model=RAGIndexResponse,
    summary="Index stored analysis results for a dataset version into RAG vector space",
)
def index_version_endpoint(
    dataset_id: UUID,
    version_id: UUID,
    req: RAGIndexRequest = RAGIndexRequest(),
    db: Session = Depends(get_db),
):
    try:
        return index_version_rag(
            dataset_id=dataset_id,
            version_id=version_id,
            db=db,
            force_reindex=req.force_reindex,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error indexing version {version_id} into RAG: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"RAG indexing failed: {e}")


@router.post(
    "/{dataset_id}/comparisons/{comparison_id}/rag/index",
    response_model=RAGIndexResponse,
    summary="Index stored version comparison results into RAG vector space",
)
def index_comparison_endpoint(
    dataset_id: UUID,
    comparison_id: UUID,
    req: RAGIndexRequest = RAGIndexRequest(),
    db: Session = Depends(get_db),
):
    try:
        return index_comparison_rag(
            dataset_id=dataset_id,
            comparison_id=comparison_id,
            db=db,
            force_reindex=req.force_reindex,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error indexing comparison {comparison_id} into RAG: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"RAG indexing failed: {e}")


@router.post(
    "/{dataset_id}/rag/index",
    response_model=RAGIndexResponse,
    summary="Index all stored versions and comparisons for a dataset into RAG vector space",
)
def index_dataset_endpoint(
    dataset_id: UUID,
    req: RAGIndexRequest = RAGIndexRequest(),
    db: Session = Depends(get_db),
):
    try:
        return index_dataset_rag(
            dataset_id=dataset_id,
            db=db,
            force_reindex=req.force_reindex,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error indexing dataset {dataset_id} into RAG: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"RAG indexing failed: {e}")


@router.post(
    "/{dataset_id}/rag/retrieve",
    response_model=GroundedContextResponse,
    summary="Execute semantic retrieval and assemble grounded context for a query",
)
def retrieve_rag_endpoint(
    dataset_id: UUID,
    req: RAGRetrieveRequest,
    db: Session = Depends(get_db),
):
    try:
        retrieved = retrieve_rag_documents(
            dataset_id=dataset_id,
            query=req.query,
            scope=req.scope,
            db=db,
            version_id=req.version_id,
            comparison_id=req.comparison_id,
            top_k=req.top_k,
            phases=req.phases,
            include_comparisons=req.include_comparisons,
        )
        return build_grounded_context(
            query=req.query,
            dataset_id=dataset_id,
            scope=req.scope,
            retrieved_documents=retrieved,
            version_id=req.version_id,
            comparison_id=req.comparison_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error executing semantic retrieval for dataset {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Retrieval failed: {e}")


@router.get(
    "/{dataset_id}/rag/documents",
    response_model=RAGDocumentListResponse,
    summary="List indexed RAG documents for a dataset",
)
def list_dataset_rag_documents(
    dataset_id: UUID,
    version_id: Optional[UUID] = None,
    source_phase: Optional[str] = None,
    document_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    conditions = [RAGDocument.dataset_id == dataset_id]
    if version_id:
        conditions.append(RAGDocument.version_id == version_id)
    if source_phase:
        conditions.append(RAGDocument.source_phase == source_phase.upper())
    if document_type:
        conditions.append(RAGDocument.document_type == document_type)

    docs = db.execute(
        select(RAGDocument)
        .where(and_(*conditions))
        .order_by(RAGDocument.source_phase, RAGDocument.document_type, RAGDocument.created_at.desc())
    ).scalars().all()

    items = [
        RAGDocumentResponse(
            id=d.id,
            dataset_id=d.dataset_id,
            version_id=d.version_id,
            comparison_id=d.comparison_id,
            source_result_id=d.source_result_id,
            source_phase=d.source_phase,
            document_type=d.document_type,
            logical_document_id=d.logical_document_id,
            title=d.title,
            content=d.content,
            doc_metadata=d.doc_metadata or {},
            similarity=None,
            embedding_provider=d.embedding_provider,
            embedding_model=d.embedding_model,
            embedding_dimension=d.embedding_dimension,
            content_hash=d.content_hash,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in docs
    ]

    return RAGDocumentListResponse(
        dataset_id=dataset_id,
        total_count=len(items),
        documents=items,
    )


@router.get(
    "/{dataset_id}/versions/{version_id}/rag/documents",
    response_model=RAGDocumentListResponse,
    summary="List indexed RAG documents for a specific dataset version",
)
def list_version_rag_documents(
    dataset_id: UUID,
    version_id: UUID,
    source_phase: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return list_dataset_rag_documents(
        dataset_id=dataset_id,
        version_id=version_id,
        source_phase=source_phase,
        db=db,
    )


@router.delete(
    "/{dataset_id}/rag/documents",
    status_code=status.HTTP_200_OK,
    summary="Purge all RAG documents for a dataset",
)
def purge_dataset_rag_documents(
    dataset_id: UUID,
    db: Session = Depends(get_db),
):
    res = db.execute(delete(RAGDocument).where(RAGDocument.dataset_id == dataset_id))
    db.commit()
    return {"message": f"Successfully deleted {res.rowcount} RAG documents for dataset {dataset_id}"}
