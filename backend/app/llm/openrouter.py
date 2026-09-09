import json
import httpx
from typing import Optional, Dict, Any
from app.config.settings import settings
from app.utils.logger import logger
from app.llm.provider import BaseLLMProvider, MockLLMProvider


class OpenRouterLLMProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.model = model or settings.LLM_MODEL or "openrouter/free"
        self.base_url = (base_url or settings.LLM_BASE_URL or "https://openrouter.ai/api/v1").rstrip("/")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://deep-research-ai.local",
            "X-Title": "Deep Research AI",
            "Content-Type": "application/json",
        }

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        if not self.api_key:
            logger.info("OpenRouter API key missing. Falling back to Mock LLM provider.")
            return await MockLLMProvider().generate_text(prompt, system_prompt, temperature, max_tokens)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"OpenRouter API Error {res.status_code}: {res.text}")
                    return await MockLLMProvider().generate_text(prompt, system_prompt)
        except Exception as e:
            logger.error(f"Failed OpenRouter request: {e}")
            return await MockLLMProvider().generate_text(prompt, system_prompt)

    async def generate_structured_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        if not self.api_key:
            logger.info("OpenRouter API key missing. Falling back to Mock LLM provider.")
            return await MockLLMProvider().generate_structured_json(prompt, system_prompt)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": f"{prompt}\nReturn ONLY valid JSON."})

        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"OpenRouter API JSON Error {res.status_code}: {res.text}")
                    return await MockLLMProvider().generate_structured_json(prompt, system_prompt)
        except Exception as e:
            logger.error(f"OpenRouter JSON request failed: {e}")
            return await MockLLMProvider().generate_structured_json(prompt, system_prompt)


def get_openrouter_provider() -> OpenRouterLLMProvider:
    return OpenRouterLLMProvider()
