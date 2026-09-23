"""
DataGuard AI — Chat & Conversational Intelligence Pydantic Schemas

Validates chat session creation, message submission, scope integrity, and response serialization.
Strictly disallows client injection of system roles or provider overrides.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ChatScope(str, Enum):
    """Scope constraint for a chat session."""
    VERSION = "VERSION"
    COMPARISON = "COMPARISON"
    DATASET = "DATASET"


class ChatSessionCreate(BaseModel):
    """Payload for creating a new persistent chat session."""
    scope: ChatScope = Field(default=ChatScope.VERSION, description="Operational scope")
    version_id: Optional[UUID] = Field(default=None, description="Required for VERSION scope")
    comparison_id: Optional[UUID] = Field(default=None, description="Required for COMPARISON scope")
    title: Optional[str] = Field(default=None, max_length=255, description="Optional custom session title")


class ChatSessionUpdate(BaseModel):
    """Payload for updating session metadata (e.g. renaming)."""
    title: str = Field(..., min_length=1, max_length=255, description="New session title")


class ChatMessageCreate(BaseModel):
    """
    User message submission payload.
    Strictly restricts user inputs to text content with an 8000-character ceiling.
    Prevents role spoofing or provider manipulation.
    """
    content: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="User message text prompt (max 8000 chars)",
    )


class ChatMessageResponse(BaseModel):
    """Serialized conversational message representation."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    role: str = Field(..., description="'user', 'assistant', or 'system'")
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    fallback_occurred: bool = False
    grounded: bool = True
    sources: Optional[List[Dict[str, Any]]] = None
    warnings: Optional[List[str]] = None
    created_at: datetime


class ChatSessionResponse(BaseModel):
    """Summary of a chat session for list endpoints."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    version_id: Optional[UUID] = None
    comparison_id: Optional[UUID] = None
    scope: ChatScope
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatSessionDetailResponse(BaseModel):
    """Detailed chat session representation including full message history."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    version_id: Optional[UUID] = None
    comparison_id: Optional[UUID] = None
    scope: ChatScope
    title: str
    messages: List[ChatMessageResponse] = []
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    """List container for chat sessions."""
    sessions: List[ChatSessionResponse]
    total: int
