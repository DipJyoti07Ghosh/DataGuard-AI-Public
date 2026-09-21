"""
DataGuard AI — Phase 12 Ollama LLM Service

Provides client communication with local Ollama daemon for inference:
- Health checking and connectivity verification
- Local model availability verification
- Prompt dispatch with timeout, low temperature (0.1), and token bounding
- Strict error classification without leaking internal stack traces or sensitive data
"""

import logging
import time
from typing import Dict, Any, List, Optional
import httpx

from app.config import settings
from app.schemas.assistant import AssistantHealthResponse

logger = logging.getLogger(__name__)


class OllamaService:
    """Client wrapper for local Ollama LLM interactions."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model_name = model_name or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout_seconds
        self._custom_client = http_client

    def _get_client(self) -> httpx.Client:
        if self._custom_client is not None:
            return self._custom_client
        return httpx.Client(timeout=self.timeout)

    def check_health(self) -> AssistantHealthResponse:
        """
        Check whether the local Ollama daemon is reachable and whether the configured model is available.
        """
        try:
            client = self._get_client()
            url = f"{self.base_url}/api/tags"
            response = client.get(url)

            if response.status_code != 200:
                logger.warning(f"Ollama returned HTTP status {response.status_code}")
                return AssistantHealthResponse(
                    status="DEGRADED",
                    ollama_reachable=True,
                    ollama_base_url=self.base_url,
                    configured_model=self.model_name,
                    model_available=False,
                    available_models=[],
                    message=f"Ollama daemon reachable at {self.base_url}, but returned HTTP {response.status_code}",
                )

            data = response.json()
            models_list = data.get("models", [])
            installed_tags = [m.get("name", "") for m in models_list if m.get("name")]

            # Check if configured model or its base tag is installed (e.g., 'llama3.1:8b' or 'llama3.1:latest')
            model_target = self.model_name.strip().lower()
            model_found = any(
                tag.lower() == model_target
                or tag.lower().startswith(f"{model_target}:")
                or model_target.startswith(f"{tag.lower()}:")
                for tag in installed_tags
            )

            if model_found:
                return AssistantHealthResponse(
                    status="HEALTHY",
                    ollama_reachable=True,
                    ollama_base_url=self.base_url,
                    configured_model=self.model_name,
                    model_available=True,
                    available_models=installed_tags,
                    message=f"Ollama connected and model '{self.model_name}' is ready for inference.",
                )
            else:
                return AssistantHealthResponse(
                    status="DEGRADED",
                    ollama_reachable=True,
                    ollama_base_url=self.base_url,
                    configured_model=self.model_name,
                    model_available=False,
                    available_models=installed_tags,
                    message=(
                        f"Ollama daemon is active, but configured model '{self.model_name}' is not installed. "
                        f"Please run `ollama pull {self.model_name}` locally."
                    ),
                )

        except httpx.ConnectError:
            logger.info(f"Ollama connection refused at {self.base_url}")
            return AssistantHealthResponse(
                status="UNAVAILABLE",
                ollama_reachable=False,
                ollama_base_url=self.base_url,
                configured_model=self.model_name,
                model_available=False,
                available_models=[],
                message=(
                    f"Ollama daemon unreachable at {self.base_url}. "
                    "Ensure Ollama is installed and running (`ollama serve`)."
                ),
            )
        except httpx.TimeoutException:
            logger.warning(f"Ollama health check timed out at {self.base_url}")
            return AssistantHealthResponse(
                status="UNAVAILABLE",
                ollama_reachable=False,
                ollama_base_url=self.base_url,
                configured_model=self.model_name,
                model_available=False,
                available_models=[],
                message=f"Ollama health check timed out after {self.timeout}s at {self.base_url}.",
            )
        except Exception as e:
            logger.error(f"Unexpected error during Ollama health check: {type(e).__name__}")
            return AssistantHealthResponse(
                status="UNAVAILABLE",
                ollama_reachable=False,
                ollama_base_url=self.base_url,
                configured_model=self.model_name,
                model_available=False,
                available_models=[],
                message=f"Error checking Ollama status: {type(e).__name__}",
            )

    def generate_completion(
        self,
        prompt: str,
        system_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate completion from the local Ollama LLM.
        Applies temperature bounding (default 0.1) and token limit.
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
            logger.info(f"Submitting prompt to Ollama model '{self.model_name}' (temp={temp}, max_tokens={num_predict})...")
            response = client.post(url, json=payload)
            elapsed = time.time() - start_time

            if response.status_code == 404:
                raise RuntimeError(
                    f"Model '{self.model_name}' not found on Ollama server. Run `ollama pull {self.model_name}`."
                )
            elif response.status_code != 200:
                raise RuntimeError(
                    f"Ollama returned HTTP error {response.status_code}: {response.text[:200]}"
                )

            data = response.json()
            answer = data.get("response", "").strip()
            if not answer:
                logger.warning(f"Ollama returned empty response string after {elapsed:.2f}s")
                return "No response could be generated from the available analytical evidence."

            logger.info(f"Ollama generation completed in {elapsed:.2f}s (length={len(answer)} chars)")
            return answer

        except httpx.ConnectError:
            logger.error(f"Failed to connect to Ollama at {self.base_url}")
            raise ConnectionError(
                f"Cannot connect to local Ollama service at {self.base_url}. Please start Ollama with `ollama serve`."
            )
        except httpx.TimeoutException:
            logger.error(f"Ollama request timed out after {self.timeout}s")
            raise TimeoutError(
                f"Ollama generation timed out after {self.timeout}s. Try asking a more specific question or checking system resources."
            )
        except Exception as e:
            if isinstance(e, (ConnectionError, TimeoutError, RuntimeError)):
                raise
            logger.error(f"Unexpected error during Ollama inference: {type(e).__name__}")
            raise RuntimeError(f"Ollama generation failed: {type(e).__name__}")


# Singleton instance
_default_ollama_service = None


def get_ollama_service() -> OllamaService:
    """Retrieve the global OllamaService singleton."""
    global _default_ollama_service
    if _default_ollama_service is None:
        _default_ollama_service = OllamaService()
    return _default_ollama_service
