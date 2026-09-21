"""
DataGuard AI — Phase 12A Hugging Face Hosted Inference Provider

Integrates the free Hugging Face Serverless Inference API as a secondary
cloud LLM provider. Uses OpenAI-compatible chat completions routing:
- Primary Endpoint: https://router.huggingface.co/hf-inference/v1/chat/completions
- Fallback Endpoint: https://api-inference.huggingface.co/models/{model_name}
- Default Model: Qwen/Qwen2.5-7B-Instruct (or meta-llama/Llama-3.2-3B-Instruct)
- Grounded context isolation with strict privacy boundaries (zero raw data)
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


class HuggingFaceProvider(BaseLLMProvider):
    """Hugging Face hosted serverless inference LLM provider."""

    def __init__(
        self,
        api_token_or_settings: Any = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
        http_client: Optional[httpx.Client] = None,
        api_token: Optional[str] = None,
    ):
        target_token = api_token or api_token_or_settings
        if hasattr(target_token, "huggingface_api_token"):
            cfg = target_token
            self.api_token = (cfg.huggingface_api_token or "").strip()
            self.model_name = (model_name or cfg.huggingface_model or "meta-llama/Llama-3.3-70B-Instruct").strip()
            self.timeout = timeout or cfg.huggingface_timeout_seconds
        else:
            cfg = settings
            self.api_token = (
                target_token
                or getattr(cfg, "huggingface_api_token", None)
                or ""
            ).strip()
            self.model_name = (
                model_name
                or getattr(cfg, "huggingface_model", "meta-llama/Llama-3.3-70B-Instruct")
            ).strip()
            self.timeout = timeout or getattr(cfg, "huggingface_timeout_seconds", 60.0)

        self._custom_client = http_client
        self._router_url = "https://router.huggingface.co/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "huggingface"

    @property
    def provider_type(self) -> str:
        return "HOSTED_API"

    def _get_client(self) -> httpx.Client:
        if self._custom_client is not None:
            return self._custom_client
        return httpx.Client(timeout=self.timeout)

    def check_health(self) -> Dict[str, Any]:
        """
        Check Hugging Face token and model availability without billable generation calls.
        """
        if not self.api_token:
            return {
                "available": False,
                "status": "CONFIGURATION_ERROR",
                "configured_model": self.model_name,
                "message": "HUGGINGFACE_API_TOKEN is not configured in backend/.env.",
            }

        try:
            client = self._get_client()
            headers = {"Authorization": f"Bearer {self.api_token}"}
            url = f"https://huggingface.co/api/models/{self.model_name}"
            resp = client.get(url, headers=headers)

            if resp.status_code == 200:
                return {
                    "available": True,
                    "status": "HEALTHY",
                    "configured_model": self.model_name,
                    "message": f"Hugging Face API connected and model '{self.model_name}' is verified.",
                }
            elif resp.status_code in (401, 403):
                return {
                    "available": False,
                    "status": "CONFIGURATION_ERROR",
                    "configured_model": self.model_name,
                    "message": f"Hugging Face token authentication failed (HTTP {resp.status_code}). Check HUGGINGFACE_API_TOKEN.",
                }
            elif resp.status_code == 404:
                return {
                    "available": False,
                    "status": "DEGRADED",
                    "configured_model": self.model_name,
                    "message": f"Hugging Face model '{self.model_name}' was not found.",
                }
            elif resp.status_code == 429:
                return {
                    "available": False,
                    "status": "DEGRADED",
                    "configured_model": self.model_name,
                    "message": "Hugging Face inference rate limit exceeded.",
                }
            else:
                return {
                    "available": False,
                    "status": "UNAVAILABLE",
                    "configured_model": self.model_name,
                    "message": f"Hugging Face API returned HTTP {resp.status_code}.",
                }

        except httpx.ConnectError:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": "Cannot connect to Hugging Face API endpoint (network failure).",
            }
        except httpx.TimeoutException:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": f"Hugging Face health check timed out after {self.timeout}s.",
            }
        except Exception as e:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": f"Error verifying Hugging Face API: {type(e).__name__}",
            }

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Execute natural language completion using Hugging Face Serverless Chat Completions API.
        """
        if not self.api_token:
            raise LLMConfigurationError(
                "HUGGINGFACE_API_TOKEN is not configured in backend/.env"
            )

        temp = temperature if temperature is not None else settings.ollama_temperature
        num_predict = max_tokens if max_tokens is not None else settings.ollama_max_tokens

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": max(0.01, min(1.0, temp)),
            "max_tokens": num_predict,
        }

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        client = self._get_client()
        start_time = time.time()
        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    f"Submitting grounded prompt to Hosted Hugging Face model '{self.model_name}' "
                    f"(attempt {attempt}/{max_attempts}, temp={temp}, max_tokens={num_predict})..."
                )
                resp = client.post(self._router_url, json=payload, headers=headers)
                elapsed = time.time() - start_time

                if resp.status_code in (401, 403):
                    raise LLMAuthenticationError(
                        f"Hugging Face token authentication failed (HTTP {resp.status_code})"
                    )
                elif resp.status_code == 404:
                    raise LLMModelNotFoundError(
                        f"Hugging Face model '{self.model_name}' not found on serverless router"
                    )
                elif resp.status_code == 429:
                    if attempt < max_attempts:
                        wait_sec = 2.0 * attempt
                        logger.warning(f"Hugging Face rate-limited (HTTP 429). Retrying in {wait_sec}s...")
                        time.sleep(wait_sec)
                        continue
                    raise LLMRateLimitError(
                        "Hugging Face inference rate limit or quota exceeded (HTTP 429)"
                    )
                elif resp.status_code in (500, 502, 503, 504):
                    # 503 in HF often means "Model is currently loading (estimated_time)"
                    if attempt < max_attempts:
                        wait_sec = 2.0 * attempt
                        logger.warning(
                            f"Hugging Face server error / model warming (HTTP {resp.status_code}). "
                            f"Retrying attempt {attempt + 1}/{max_attempts} in {wait_sec}s..."
                        )
                        time.sleep(wait_sec)
                        continue
                    raise LLMUnavailableError(
                        f"Hugging Face API server error (HTTP {resp.status_code})"
                    )
                elif resp.status_code != 200:
                    raise LLMProviderError(
                        f"Hugging Face API returned error HTTP {resp.status_code}: {resp.text[:200]}"
                    )

                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    logger.warning(f"Hugging Face returned empty choices list after {elapsed:.2f}s")
                    raise LLMProviderError("Hugging Face returned empty choices list")

                answer = choices[0].get("message", {}).get("content", "").strip()
                if not answer:
                    logger.warning(f"Hugging Face returned empty message content after {elapsed:.2f}s")
                    return "No response could be generated from the available analytical evidence."

                logger.info(f"Hugging Face generation completed in {elapsed:.2f}s (length={len(answer)} chars)")
                return answer

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < max_attempts:
                    wait_sec = 2.0 * attempt
                    logger.warning(f"Hugging Face network hiccup ({type(e).__name__}). Retrying in {wait_sec}s...")
                    time.sleep(wait_sec)
                    continue
                if isinstance(e, httpx.TimeoutException):
                    raise LLMTimeoutError(f"Hugging Face request timed out after {self.timeout}s")
                raise LLMUnavailableError(f"Cannot connect to Hugging Face API: {e}")
            except LLMProviderError:
                raise
            except Exception as e:
                logger.error(f"Unexpected error in HuggingFaceProvider: {type(e).__name__} - {e}")
                raise LLMProviderError(f"Unexpected error during Hugging Face generation: {e}")

        raise LLMUnavailableError("Hugging Face API failed across all retry attempts")
