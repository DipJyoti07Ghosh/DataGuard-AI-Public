"""
DataGuard AI — Phase 12 Assistant API Endpoints

Provides REST endpoints for:
- POST /api/datasets/{dataset_id}/assistant/ask: Grounded conversational QA using Phase 11 RAG & Ollama
- GET  /api/assistant/health: Health check and status of the local Ollama LLM subsystem
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.assistant import (
    AssistantAskRequest,
    AssistantAskResponse,
    AssistantHealthResponse,
)
from app.services.assistant_service import ask_assistant
from app.services.ollama_service import get_ollama_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Assistant"])


@router.post(
    "/datasets/{dataset_id}/assistant/ask",
    response_model=AssistantAskResponse,
    summary="Ask a grounded analytical question about a dataset, version, or comparison",
)
def ask_dataset_assistant(
    dataset_id: UUID,
    request: AssistantAskRequest,
    db: Session = Depends(get_db),
) -> AssistantAskResponse:
    """
    Ask a natural-language question. Queries Phase 11 pgvector RAG, builds grounded context,
    and returns a factual response from the local Ollama LLM with authoritative source attribution.
    """
    try:
        return ask_assistant(dataset_id=dataset_id, request=request, db=db)
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except ConnectionError as e:
        logger.warning(f"Ollama connection error during assistant query: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except TimeoutError as e:
        logger.warning(f"Ollama timeout during assistant query: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e),
        )
    except RuntimeError as e:
        logger.error(f"Ollama runtime error during assistant query: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error in assistant endpoint: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the assistant request.",
        )


@router.get(
    "/assistant/health",
    response_model=AssistantHealthResponse,
    summary="Check local Ollama service health and configured model availability",
)
def get_assistant_health() -> AssistantHealthResponse:
    """
    Check if the local Ollama daemon is reachable and whether the configured model is ready.
    """
    ollama_svc = get_ollama_service()
    return ollama_svc.check_health()
