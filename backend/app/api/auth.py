"""
DataGuard AI — Auth API (email/password + Google sign-in)

POST /api/auth/register   {full_name, email, password}
POST /api/auth/login      {email, password}
POST /api/auth/google     {credential}   (Google ID token)
GET  /api/auth/me         Authorization: Bearer <token>
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    GoogleLoginRequest,
    LoginRequest,
    RegisterRequest,
    UserOut,
)
from app.services import auth_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name or "",
        has_password=bool(user.password_hash),
        has_google=bool(user.google_sub),
    )


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=svc.create_access_token(str(user.id), user.email),
        user=_user_out(user),
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = svc.normalize_email(payload.email)
    if not svc.is_valid_email(email):
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=svc.hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    db.refresh(user)
    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = svc.normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not svc.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return _auth_response(user)


@router.post("/google", response_model=AuthResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        info = svc.verify_google_credential(payload.credential)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # invalid / expired token, network error
        logger.warning(f"Google token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Google sign-in failed. Please try again.")

    email = svc.normalize_email(info["email"])
    sub = info["sub"]
    user = db.query(User).filter(User.google_sub == sub).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_sub = sub  # link Google to the existing email account
        else:
            user = User(
                email=email,
                full_name=info.get("name") or email.split("@")[0],
                google_sub=sub,
            )
            db.add(user)
        db.commit()
        db.refresh(user)
    return _auth_response(user)


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")
    claims = svc.decode_access_token(authorization.split(" ", 1)[1].strip())
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except (ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid token.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists.")
    return user


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)
