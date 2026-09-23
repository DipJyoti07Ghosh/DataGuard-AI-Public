"""
DataGuard AI — Phase 12A Local Ollama LLM Provider

Implements local Ollama LLM provider under the BaseLLMProvider interface:
- Non-billable health checks (daemon ping and model tags inspection)
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
    LLMUnavailableError,
    LLMTimeoutError,
    LLMModelNotFoundError,
)

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Local Ollama LLM provider."""

    def __init__(
        self,
        base_url_or_settings: Any = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
        http_client: Optional[httpx.Client] = None,
        base_url: Optional[str] = None,
    ):
        target_url = base_url or base_url_or_settings
        if hasattr(target_url, "ollama_base_url"):
            cfg = target_url
            self.base_url = (cfg.ollama_base_url or "http://localhost:11434").rstrip("/")
            self.model_name = (model_name or cfg.ollama_model or "llama3.2:1b").strip()
            self.timeout = timeout or cfg.ollama_timeout_seconds
        else:
            cfg = settings
            self.base_url = (target_url or getattr(cfg, "ollama_base_url", "http://localhost:11434")).rstrip("/")
            self.model_name = (model_name or getattr(cfg, "ollama_model", "llama3.2:1b")).strip()
            self.timeout = timeout or getattr(cfg, "ollama_timeout_seconds", 60.0)
        self._custom_client = http_client

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def provider_type(self) -> str:
        return "LOCAL_LLM"

    def _get_client(self) -> httpx.Client:
        if self._custom_client is not None:
            return self._custom_client
        return httpx.Client(timeout=self.timeout)

    def check_health(self) -> Dict[str, Any]:
        """
        Check if local Ollama daemon is reachable and whether configured model is available.
        """
        try:
            client = self._get_client()
            url = f"{self.base_url}/api/tags"
            response = client.get(url)

            if response.status_code != 200:
                return {
                    "available": False,
                    "status": "DEGRADED",
                    "configured_model": self.model_name,
                    "message": f"Ollama daemon reachable at {self.base_url}, but returned HTTP {response.status_code}",
                }

            data = response.json()
            models_list = data.get("models", [])
            installed_tags = [m.get("name", "") for m in models_list if m.get("name")]

            model_target = self.model_name.strip().lower()
            model_found = any(
                tag.lower() == model_target
                or tag.lower().startswith(f"{model_target}:")
                or model_target.startswith(f"{tag.lower()}:")
                for tag in installed_tags
            )

            if model_found:
                return {
                    "available": True,
                    "status": "HEALTHY",
                    "configured_model": self.model_name,
                    "message": f"Ollama connected and model '{self.model_name}' is ready for inference.",
                }
            else:
                return {
                    "available": False,
                    "status": "DEGRADED",
                    "configured_model": self.model_name,
                    "message": (
                        f"Ollama daemon is active, but configured model '{self.model_name}' is not installed. "
                        f"Run `ollama pull {self.model_name}` locally."
                    ),
                }

        except httpx.ConnectError:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": (
                    f"Ollama daemon unreachable at {self.base_url}. "
                    "Ensure Ollama is running locally (`ollama serve`)."
                ),
            }
        except httpx.TimeoutException:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": f"Ollama health check timed out after {self.timeout}s at {self.base_url}.",
            }
        except Exception as e:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "configured_model": self.model_name,
                "message": f"Error checking Ollama status: {type(e).__name__}",
            }

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Execute natural language completion via local Ollama daemon.
        """
        temp = temperature if temperature is not None else settings.ollama_temperature
        num_predict = max_tokens if max_tokens is not None else settings.ollama_max_tokens

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": num_predict,
            },
        }

        url = f"{self.base_url}/api/generate"
        client = self._get_client()
        start_time = time.time()

        try:
            logger.info(
                f"Submitting grounded prompt to Local Ollama model '{self.model_name}' "
                f"(temp={temp}, max_tokens={num_predict})..."
            )
            response = client.post(url, json=payload)
            elapsed = time.time() - start_time

            if response.status_code == 404:
                raise LLMModelNotFoundError(
                    f"Model '{self.model_name}' not found on Ollama server. Run `ollama pull {self.model_name}`."
                )
            elif response.status_code != 200:
                raise LLMProviderError(
                    f"Ollama returned HTTP error {response.status_code}: {response.text[:200]}"
                )

            data = response.json()
            answer = data.get("response", "").strip()
            if not answer:
                logger.warning(f"Ollama returned empty response string after {elapsed:.2f}s")
                return "No response could be generated from the available analytical evidence."

            logger.info(f"Ollama generation completed in {elapsed:.2f}s (length={len(answer)} chars)")
            return answer

        except httpx.ConnectError as e:
            logger.warning(f"Ollama connection failure at {self.base_url}: {e}")
            raise LLMUnavailableError(
                f"Cannot connect to local Ollama service at {self.base_url}. Please start Ollama with `ollama serve`."
            )
        except httpx.TimeoutException as e:
            logger.warning(f"Ollama request timed out after {self.timeout}s: {e}")
            raise LLMTimeoutError(
                f"Ollama generation timed out after {self.timeout}s."
            )
        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during Ollama inference: {type(e).__name__}")
            raise LLMProviderError(f"Ollama generation failed: {type(e).__name__}")
