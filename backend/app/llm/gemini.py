"""Small REST client for the configured Google Gemini text provider.

The deep-research pipeline deliberately uses the same provider boundary as
OpenAI/OpenRouter.  Keeping the client here avoids making agents aware of a
vendor SDK and, importantly, lets provider failures reach deterministic
grounded fallbacks instead of becoming canned research claims.
"""

import asyncio
from typing import Any, Dict, Optional

import httpx

from app.config.settings import settings
from app.llm.provider import BaseLLMProvider, LLMProviderError, LLMUnavailableError
from app.utils.logger import logger


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
LLM_REQUEST_TIMEOUT_SECONDS = 30.0


class GeminiLLMProvider(BaseLLMProvider):
    provider_type = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL or "gemini-flash-lite-latest"

    def _payload(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        response_mime_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if response_mime_type:
            payload["generationConfig"]["responseMimeType"] = response_mime_type
        return payload

    async def _generate(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        response_mime_type: Optional[str] = None,
    ) -> str:
        if not self.api_key:
            raise LLMUnavailableError("Gemini API key is not configured")

        url = GEMINI_API_URL.format(model=self.model)
        params = {"key": self.api_key}
        payload = self._payload(
            prompt,
            system_prompt,
            temperature,
            max_tokens,
            response_mime_type=response_mime_type,
        )

        try:
            async with httpx.AsyncClient(timeout=LLM_REQUEST_TIMEOUT_SECONDS) as client:
                response = await asyncio.wait_for(
                    client.post(url, json=payload, params=params),
                    timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                )
            if response.status_code != 200:
                logger.warning(f"Gemini API request failed with status {response.status_code}")
                raise LLMProviderError(f"Gemini API request failed (status {response.status_code})")
            data = response.json()
            candidates = data.get("candidates") or []
            parts = (candidates[0].get("content") or {}).get("parts") if candidates else None
            text = "".join(
                str(part.get("text") or "")
                for part in (parts or [])
                if isinstance(part, dict)
            ).strip()
            if not text:
                raise LLMProviderError("Gemini API returned no text")
            return text
        except asyncio.TimeoutError as exc:
            raise LLMProviderError("Gemini API request timed out") from exc
        except httpx.RequestError as exc:
            raise LLMProviderError("Gemini API request could not be completed") from exc
        except LLMProviderError:
            raise
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMProviderError("Gemini API response could not be parsed") from exc
        except Exception as exc:
            logger.error(f"Gemini request failed: {type(exc).__name__}")
            raise LLMProviderError("Gemini API request failed") from exc

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        return await self._generate(
            prompt,
            system_prompt,
            temperature,
            max_tokens,
        )

    async def generate_structured_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        return await self._generate(
            prompt,
            system_prompt,
            temperature=0.2,
            max_tokens=4000,
            response_mime_type="application/json",
        )
