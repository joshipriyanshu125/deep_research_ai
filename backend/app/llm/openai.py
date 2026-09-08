import json
import httpx
from typing import Optional, Dict, Any
from app.config.settings import settings
from app.utils.logger import logger
from app.llm.provider import BaseLLMProvider, MockLLMProvider


class OpenAILLMProvider(BaseLLMProvider):
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
            logger.info("OpenAI API key missing. Falling back to Mock LLM provider.")
            return await MockLLMProvider().generate_text(prompt, system_prompt, temperature, max_tokens)

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
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    logger.error(f"OpenAI API Error {res.status_code}: {res.text}")
                    return await MockLLMProvider().generate_text(prompt, system_prompt)
        except Exception as e:
            logger.error(f"Failed OpenAI request: {e}")
            return await MockLLMProvider().generate_text(prompt, system_prompt)

    async def generate_structured_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        if not self.api_key:
            return await MockLLMProvider().generate_structured_json(prompt, system_prompt)

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
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return await MockLLMProvider().generate_structured_json(prompt, system_prompt)
        except Exception as e:
            logger.error(f"OpenAI JSON request failed: {e}")
            return await MockLLMProvider().generate_structured_json(prompt, system_prompt)


def get_llm_provider(provider_type: Optional[str] = None) -> BaseLLMProvider:
    provider = provider_type or settings.LLM_PROVIDER
    if provider.lower() == "openai" and settings.OPENAI_API_KEY:
        return OpenAILLMProvider()
    return MockLLMProvider()
