"""
DataGuard AI — Auth API Router
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.auth_database import get_auth_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    GoogleLoginRequest,
    UserPublic,
    TokenResponse,
)
from app.auth.security import create_access_token
from app.auth.service import (
    register_user,
    authenticate_user,
    authenticate_with_google,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _build_token_response(user: User) -> TokenResponse:
    token = create_access_token(
        subject=str(user.id),                      # ← UUID → str
        extra_claims={"email": user.email, "name": user.name},
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserPublic.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_auth_db)):
    user = register_user(db, payload.name, payload.email, payload.password)
    return _build_token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_auth_db)):
    user = authenticate_user(db, payload.email, payload.password)
    return _build_token_response(user)


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_auth_db)):
    user = authenticate_with_google(db, payload.id_token)
    return _build_token_response(user)


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return UserPublic.model_validate(current_user)