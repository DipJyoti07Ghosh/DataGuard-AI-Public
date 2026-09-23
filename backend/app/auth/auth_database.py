"""
DataGuard AI — Auth Database (PostgreSQL, 'auth' schema)

The users table lives in the same PostgreSQL database as datasets,
but in a dedicated schema called 'auth'. This allows the datasets table
to enforce a real foreign key on auth.users.id.
"""

import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from app.config import settings

logger = logging.getLogger(__name__)

AuthBase = declarative_base()

auth_engine = None
AuthSessionLocal = None


def init_auth_database() -> bool:
    """Initialize PostgreSQL engine for the auth schema."""
    global auth_engine, AuthSessionLocal
    try:
        # Import models so User registers with AuthBase.metadata
        from app.auth import models as _auth_models  # noqa: F401

        auth_engine = create_engine(
            settings.database_url,        # same DB as datasets
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )

        # Ensure schema exists before any table creation
        with auth_engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.auth_schema}"'))

        AuthSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=auth_engine
        )

        logger.info(
            f"Auth database (PostgreSQL schema '{settings.auth_schema}') initialized."
        )
        return True
    except Exception as e:
        logger.warning(f"Auth database init failed: {e}")
        auth_engine = None
        AuthSessionLocal = None
        return False


def get_auth_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a PostgreSQL session for auth."""
    global AuthSessionLocal
    if AuthSessionLocal is None:
        init_auth_database()
        if AuthSessionLocal is None:
            raise RuntimeError(
                "Auth database not connected. Verify PostgreSQL is running "
                "and DATABASE_URL is configured."
            )
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()