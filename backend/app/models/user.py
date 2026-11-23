"""
DataGuard AI — User model (email/password + Google sign-in).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False, default="")
    password_hash = Column(String(255), nullable=True)  # null for Google-only users
    google_sub = Column(String(255), unique=True, nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
