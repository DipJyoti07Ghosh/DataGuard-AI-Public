"""
DataGuard AI — Auth Dependencies

Reusable FastAPI dependencies:
- get_current_user: extracts and validates Bearer JWT
- get_current_user_optional: same, but returns None if unauthenticated
"""

from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from uuid import UUID as _UUID
from sqlalchemy.orm import Session as _Session

from app.auth.auth_database import get_auth_db
from app.auth.models import User
from app.auth.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _load_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials],
    db: Session,
) -> Optional[User]:
    if credentials is None or not credentials.credentials:
        return None

    claims = decode_access_token(credentials.credentials)
    if not claims:
        return None

    user_id_str = claims.get("sub")
    if not user_id_str:
        return None

    # Convert JWT subject (str) back to UUID for the PostgreSQL query
    try:
        user_id = UUID(user_id_str)
    except (ValueError, TypeError):
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_auth_db),
) -> User:
    user = _load_user_from_token(credentials, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_auth_db),
) -> Optional[User]:
    return _load_user_from_token(credentials, db)

def assert_dataset_owner(
    db: _Session,
    dataset_id: _UUID,
    current_user: Optional[User],
) -> None:
    """
    Verify the current user owns the dataset. Raises HTTP 404 (not 403)
    to avoid leaking existence to unauthorized callers.
    Called by every dataset-scoped endpoint.
    """
    from app.models.dataset import Dataset
    from sqlalchemy import select

    ds = db.scalar(select(Dataset).where(Dataset.id == dataset_id))
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    if ds.user_id is None:
        # Legacy dataset (created before ownership scoping).
        # Policy: deny to everyone. Assign ownership via DB directly
        # if you need to recover such a dataset.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )

    if current_user is None or ds.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )