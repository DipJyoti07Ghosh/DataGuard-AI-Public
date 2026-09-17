"""
DataGuard AI — FastAPI Application Entry Point
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.health import router as health_router
from app.api.datasets import router as datasets_router
from app.api.profiling import router as profiling_router
from app.api.quality import router as quality_router


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging():
    """Configure structured logging for the application."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — runs startup and shutdown logic."""
    logger.info("=" * 60)
    logger.info(f"  {settings.app_name} starting up")
    logger.info(f"  Environment: {settings.app_env}")
    logger.info(f"  Debug: {settings.debug}")
    logger.info("=" * 60)

    # Ensure upload directory exists
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload directory: {settings.upload_path.resolve()}")

    # Attempt database connection (will succeed once PostgreSQL is set up)
    try:
        from app.database import init_database
        if init_database():
            logger.info("Database connected successfully.")
        else:
            logger.warning("Database not available — running without persistence.")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")

    yield  # Application runs here

    logger.info(f"{settings.app_name} shutting down.")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    description=(
        "Industry Data Profiling & Data Quality Assistant — "
        "An intelligent tool for dataset profiling, quality checks, "
        "PII detection, risk classification, drift detection, and "
        "AI-powered data quality assistance."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health_router)
app.include_router(datasets_router)
app.include_router(profiling_router)
app.include_router(quality_router, prefix="/api/datasets")


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint — redirects to API docs."""
    return {
        "application": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }
