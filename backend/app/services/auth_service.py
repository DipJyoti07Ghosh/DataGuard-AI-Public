"""
DataGuard AI — Auth helpers: password hashing, JWT, Google token check.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from app.config import settings

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def verify_google_credential(credential: str) -> dict:
    """Verify a Google ID token. Raises ValueError if invalid."""
    if not settings.google_client_id:
        raise ValueError("Google sign-in is not configured on the server.")
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    info = id_token.verify_oauth2_token(
        credential, google_requests.Request(), settings.google_client_id
    )
    if not info.get("email") or not info.get("email_verified", False):
        raise ValueError("Google account email is not verified.")
    return info
