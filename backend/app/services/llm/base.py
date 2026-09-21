"""
DataGuard AI — Phase 12A LLM Base Provider Interface

Defines the abstract interface, normalized generation results, and explicit provider
exceptions for provider-independent LLM orchestration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


# ===========================================================================
# Explicit Provider Exceptions (for deterministic fallback classification)
# ===========================================================================

class LLMProviderError(Exception):
    """Base exception for all LLM provider failures."""
    pass


class LLMConfigurationError(LLMProviderError):
    """Raised when provider configuration or API key is missing/invalid."""
    pass


class LLMAuthenticationError(LLMProviderError):
    """Raised when provider returns 401/403 authentication error."""
    pass


class LLMUnavailableError(LLMProviderError):
    """Raised when provider endpoint/daemon is unreachable or offline."""
    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when generation request exceeds timeout threshold."""
    pass


class LLMRateLimitError(LLMProviderError):
    """Raised when API quota or rate limit (429) is exceeded."""
    pass


class LLMModelNotFoundError(LLMProviderError):
    """Raised when configured model is not pulled or unavailable on provider."""
    pass


# ===========================================================================
# Normalized Generation Result
# ===========================================================================

@dataclass
class LLMGenerationResult:
    """Normalized output returned by any LLM provider."""
    content: str
    provider_name: str
    model_name: str
    fallback_occurred: bool = False
    latency_ms: float = 0.0
    token_usage: Optional[Dict[str, int]] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


# ===========================================================================
# Base Provider Interface
# ===========================================================================

class BaseLLMProvider(ABC):
    """Abstract base class for all LLM inference providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier for this provider ('gemini', 'ollama', etc.)."""
        pass

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Provider category ('HOSTED_API' or 'LOCAL_LLM')."""
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """
        Evaluate provider health status without making billable generation calls.
        Returns dictionary with:
        - available: bool
        - status: 'HEALTHY', 'DEGRADED', 'CONFIGURATION_ERROR', or 'UNAVAILABLE'
        - configured_model: str
        - message: str
        """
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Execute natural language completion given system prompt and grounded prompt.
        Raises explicit LLMProviderError subclasses on failure.
        """
        pass
