"""
DataGuard AI — Phase 12A LLM Provider Manager

Orchestrates automatic priority-based LLM provider fallback:
- Primary: Hosted Gemini API
- Fallback: Local Ollama LLM
- Strict fallback eligibility policy (transport, quota, timeout, config)
- Normalized LLMGenerationResult with authoritative fallback_occurred tracking
"""

import time
import logging
from typing import Dict, Any, List, Optional

from app.config import settings
from app.schemas.assistant import AssistantHealthResponse
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

logger = logging.getLogger(__name__)


class ProviderManager:
    """Manages LLM provider priority ordering and automatic error fallback."""

    def __init__(
        self,
        settings_instance: Optional[Any] = None,
        gemini_provider: Optional[BaseLLMProvider] = None,
        groq_provider: Optional[BaseLLMProvider] = None,
        huggingface_provider: Optional[BaseLLMProvider] = None,
        ollama_provider: Optional[BaseLLMProvider] = None,
        provider_order: Optional[List[str]] = None,
        providers_override: Optional[List[BaseLLMProvider]] = None,
    ):
        self._settings = settings_instance or settings
        self._providers_override = providers_override
        if providers_override:
            self._providers_map = {p.provider_name.lower(): p for p in providers_override}
            self._order_override = provider_order or [p.provider_name.lower() for p in providers_override]
        else:
            self._gemini = gemini_provider or GeminiProvider(self._settings)
            self._groq = groq_provider or GroqProvider(self._settings)
            self._huggingface = huggingface_provider or HuggingFaceProvider(self._settings)
            self._ollama = ollama_provider or OllamaProvider(self._settings)
            self._providers_map = {
                "gemini": self._gemini,
                "groq": self._groq,
                "huggingface": self._huggingface,
                "ollama": self._ollama,
            }
            self._order_override = provider_order

    @property
    def provider_order(self) -> List[str]:
        if self._order_override is not None:
            return self._order_override
        return self._settings.llm_provider_order_list

    def get_provider(self, name: str) -> Optional[BaseLLMProvider]:
        return self._providers_map.get(name.strip().lower())

    def get_active_providers(self) -> List[BaseLLMProvider]:
        """Return list of instantiated providers in configured priority order."""
        res = []
        for name in self.provider_order:
            p = self.get_provider(name)
            if p:
                res.append(p)
        return res

    def check_health(self) -> AssistantHealthResponse:
        """
        Evaluate provider subsystem health across configured provider order without billable calls.
        """
        order = self.provider_order
        primary_name = order[0] if order else "gemini"
        
        details: Dict[str, Any] = {}
        usable_providers: List[str] = []

        for p_name in order:
            provider = self.get_provider(p_name)
            if provider:
                h = provider.check_health()
                details[p_name] = {
                    "provider_type": provider.provider_type,
                    "status": h.get("status", "UNKNOWN"),
                    "available": h.get("available", False),
                    "configured_model": h.get("configured_model", ""),
                    "message": h.get("message", ""),
                }
                if h.get("available", False):
                    usable_providers.append(p_name)

        primary_available = primary_name in usable_providers

        if primary_available:
            overall_status = "HEALTHY"
            active_fallback = None
            msg = f"Primary provider '{primary_name}' is ready for inference."
        elif usable_providers:
            overall_status = "DEGRADED"
            active_fallback = usable_providers[0]
            msg = (
                f"Primary provider '{primary_name}' is unavailable. "
                f"Automatic fallback active on '{active_fallback}'."
            )
        else:
            overall_status = "UNAVAILABLE"
            active_fallback = None
            msg = "All configured LLM providers are currently unavailable or unconfigured."

        return AssistantHealthResponse(
            status=overall_status,
            primary_provider=primary_name,
            active_fallback=active_fallback,
            available_providers=usable_providers,
            provider_details=details,
            message=msg,
        )

    def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMGenerationResult:
        """
        Attempt generation using providers in configured priority order.
        Executes automatic fallback on eligible provider errors.
        """
        order = self.provider_order
        attempt_errors: List[str] = []
        primary_name = order[0] if order else "gemini"

        for idx, p_name in enumerate(order):
            provider = self.get_provider(p_name)
            if not provider:
                continue

            fallback_flag = (idx > 0)
            start_time = time.time()

            try:
                logger.info(
                    f"Attempting inference on provider [{idx + 1}/{len(order)}]: '{p_name}' "
                    f"(type={provider.provider_type}, fallback={fallback_flag})..."
                )
                raw_result = provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                elapsed_ms = round((time.time() - start_time) * 1000, 2)

                logger.info(
                    f"Inference succeeded on provider '{p_name}' in {elapsed_ms}ms "
                    f"(fallback_occurred={fallback_flag})"
                )

                if isinstance(raw_result, LLMGenerationResult):
                    # Copy and enforce accurate fallback flag
                    return LLMGenerationResult(
                        content=raw_result.content,
                        provider_name=p_name,
                        model_name=raw_result.model_name or getattr(provider, "model_name", "unknown"),
                        fallback_occurred=fallback_flag,
                        latency_ms=raw_result.latency_ms or elapsed_ms,
                        token_usage=raw_result.token_usage,
                    )

                # Fetch model name safely
                model_name = getattr(provider, "model_name", "unknown")

                return LLMGenerationResult(
                    content=str(raw_result),
                    provider_name=p_name,
                    model_name=model_name,
                    fallback_occurred=fallback_flag,
                    latency_ms=elapsed_ms,
                )

            except (
                LLMConfigurationError,
                LLMAuthenticationError,
                LLMUnavailableError,
                LLMTimeoutError,
                LLMRateLimitError,
                LLMModelNotFoundError,
            ) as e:
                err_summary = f"{p_name} error: {type(e).__name__} - {e}"
                logger.warning(
                    f"Provider '{p_name}' failed with fallback-eligible error: {e}. "
                    f"Checking for next provider in priority order..."
                )
                attempt_errors.append(err_summary)
                continue

            except LLMProviderError as e:
                err_summary = f"{p_name} error: {e}"
                logger.warning(f"Provider '{p_name}' failed: {e}. Attempting fallback...")
                attempt_errors.append(err_summary)
                continue

            except Exception as e:
                # Unexpected error -> do not hide, but record and try next provider if available
                logger.error(f"Unexpected error in provider '{p_name}': {type(e).__name__} - {e}")
                attempt_errors.append(f"{p_name}: {type(e).__name__}")
                continue

        # If all providers failed
        combined_err = " | ".join(attempt_errors) if attempt_errors else "No providers available"
        logger.error(f"All configured LLM providers failed: {combined_err}")
        raise LLMUnavailableError(
            f"AI Assistant is temporarily unavailable. All configured LLM providers failed: {combined_err}"
        )


# Alias for backward compatibility / explicit naming
LLMProviderManager = ProviderManager

# Singleton instance
_default_provider_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """Retrieve the global ProviderManager singleton."""
    global _default_provider_manager
    if _default_provider_manager is None:
        _default_provider_manager = ProviderManager()
    return _default_provider_manager

