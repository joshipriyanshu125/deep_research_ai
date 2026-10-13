import asyncio
import httpx
from typing import Optional, Dict, Any
from app.config.settings import settings
from app.utils.logger import logger
from app.llm.provider import (
    BaseLLMProvider,
    LLMProviderError,
    LLMUnavailableError,
    UnavailableLLMProvider,
    MockLLMProvider,
)


LLM_REQUEST_TIMEOUT_SECONDS = 30.0


class OpenAILLMProvider(BaseLLMProvider):
    provider_type = "openai"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.DEFAULT_MODEL
        self.base_url = "https://api.openai.com/v1"

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> str:
        if not self.api_key:
            raise LLMUnavailableError("OpenAI API key is not configured")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            async with httpx.AsyncClient(timeout=LLM_REQUEST_TIMEOUT_SECONDS) as client:
                res = await asyncio.wait_for(
                    client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload),
                    timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                )
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                logger.error(f"OpenAI API request failed with status {res.status_code}")
                raise LLMProviderError(f"OpenAI API request failed (status {res.status_code})")
        except asyncio.TimeoutError as exc:
            raise LLMProviderError("OpenAI API request timed out") from exc
        except httpx.RequestError as exc:
            raise LLMProviderError("OpenAI API request could not be completed") from exc
        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"Failed OpenAI request: {type(e).__name__}")
            raise LLMProviderError("OpenAI API response could not be parsed") from e

    async def generate_structured_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        if not self.api_key:
            raise LLMUnavailableError("OpenAI API key is not configured")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": f"{prompt}\nReturn ONLY valid JSON."})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        try:
            async with httpx.AsyncClient(timeout=LLM_REQUEST_TIMEOUT_SECONDS) as client:
                res = await asyncio.wait_for(
                    client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload),
                    timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                )
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                logger.error(f"OpenAI JSON request failed with status {res.status_code}")
                raise LLMProviderError(f"OpenAI JSON request failed (status {res.status_code})")
        except asyncio.TimeoutError as exc:
            raise LLMProviderError("OpenAI JSON request timed out") from exc
        except httpx.RequestError as exc:
            raise LLMProviderError("OpenAI JSON request could not be completed") from exc
        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"OpenAI JSON request failed: {type(e).__name__}")
            raise LLMProviderError("OpenAI JSON response could not be parsed") from e


def get_llm_provider(provider_type: Optional[str] = None) -> BaseLLMProvider:
    """Resolve the configured provider without implicit canned-output fallback.

    An explicitly selected provider remains authoritative when its key is
    missing.  For the historical default (OpenRouter), an actually configured
    alternate provider may be used, but a run with no usable key receives an
    ``UnavailableLLMProvider`` so callers can report the limitation honestly.
    """
    provider = (provider_type or settings.LLM_PROVIDER or "").strip().lower()
    aliases = {"google": "gemini", "google_gemini": "gemini", "gemini_api": "gemini"}
    provider = aliases.get(provider, provider)

    if provider == "mock":
        return MockLLMProvider()

    if provider == "gemini":
        if settings.GEMINI_API_KEY:
            from app.llm.gemini import GeminiLLMProvider
            return GeminiLLMProvider()
        return UnavailableLLMProvider("Gemini API key is not configured")

    if provider == "openrouter":
        if settings.OPENROUTER_API_KEY:
            from app.llm.openrouter import OpenRouterLLMProvider
            return OpenRouterLLMProvider()
        # The application default historically points at OpenRouter.  If it
        # is not configured, permit an explicitly configured real provider to
        # serve the run rather than returning canned output.
        if provider_type:
            return UnavailableLLMProvider("OpenRouter API key is not configured")

    if provider == "openai":
        if settings.OPENAI_API_KEY:
            return OpenAILLMProvider()
        if provider_type:
            return UnavailableLLMProvider("OpenAI API key is not configured")

    # If the selected provider is unavailable, use another *configured* real
    # provider rather than silently returning a canned model response.  The
    # order keeps the existing OpenRouter/OpenAI preference and adds Gemini.
    if settings.OPENROUTER_API_KEY:
        from app.llm.openrouter import OpenRouterLLMProvider
        return OpenRouterLLMProvider()

    if settings.GEMINI_API_KEY:
        from app.llm.gemini import GeminiLLMProvider
        return GeminiLLMProvider()

    if settings.OPENAI_API_KEY:
        return OpenAILLMProvider()

    if settings.ANTHROPIC_API_KEY:
        return UnavailableLLMProvider(
            "Anthropic is configured but this installation has no Anthropic provider"
        )

    return UnavailableLLMProvider()
