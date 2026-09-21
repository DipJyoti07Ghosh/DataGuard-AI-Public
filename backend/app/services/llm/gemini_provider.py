"""
DataGuard AI — Phase 12A Hosted Gemini LLM Provider

Implements Google Gemini API provider using official REST endpoints via httpx:
- Non-billable health checks (metadata verification)
- System instructions & grounded prompt framing
- Low temperature (0.1) & token bounding
- Explicit exception normalization for deterministic fallback
- Mock transport injection for automated tests
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


class GeminiProvider(BaseLLMProvider):
    """Google Gemini hosted LLM provider."""

    def __init__(
        self,
        api_key_or_settings: Any = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
        http_client: Optional[httpx.Client] = None,
        api_key: Optional[str] = None,
    ):
        target_key = api_key or api_key_or_settings
        if hasattr(target_key, "gemini_api_key"):
            cfg = target_key
            self.api_key = (cfg.gemini_api_key or "").strip()
            self.model_name = (model_name or cfg.gemini_model or "gemini-1.5-flash").strip()
            self.timeout = timeout or cfg.gemini_timeout_seconds
        else:
            cfg = settings
            self.api_key = (target_key or getattr(cfg, "gemini_api_key", None) or "").strip()
            self.model_name = (model_name or getattr(cfg, "gemini_model", "gemini-1.5-flash")).strip()
            self.timeout = timeout or getattr(cfg, "gemini_timeout_seconds", 30.0)
        self._custom_client = http_client
        self._base_api_url = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def provider_type(self) -> str:
        return "HOSTED_API"

    def _get_client(self) -> httpx.Client:
        if self._custom_client is not None:
            return self._custom_client
        return httpx.Client(timeout=self.timeout)

    def check_health(self) -> Dict[str, Any]:
        """
        Check Gemini API configuration and model availability without billable generation calls.
        """
        if not self.api_key:
            return {
                "available": False,
                "status": "CONFIGURATION_ERROR",
                "configured_model": self.model_name,
                "message": "GEMINI_API_KEY is not configured in backend/.env. Automatic fallback will use local Ollama.",
            }

        try:
            client = self._get_client()
            url = f"{self._base_api_url}/models/{self.model_name}?key={self.api_key}"
            resp = client.get(url)

            if resp.status_code == 200:
                return {
                    "available": True,
                    "status": "HEALTHY",
                    "configured_model": self.model_name,
                    "message": f"Hosted Gemini API connected and model '{self.model_name}' is ready.",
                }
            elif resp.status_code in (400, 401, 403):
                return {
                    "available": False,
                    "status": "CONFIGURATION_ERROR",
                    "configured_model": self.model_name,
                    "message": f"Gemini API authentication failed (HTTP {resp.status_code}). Check GEMINI_API_KEY.",
                }
            elif resp.status_code == 404:
                return {
                    "available": False,
                    "status": "DEGRADED",
                    "configured_model": self.model_name,
                    "message": f"Configured Gemini model '{self.model_name}' was not found on API.",
                }
            elif resp.status_code == 429:
                return {
                    "available": False,
                    "status": "DEGRADED",
                    "configured_model": self.model_name,
                    "message": "Gemini API rate limit or quota exceeded.",
                }
            else:
                return {
                    "available": False,
                    "status": "UNAVAILABLE",
                    "configured_model": self.model_name,
                    "message": f"Gemini API returned unexpected status HTTP {resp.status_code}.",
                }

        except httpx.ConnectError:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": "Cannot reach Google Gemini API endpoint (Network connection failure).",
            }
        except httpx.TimeoutException:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": f"Gemini API health check timed out after {self.timeout}s.",
            }
        except Exception as e:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": f"Error verifying Gemini API: {type(e).__name__}",
            }

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Execute natural language completion using Google Gemini REST API.
        """
        if not self.api_key:
            raise LLMConfigurationError(
                "GEMINI_API_KEY is not configured in backend/.env"
            )

        temp = temperature if temperature is not None else settings.ollama_temperature
        num_predict = max_tokens if max_tokens is not None else settings.ollama_max_tokens

        url = f"{self._base_api_url}/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "generationConfig": {
                "temperature": temp,
                "maxOutputTokens": num_predict,
                "thinkingConfig": {
                    "thinkingBudget": 0
                },
            },
        }

        client = self._get_client()
        start_time = time.time()
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"Submitting grounded prompt to Hosted Gemini API model '{self.model_name}' "
                    f"(attempt {attempt}/{max_attempts}, temp={temp}, max_tokens={num_predict})..."
                )
                resp = client.post(url, json=payload)
                elapsed = time.time() - start_time

                if resp.status_code in (401, 403):
                    raise LLMAuthenticationError(
                        f"Gemini API authentication failed (HTTP {resp.status_code})"
                    )
                elif resp.status_code == 404:
                    raise LLMModelNotFoundError(
                        f"Gemini model '{self.model_name}' not found on API"
                    )
                elif resp.status_code == 429:
                    if attempt < max_attempts:
                        wait_sec = 2.0 * attempt
                        logger.warning(f"Gemini rate-limited (HTTP 429). Retrying in {wait_sec}s...")
                        time.sleep(wait_sec)
                        continue
                    raise LLMRateLimitError(
                        "Gemini API rate limit or quota exceeded (HTTP 429)"
                    )
                elif resp.status_code in (500, 502, 503, 504):
                    if attempt < max_attempts:
                        wait_sec = 1.5 * attempt
                        logger.warning(
                            f"Gemini transient server error (HTTP {resp.status_code}). "
                            f"Retrying attempt {attempt + 1}/{max_attempts} in {wait_sec}s..."
                        )
                        time.sleep(wait_sec)
                        continue
                    raise LLMUnavailableError(
                        f"Gemini API server error (HTTP {resp.status_code})"
                    )
                elif resp.status_code != 200:
                    raise LLMProviderError(
                        f"Gemini API returned error HTTP {resp.status_code}: {resp.text[:200]}"
                    )

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.warning(f"Gemini returned empty candidates list after {elapsed:.2f}s")
                    raise LLMProviderError("Gemini returned empty candidate list")

                parts = candidates[0].get("content", {}).get("parts", [])
                text_chunks = [p.get("text", "") for p in parts if p.get("text")]
                answer = "".join(text_chunks).strip()
                if not answer:
                    logger.warning(f"Gemini returned empty text parts after {elapsed:.2f}s (candidates: {candidates})")
                    return "No response could be generated from the available analytical evidence."

                logger.info(f"Gemini generation completed in {elapsed:.2f}s (length={len(answer)} chars)")
                return answer

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < max_attempts:
                    wait_sec = 1.5 * attempt
                    logger.warning(f"Gemini network hiccup ({type(e).__name__}). Retrying in {wait_sec}s...")
                    time.sleep(wait_sec)
                    continue
                if isinstance(e, httpx.TimeoutException):
                    raise LLMTimeoutError(f"Gemini request timed out after {self.timeout}s")
                raise LLMUnavailableError(f"Cannot connect to Gemini API: {e}")
            except LLMProviderError:
                raise
            except Exception as e:
                logger.error(f"Unexpected error in GeminiProvider: {type(e).__name__} - {e}")
                raise LLMProviderError(f"Unexpected error during Gemini generation: {e}")
            logger.error(f"Unexpected error during Gemini inference: {type(e).__name__}")
            raise LLMProviderError(f"Gemini inference failed: {type(e).__name__}")
