"""
DataGuard AI — Phase 12A LLM Providers Package
"""

from app.services.llm.base import (
    BaseLLMProvider,
    LLMGenerationResult,
    LLMProviderError,
    LLMConfigurationError,
    LLMAuthenticationError,
    LLMUnavailableError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMModelNotFoundError,
)
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.groq_provider import GroqProvider
from app.services.llm.huggingface_provider import HuggingFaceProvider
from app.services.llm.ollama_provider import OllamaProvider
from app.services.llm.provider_manager import (
    ProviderManager,
    LLMProviderManager,
    get_provider_manager,
)

__all__ = [
    "BaseLLMProvider",
    "LLMGenerationResult",
    "LLMProviderError",
    "LLMConfigurationError",
    "LLMAuthenticationError",
    "LLMUnavailableError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMModelNotFoundError",
    "GeminiProvider",
    "GroqProvider",
    "HuggingFaceProvider",
    "OllamaProvider",
    "ProviderManager",
    "LLMProviderManager",
    "get_provider_manager",
]
