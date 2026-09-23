"""
DataGuard AI — Phase 11 Embedding Service

Provides an abstract interface and pre-warmed FastEmbed implementation
using BAAI/bge-small-en-v1.5 (384-dimensional dense sentence embeddings).
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for RAG embedding generation."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single query string into a dense float vector."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of document texts into a list of dense float vectors."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return embedding vector dimension."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier (e.g. 'fastembed')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return model name (e.g. 'BAAI/bge-small-en-v1.5')."""
        pass

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Return model version tag."""
        pass


class FastEmbedProvider(EmbeddingProvider):
    """
    Production embedding provider using FastEmbed ONNX runtime.
    Model: BAAI/bge-small-en-v1.5 (384-dimensional dense vector).
    Fast, local CPU execution, deterministic, zero network call during inference.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self._model_name = model_name
        self._dimension = 384
        self._model_version = "1.5"
        self._model = None
        self._init_model()

    def _init_model(self) -> None:
        try:
            from fastembed import TextEmbedding
            logger.info(f"Loading FastEmbed model '{self._model_name}'...")
            self._model = TextEmbedding(model_name=self._model_name)
            # Pre-warm with a dummy embedding to ensure ONNX session is ready
            _ = list(self._model.embed(["DataGuard AI pre-warm"]))
            logger.info(f"FastEmbed model '{self._model_name}' loaded and pre-warmed successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize FastEmbed model '{self._model_name}': {e}")
            raise RuntimeError(
                f"Embedding provider initialization failed: {e}. "
                "Ensure 'fastembed' is installed and model weights are accessible."
            )

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return "fastembed"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    def embed_text(self, text: str) -> List[float]:
        if not text or not text.strip():
            # Return zero vector or placeholder if empty
            return [0.0] * self._dimension
        if self._model is None:
            self._init_model()
        
        embeddings = list(self._model.embed([text]))
        vec = [float(x) for x in embeddings[0]]
        if len(vec) != self._dimension:
            raise ValueError(f"Expected embedding dimension {self._dimension}, got {len(vec)}")
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self._model is None:
            self._init_model()

        clean_texts = [t if t and t.strip() else "empty document" for t in texts]
        embeddings = list(self._model.embed(clean_texts))
        result = []
        for emb in embeddings:
            vec = [float(x) for x in emb]
            if len(vec) != self._dimension:
                raise ValueError(f"Expected embedding dimension {self._dimension}, got {len(vec)}")
            result.append(vec)
        return result


# Singleton instance
_embedding_provider_instance: Optional[EmbeddingProvider] = None


def get_embedding_provider() -> EmbeddingProvider:
    """Retrieve or initialize the active singleton embedding provider."""
    global _embedding_provider_instance
    if _embedding_provider_instance is None:
        _embedding_provider_instance = FastEmbedProvider()
    return _embedding_provider_instance
