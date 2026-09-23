"""
DataGuard AI — User Model (PostgreSQL 'auth' schema)

The users table lives in a dedicated PostgreSQL schema 'auth',
which allows a real foreign key from datasets.user_id → auth.users.id.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.auth.auth_database import AuthBase
from app.config import settings


class User(AuthBase):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email_provider", "email", "auth_provider"),
        {"schema": settings.auth_schema},   # places table in 'auth' schema
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)

    # Null for Google-only accounts
    password_hash = Column(String(255), nullable=True)

    # 'local' | 'google'
    auth_provider = Column(String(20), nullable=False, default="local")

    # Google subject ID (unique if present)
    google_id = Column(String(64), nullable=True, unique=True)

    is_active = Column(Boolean, nullable=False, default=True)

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

    def __repr__(self) -> str:
        return f"<User id={self.id} email='{self.email}' provider='{self.auth_provider}'>"