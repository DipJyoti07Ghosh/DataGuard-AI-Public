"""
DataGuard AI — Health Check Router

Provides system health and readiness endpoints.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("")
async def health_check():
    """
    Basic health check — confirms the API is running.
    Returns application info and component status.
    """
    # Check database connectivity
    db_status = "not_configured"
    try:
        from app.database import engine
        if engine is not None:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_status = "connected"
        else:
            db_status = "not_initialized"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check Ollama connectivity
    ollama_status = "not_configured"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                ollama_status = "connected"
            else:
                ollama_status = "unreachable"
    except Exception:
        ollama_status = "unavailable"

    return {
        "status": "healthy",
        "application": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "api": "running",
            "database": db_status,
            "ollama": ollama_status,
        },
    }
