"""
DataGuard AI — Phase 14 Chat & Conversational Intelligence API Endpoints

Provides REST endpoints for managing dataset-scoped persistent chat sessions
and conducting multi-turn grounded conversations with 3-tier provider fallback.
"""

import logging
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatSessionResponse,
    ChatSessionDetailResponse,
    ChatMessageCreate,
    ChatMessageResponse,
)
from app.services.chat_service import (
    create_chat_session,
    list_chat_sessions,
    get_chat_session,
    update_chat_session,
    delete_chat_session,
    send_chat_message,
    retry_last_chat_message,
)
from app.services.llm import LLMUnavailableError, LLMTimeoutError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Chat"])


@router.post(
    "/datasets/{dataset_id}/chat/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new dataset-scoped persistent chat session",
)
def create_session_endpoint(
    dataset_id: UUID,
    request: ChatSessionCreate,
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    """Create a new chat session with a locked operational scope."""
    try:
        return create_chat_session(dataset_id=dataset_id, request=request, db=db)
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.get(
    "/datasets/{dataset_id}/chat/sessions",
    response_model=List[ChatSessionResponse],
    summary="List all chat sessions for a dataset",
)
def list_sessions_endpoint(
    dataset_id: UUID,
    db: Session = Depends(get_db),
) -> List[ChatSessionResponse]:
    """Retrieve all chat sessions associated with a dataset ordered by most recent."""
    try:
        return list_chat_sessions(dataset_id=dataset_id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/datasets/{dataset_id}/chat/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    summary="Get chat session details and message history",
)
def get_session_endpoint(
    dataset_id: UUID,
    session_id: UUID,
    db: Session = Depends(get_db),
) -> ChatSessionDetailResponse:
    """Retrieve a single chat session with complete chronological message history."""
    try:
        return get_chat_session(dataset_id=dataset_id, session_id=session_id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/datasets/{dataset_id}/chat/sessions/{session_id}",
    response_model=ChatSessionResponse,
    summary="Rename a chat session",
)
def update_session_endpoint(
    dataset_id: UUID,
    session_id: UUID,
    request: ChatSessionUpdate,
    db: Session = Depends(get_db),
) -> ChatSessionResponse:
    """Update chat session title."""
    try:
        return update_chat_session(dataset_id=dataset_id, session_id=session_id, request=request, db=db)
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.delete(
    "/datasets/{dataset_id}/chat/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session and all messages",
)
def delete_session_endpoint(
    dataset_id: UUID,
    session_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a chat session and all its child messages."""
    try:
        delete_chat_session(dataset_id=dataset_id, session_id=session_id, db=db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/datasets/{dataset_id}/chat/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    summary="Send a message in a chat session and generate an assistant response",
)
def send_message_endpoint(
    dataset_id: UUID,
    session_id: UUID,
    request: ChatMessageCreate,
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    """
    Send a user question in an active chat session.
    Triggers conversation-aware Phase 11 RAG retrieval and produces a grounded response.
    """
    try:
        return send_chat_message(dataset_id=dataset_id, session_id=session_id, request=request, db=db)
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except (LLMUnavailableError, ConnectionError) as e:
        logger.warning(f"LLM provider unavailable error during chat message: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Assistant is temporarily unavailable. All configured LLM providers failed or are offline.",
        )
    except (LLMTimeoutError, TimeoutError) as e:
        logger.warning(f"LLM provider timeout during chat message: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Chat request timed out. Please try again.",
        )
    except Exception as e:
        logger.error(f"Unexpected error processing chat message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the assistant response.",
        )


@router.post(
    "/datasets/{dataset_id}/chat/sessions/{session_id}/retry",
    response_model=ChatMessageResponse,
    summary="Retry assistant response generation for the latest user message",
)
def retry_message_endpoint(
    dataset_id: UUID,
    session_id: UUID,
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    """Retry generation for the latest user message without duplicating the user's message record."""
    try:
        return retry_last_chat_message(dataset_id=dataset_id, session_id=session_id, db=db)
    except ValueError as e:
        err_msg = str(e)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except (LLMUnavailableError, ConnectionError) as e:
        logger.warning(f"LLM provider unavailable error during retry: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Assistant is temporarily unavailable. Please try again.",
        )
    except (LLMTimeoutError, TimeoutError) as e:
        logger.warning(f"LLM provider timeout during retry: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Chat request timed out. Please try again.",
        )
    except Exception as e:
        logger.error(f"Unexpected error processing retry: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrying the assistant response.",
        )
