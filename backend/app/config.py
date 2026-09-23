"""
DataGuard AI — Application Configuration

Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = Field(default="DataGuard AI")
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # Backend
    backend_host: str = Field(default="0.0.0.0")
    backend_port: int = Field(default=8000)
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    # PostgreSQL — datasets AND auth in the SAME database
    database_url: str = Field(
        default="postgresql+psycopg2://dataguard:dataguard_dev@localhost:5432/dataguard_ai"
    )
    auth_schema: str = Field(
        default="auth",
        description="PostgreSQL schema where the users table lives",
    )

    # ---------------------------------------------------------------
    # JWT Authentication
    # ---------------------------------------------------------------
    jwt_secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_use_openssl_rand_hex_32"
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=60 * 24 * 7)

    # ---------------------------------------------------------------
    # Google OAuth
    # ---------------------------------------------------------------
    google_client_id: str = Field(default="")

    # File Storage
    upload_dir: str = Field(default="./uploads")
    max_upload_size_mb: int = Field(default=100)

    # LLM Provider Architecture (Phase 12A)
    llm_provider_order: str = Field(default="gemini,huggingface,ollama")

    # Gemini (Primary Hosted Provider)
    gemini_api_key: Optional[str] = Field(default=None)
    gemini_model: str = Field(default="gemini-2.0-flash")
    gemini_timeout_seconds: float = Field(default=60.0)

    # Hugging Face (Secondary Hosted Serverless Provider)
    huggingface_api_token: Optional[str] = Field(default=None)
    huggingface_model: str = Field(default="Qwen/Qwen2.5-7B-Instruct")
    huggingface_timeout_seconds: float = Field(default=60.0)

    # Groq (Hosted Fast Inference Provider)
    groq_api_key: Optional[str] = Field(default=None)
    groq_model: str = Field(default="llama-3.1-8b-instant")
    groq_timeout_seconds: float = Field(default=30.0)

    # Ollama (Fallback Local Provider)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.2:1b")
    ollama_temperature: float = Field(default=0.1)
    ollama_timeout_seconds: float = Field(default=120.0)
    ollama_max_tokens: int = Field(default=1024)

    # RAG (Phase 11+) & Assistant
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")
    embedding_dimension: int = Field(default=384)
    rag_chunk_size: int = Field(default=500)
    rag_chunk_overlap: int = Field(default=50)
    rag_top_k: int = Field(default=8)
    rag_min_similarity: float = Field(default=0.35)
    assistant_default_top_k: int = Field(default=8)

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        protected_namespaces=(),
    )

    @property
    def llm_provider_order_list(self) -> list[str]:
        """
        Parse, normalize, deduplicate and validate configured provider order.
        Supported providers: 'gemini', 'groq', 'huggingface', 'ollama'.
        """
        supported = {"gemini", "groq", "huggingface", "ollama"}
        order = []
        for raw in self.llm_provider_order.split(","):
            p = raw.strip().lower()
            if p in supported and p not in order:
                order.append(p)
        return order or ["gemini", "groq", "huggingface", "ollama"]

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def upload_path(self) -> Path:
        """Resolved upload directory path."""
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_upload_size_bytes(self) -> int:
        """Max upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024


# Singleton settings instance
settings = Settings()


def get_settings() -> Settings:
    """Return the global settings instance."""
    return settings

