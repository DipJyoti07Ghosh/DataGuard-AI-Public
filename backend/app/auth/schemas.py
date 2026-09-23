"""
DataGuard AI — Auth Pydantic Schemas

Request/response contracts for register, login, Google OAuth, and /me.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(..., min_length=10)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class UserPublic(BaseModel):
    """Safe user data returned to the frontend."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID                    # ← UUID instead of str
    name: str
    email: EmailStr
    auth_provider: str
    created_at: datetime


class TokenResponse(BaseModel):
    """JWT access token + user info."""
    access_token: str
    token_type: str = "bearer"
    user: UserPublic