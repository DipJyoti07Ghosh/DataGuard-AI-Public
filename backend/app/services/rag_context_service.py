"""
DataGuard AI — Phase 11 Grounded Context Service

Transforms retrieved semantic knowledge documents into an assembled,
privacy-safe, grounded factual context object for downstream Phase 12 LLM consumption.
"""

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.schemas.rag import (
    RetrievalScope,
    GroundedSource,
    GroundedContextResponse,
)

logger = logging.getLogger(__name__)


def build_grounded_context(
    query: str,
    dataset_id: UUID,
    scope: RetrievalScope,
    retrieved_documents: List[Dict[str, Any]],
    version_id: Optional[UUID] = None,
    comparison_id: Optional[UUID] = None,
) -> GroundedContextResponse:
    """
    Assemble retrieved document chunks into a structured GroundedContextResponse.
    Formats source evidence with complete factual grounding and provenance.
    """
    sources: List[GroundedSource] = []
    seen_contents = set()
    warnings: List[str] = []

    if not retrieved_documents:
        warnings.append("No relevant analytical evidence found for the specified query and scope.")
        return GroundedContextResponse(
            query=query,
            dataset_id=dataset_id,
            scope=scope,
            version_id=version_id,
            comparison_id=comparison_id,
            retrieved_count=0,
            sources=[],
            grounded_context_text="Information not available in the analyzed dataset/version.",
            warnings=warnings,
        )

    context_blocks = []

    for i, doc in enumerate(retrieved_documents, 1):
        content = doc.get("content", "").strip()
        if content in seen_contents:
            continue
        seen_contents.add(content)

        phase = doc.get("source_phase", "ANALYTICS")
        doc_type = doc.get("document_type", "evidence")
        col_name = doc.get("column_name")
        sim = doc.get("similarity", 0.0)
        v_id = doc.get("version_id")
        c_id = doc.get("comparison_id")
        title = doc.get("title", f"Source {i}")
        meta = doc.get("doc_metadata", {})

        source_obj = GroundedSource(
            document_id=doc["document_id"],
            source_phase=phase,
            document_type=doc_type,
            column_name=col_name,
            version_id=v_id,
            comparison_id=c_id,
            similarity=sim,
            title=title,
            content=content,
            metadata=meta,
        )
        sources.append(source_obj)

        col_str = f" | Column: '{col_name}'" if col_name else ""
        v_str = f" | Version: {v_id}" if v_id else (f" | Comparison: {c_id}" if c_id else "")
        block_header = f"### [Source {len(sources)}] {phase}{col_str}{v_str} (Relevance Score: {sim:.4f})"
        context_blocks.append(f"{block_header}\n{content}")

    if sources and max(s.similarity for s in sources) < 0.40:
        warnings.append("Retrieved analytical evidence has low semantic relevance to the query.")

    grounded_context_text = "\n\n".join(context_blocks)

    return GroundedContextResponse(
        query=query,
        dataset_id=dataset_id,
        scope=scope,
        version_id=version_id,
        comparison_id=comparison_id,
        retrieved_count=len(sources),
        sources=sources,
        grounded_context_text=grounded_context_text,
        warnings=warnings,
    )
