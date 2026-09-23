"""
DataGuard AI — Password Hashing & JWT Utilities

- bcrypt password hashing via passlib
- JWT sign/verify via python-jose
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

logger = logging.getLogger(__name__)

# bcrypt is intentionally slow — good against brute force
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    """Return bcrypt hash of a plaintext password."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    try:
        return pwd_context.verify(plain_password, password_hash)
    except Exception as e:
        logger.warning(f"Password verification error: {e}")
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(
    subject: str,
    extra_claims: Optional[Dict[str, Any]] = None,
    expires_minutes: Optional[int] = None,
) -> str:
    """
    Create a signed JWT.
    `subject` is normally the user id (string).
    """
    minutes = expires_minutes or settings.jwt_access_token_expire_minutes
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT. Returns claims dict or None."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        logger.debug(f"JWT decode failed: {e}")
        return None