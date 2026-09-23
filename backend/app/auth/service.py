"""
DataGuard AI — Auth Business Logic

Handles registration, login, and Google account provisioning.
"""

import logging
from typing import Optional

from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from app.config import settings
from app.auth.models import User
from app.auth.security import hash_password, verify_password

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_user(
    db: Session,
    name: str,
    email: str,
    password: str,
) -> User:
    """Create a new local (email+password) account."""
    email = email.strip().lower()

    # Uniqueness — a person cannot register the same email twice
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if existing.auth_provider == "google":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already registered with Google. Please sign in with Google.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Please log in.",
        )

    user = User(
        name=name.strip(),
        email=email,
        password_hash=hash_password(password),
        auth_provider="local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"Registered local user: {email} (id={user.id})")
    return user


# ---------------------------------------------------------------------------
# Login (email + password)
# ---------------------------------------------------------------------------
def authenticate_user(db: Session, email: str, password: str) -> User:
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if user.auth_provider == "google" and not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account uses Google Sign-In. Please continue with Google.",
        )

    if not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    logger.info(f"Local login success: {email}")
    return user


# ---------------------------------------------------------------------------
# Google OAuth login / auto-register
# ---------------------------------------------------------------------------
def authenticate_with_google(db: Session, google_id_token_str: str) -> User:
    """
    Verify Google ID token and return (or create) the corresponding User.

    Rules:
    - If a user with the same google_id exists → log them in.
    - If a user with the same email exists but different provider →
      link the google_id if it's a local account (password still works).
    - Else → create a new user with provider='google'.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured on the server.",
        )

    try:
        idinfo = google_id_token.verify_oauth2_token(
            google_id_token_str,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as e:
        logger.warning(f"Google token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token.",
        )

    google_sub = idinfo.get("sub")
    email = (idinfo.get("email") or "").strip().lower()
    name = idinfo.get("name") or email.split("@")[0]
    email_verified = idinfo.get("email_verified", False)

    if not google_sub or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account missing required fields.",
        )

    if not email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google email is not verified.",
        )

    # 1. Lookup by google_id
    user = db.query(User).filter(User.google_id == google_sub).first()
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled.",
            )
        logger.info(f"Google login success (existing google_id): {email}")
        return user

    # 2. Lookup by email
    user = db.query(User).filter(User.email == email).first()
    if user:
        # Link the Google identity to the existing account
        user.google_id = google_sub
        if user.auth_provider == "local" and not user.password_hash:
            user.auth_provider = "google"
        db.commit()
        db.refresh(user)
        logger.info(f"Linked Google account to existing user: {email}")
        return user

    # 3. Create brand-new Google user
    user = User(
        name=name,
        email=email,
        password_hash=None,
        auth_provider="google",
        google_id=google_sub,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"Registered new Google user: {email} (id={user.id})")
    return user