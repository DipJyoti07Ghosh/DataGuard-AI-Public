"""
DataGuard AI — Hosted Groq LLM Provider

Integrates the ultra-fast Groq Cloud Inference API as a hosted cloud provider.
Uses OpenAI-compatible chat completions endpoint:
- Endpoint: https://api.groq.com/openai/v1/chat/completions
- Default Model: llama-3.1-8b-instant (or llama-3.3-70b-versatile)
- Low latency, high throughput, zero raw data leakage
"""

import time
import logging
from typing import Dict, Any, Optional
import httpx

from app.config import settings
from app.services.llm.base import (
    BaseLLMProvider,
    LLMProviderError,
    LLMConfigurationError,
    LLMAuthenticationError,
    LLMUnavailableError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMModelNotFoundError,
)

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    """Groq hosted cloud inference LLM provider."""

    def __init__(
        self,
        api_key_or_settings: Any = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
        http_client: Optional[httpx.Client] = None,
        api_key: Optional[str] = None,
    ):
        target_key = api_key or api_key_or_settings
        if hasattr(target_key, "groq_api_key"):
            cfg = target_key
            self.api_key = (cfg.groq_api_key or "").strip()
            self.model_name = (model_name or getattr(cfg, "groq_model", "llama-3.1-8b-instant") or "llama-3.1-8b-instant").strip()
            self.timeout = timeout or getattr(cfg, "groq_timeout_seconds", 30.0)
        else:
            cfg = settings
            self.api_key = (
                target_key
                or getattr(cfg, "groq_api_key", None)
                or ""
            ).strip()
            self.model_name = (
                model_name
                or getattr(cfg, "groq_model", "llama-3.1-8b-instant")
            ).strip()
            self.timeout = timeout or getattr(cfg, "groq_timeout_seconds", 30.0)

        self._custom_client = http_client
        self._endpoint_url = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def provider_type(self) -> str:
        return "HOSTED_API"

    def _get_client(self) -> httpx.Client:
        if self._custom_client is not None:
            return self._custom_client
        return httpx.Client(timeout=self.timeout)

    def check_health(self) -> Dict[str, Any]:
        """
        Check Groq API key and endpoint health without billable generation calls.
        """
        if not self.api_key:
            return {
                "available": False,
                "status": "CONFIGURATION_ERROR",
                "configured_model": self.model_name,
                "message": "GROQ_API_KEY is not configured in backend/.env.",
            }

        try:
            client = self._get_client()
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = client.get("https://api.groq.com/openai/v1/models", headers=headers)

            if resp.status_code == 200:
                return {
                    "available": True,
                    "status": "HEALTHY",
                    "configured_model": self.model_name,
                    "message": f"Groq connected and model '{self.model_name}' is ready for inference.",
                }
            elif resp.status_code in (401, 403):
                return {
                    "available": False,
                    "status": "CONFIGURATION_ERROR",
                    "configured_model": self.model_name,
                    "message": f"Groq authentication rejected with HTTP {resp.status_code}. Verify GROQ_API_KEY.",
                }
            else:
                return {
                    "available": False,
                    "status": "DEGRADED",
                    "configured_model": self.model_name,
                    "message": f"Groq returned HTTP {resp.status_code} during health check.",
                }

        except httpx.ConnectError:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": "Unable to connect to Groq API endpoint.",
            }
        except httpx.TimeoutException:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": f"Groq health check timed out after {self.timeout}s.",
            }
        except Exception as e:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": f"Error checking Groq status: {type(e).__name__}",
            }

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Execute natural language completion using Groq chat completions API.
        """
        if not self.api_key:
            raise LLMConfigurationError(
                "GROQ_API_KEY is not configured in backend/.env. Cannot invoke Groq inference."
            )

        temp = temperature if temperature is not None else 0.1
        tokens = max_tokens if max_tokens is not None else 1024

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        client = self._get_client()
        start_time = time.time()

        try:
            logger.info(
                f"Submitting grounded prompt to Groq model '{self.model_name}' "
                f"(temp={temp}, max_tokens={tokens})..."
            )
            response = client.post(self._endpoint_url, json=payload, headers=headers)
            elapsed = time.time() - start_time

            if response.status_code == 401 or response.status_code == 403:
                raise LLMAuthenticationError(
                    f"Groq API rejected request with HTTP {response.status_code}: {response.text[:200]}"
                )
            elif response.status_code == 429:
                raise LLMRateLimitError(
                    f"Groq rate limit exceeded (HTTP 429): {response.text[:200]}"
                )
            elif response.status_code == 404:
                raise LLMModelNotFoundError(
                    f"Groq model '{self.model_name}' not found: {response.text[:200]}"
                )
            elif response.status_code in (500, 502, 503):
                raise LLMUnavailableError(
                    f"Groq server error HTTP {response.status_code}: {response.text[:200]}"
                )
            elif response.status_code != 200:
                raise LLMProviderError(
                    f"Groq returned HTTP {response.status_code}: {response.text[:200]}"
                )

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMProviderError("Groq returned 200 OK but no choices in response.")

            message_obj = choices[0].get("message", {})
            content = message_obj.get("content", "").strip()

            if not content:
                logger.warning(f"Groq returned empty text after {elapsed:.2f}s")
                return "No response could be generated from the available analytical evidence."

            logger.info(f"Groq generation completed in {elapsed:.2f}s (length={len(content)} chars)")
            return content

        except httpx.ConnectError as e:
            logger.warning(f"Groq connection failure: {e}")
            raise LLMUnavailableError(f"Cannot connect to Groq endpoint: {e}")
        except httpx.TimeoutException as e:
            logger.warning(f"Groq request timed out after {self.timeout}s: {e}")
            raise LLMTimeoutError(f"Groq request timed out after {self.timeout}s.")
        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Groq inference: {type(e).__name__} - {e}")
            raise LLMProviderError(f"Groq generation failed: {type(e).__name__}")
