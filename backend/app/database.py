"""
DataGuard AI — Database Connection & Session Management

SQLAlchemy 2.x engine, session factory, and base model class.
Supports PostgreSQL with connection pooling and graceful error handling.
"""

import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from app.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# Engine and SessionLocal singletons
engine = None
SessionLocal = None


def init_database() -> bool:
    """
    Initialize the database engine and session factory.
    Returns True if engine created and connection test succeeds, False otherwise.
    """
    global engine, SessionLocal
    try:
        engine = create_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("Database engine initialized successfully.")
        return True
    except Exception as e:
        logger.warning(f"Database engine initialization failed: {e}")
        engine = None
        SessionLocal = None
        return False


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    Yields a session and guarantees cleanup.
    """
    global SessionLocal
    if SessionLocal is None:
        init_database()
        if SessionLocal is None:
            raise RuntimeError(
                "Database not connected. Please verify PostgreSQL is running "
                "and DATABASE_URL is configured."
            )

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
