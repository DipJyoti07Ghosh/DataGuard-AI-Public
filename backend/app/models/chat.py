"""
DataGuard AI — Chat & Conversational Intelligence SQLAlchemy Models

Defines persistent chat session and message entities.
Enforces strict dataset-scoping, foreign key integrity, and cascade deletion.
Zero raw PII and zero raw dataset rows are ever persisted in message records.

Note on cross-base FK to auth.users:
The `auth` schema tables live in a separate SQLAlchemy declarative base (AuthBase).
SQLAlchemy cannot resolve `ForeignKey("auth.users.id")` from the main Base without
merging the metadata registries. The physical FK constraint is enforced at the
PostgreSQL level (created by migration 011_add_auth_and_user_id). At the ORM level,
`user_id` is mapped as a plain UUID column.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class ChatSession(Base):
    """
    Persistent conversational session scoped to a specific dataset and optional version or comparison.
    Scope locking is strictly maintained after creation.
    """

    __tablename__ = "chat_sessions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    dataset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Dataset this chat session is bound to",
    )
    version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Optional specific dataset version scope (for VERSION scope)",
    )
    comparison_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dataset_comparisons.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Optional dataset comparison scope (for COMPARISON scope)",
    )
    user_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        doc="Owner user (auth.users.id). FK enforced at the DB level; "
            "not declared here because auth.users lives in a separate "
            "SQLAlchemy declarative base (AuthBase).",
    )
    scope = Column(
        String(32),
        nullable=False,
        default="VERSION",
        doc="Session scope: VERSION, COMPARISON, or DATASET",
    )
    title = Column(
        String(255),
        nullable=False,
        default="New Chat",
        doc="User-facing conversation title, deterministic and PII-safe",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    dataset = relationship("Dataset", back_populates="chat_sessions")
    version = relationship("DatasetVersion", backref="chat_sessions")
    comparison = relationship("DatasetComparison", backref="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("scope IN ('VERSION', 'COMPARISON', 'DATASET')", name="chk_chat_session_scope"),
        Index("ix_chat_sessions_dataset_updated", "dataset_id", "updated_at"),
        Index("ix_chat_sessions_dataset_created", "dataset_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ChatSession id={self.id} dataset_id={self.dataset_id} "
            f"scope={self.scope} user_id={self.user_id} title='{self.title}'>"
        )


class ChatMessage(Base):
    """
    Individual message in a conversational thread.
    Contains sanitized assistant responses, authoritative source citations, and provider metadata.
    """

    __tablename__ = "chat_messages"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Chat session this message belongs to",
    )
    role = Column(
        String(32),
        nullable=False,
        doc="Message role: 'user', 'assistant', or 'system' (backend-assigned only)",
    )
    content = Column(
        Text,
        nullable=False,
        doc="Sanitized message content (no raw PII or raw rows)",
    )
    provider = Column(
        String(64),
        nullable=True,
        doc="LLM provider name that generated the response (e.g., 'gemini', 'huggingface', 'ollama')",
    )
    model = Column(
        String(128),
        nullable=True,
        doc="Model identifier used for generation",
    )
    fallback_occurred = Column(
        Boolean,
        default=False,
        nullable=False,
        doc="True if generation fell back to a secondary provider",
    )
    grounded = Column(
        Boolean,
        default=True,
        nullable=False,
        doc="True if answer is backed by factual grounded Phase 11 RAG evidence",
    )
    sources = Column(
        JSONB,
        nullable=True,
        doc="Authoritative server-side RAG document citations",
    )
    warnings = Column(
        JSONB,
        nullable=True,
        doc="Context assembly or retrieval warnings",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="chk_chat_message_role"),
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} session_id={self.session_id} role={self.role} provider={self.provider}>"