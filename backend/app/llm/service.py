"""
Centralized LLM Service — the single gateway between agents and model providers.

All LLM interactions MUST flow through this service.  Agents call semantic
methods (generate, chat, summarize, extract, classify) instead of reaching
into provider internals.

Architecture:
    Agent  →  LLMService  →  BaseLLMProvider (OpenAI / Mock / future models)
"""

import json
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from app.config.settings import settings
from app.llm.provider import BaseLLMProvider
from app.utils.logger import logger

T = TypeVar("T")


class LLMService:
    """High-level, provider-agnostic façade for every LLM interaction."""

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        if provider is not None:
            self._provider = provider
        else:
            # Lazy import to avoid circular dependency
            from app.llm.openai import get_llm_provider
            self._provider = get_llm_provider()

    # ------------------------------------------------------------------ #
    #  Core primitives
    # ------------------------------------------------------------------ #

    @property
    def provider(self) -> BaseLLMProvider:
        """Expose the underlying provider (useful for advanced / escape-hatch usage)."""
        return self._provider

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """General-purpose text generation — the lowest-level public method."""
        try:
            return await self._provider.generate_text(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error(f"LLMService.generate failed: {e}")
            raise

    async def generate_json(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a response constrained to valid JSON."""
        try:
            return await self._provider.generate_structured_json(
                prompt,
                system_prompt=system_prompt,
            )
        except Exception as e:
            logger.error(f"LLMService.generate_json failed: {e}")
            raise

    # ------------------------------------------------------------------ #
    #  Semantic convenience methods
    # ------------------------------------------------------------------ #

    async def chat(
        self,
        user_message: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """Conversational / chat-style generation."""
        return await self.generate(
            user_message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def execute_prompt(
        self,
        prompt: Union[Any, str],
        variables: Optional[Dict[str, Any]] = None,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        is_json: bool = False,
    ) -> str:
        """Execute a centralized prompt configuration with versioning, parameters, and telemetry."""
        from app.llm.prompts import PromptConfig, get_prompt

        if isinstance(prompt, str):
            config = get_prompt(prompt)
        elif isinstance(prompt, PromptConfig):
            config = prompt
        else:
            raise TypeError("prompt must be a PromptConfig instance or registered prompt name string")

        vars_dict = variables or {}
        user_prompt = config.format_user_prompt(**vars_dict)
        system_prompt = config.system_prompt
        effective_temp = temperature if temperature is not None else config.temperature
        effective_max_tokens = max_tokens if max_tokens is not None else config.max_tokens
        effective_model = model or config.model or settings.DEFAULT_MODEL

        logger.debug(
            f"[LLM Operation] Prompt: '{config.name}' (v{config.version}) | "
            f"Model: {effective_model} | Temp: {effective_temp} | MaxTokens: {effective_max_tokens}"
        )

        if is_json:
            return await self.generate_json(user_prompt, system_prompt=system_prompt)
        else:
            return await self.generate(
                user_prompt,
                system_prompt=system_prompt,
                temperature=effective_temp,
                max_tokens=effective_max_tokens,
            )

    async def summarize(
        self,
        text: str,
        *,
        max_length: Optional[int] = None,
        style: str = "concise",
        system_prompt: Optional[str] = None,
    ) -> str:
        """Summarize a block of text.

        Args:
            text: Source text to summarize.
            max_length: Soft target word-count for the summary.
            style: One of 'concise', 'detailed', 'executive', 'bullet_points'.
            system_prompt: Optional override for the system prompt.
        """
        length_hint = f" in roughly {max_length} words" if max_length else ""
        style_map = {
            "concise": "Write a concise summary.",
            "detailed": "Write a thorough, detailed summary.",
            "executive": "Write an executive summary suitable for senior leadership.",
            "bullet_points": "Summarize as bullet points.",
        }
        instruction = style_map.get(style, style_map["concise"])

        from app.llm.prompts import summarization_prompt
        user_prompt = summarization_prompt.format_user_prompt(
            instruction=instruction,
            length_hint=length_hint,
            text=text,
        )
        return await self.generate(
            user_prompt,
            system_prompt=system_prompt or summarization_prompt.system_prompt,
            temperature=summarization_prompt.temperature,
            max_tokens=summarization_prompt.max_tokens,
        )

    async def extract(
        self,
        text: str,
        *,
        schema_description: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Extract structured information from text and return valid JSON.

        Args:
            text: Source text to extract from.
            schema_description: Natural-language description of the desired JSON schema.
            system_prompt: Optional override for the system prompt.
        """
        schema_hint = ""
        if schema_description:
            schema_hint = f"\nExpected JSON schema:\n{schema_description}\n"

        prompt = (
            f"Extract structured information from the text below and return valid JSON.{schema_hint}\n\n"
            f"Text:\n{text}"
        )
        default_system = "You are a precise data-extraction assistant. Return ONLY valid JSON."
        return await self.generate_json(
            prompt,
            system_prompt=system_prompt or default_system,
        )

    async def classify(
        self,
        text: str,
        categories: List[str],
        *,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Classify text into one or more of the given categories. Returns JSON.

        Args:
            text: Text to classify.
            categories: List of valid category labels.
            system_prompt: Optional override for the system prompt.
        """
        cats_str = ", ".join(f'"{c}"' for c in categories)
        prompt = (
            f"Classify the following text into one of these categories: [{cats_str}].\n"
            f"Return JSON with keys 'category' (primary label) and 'confidence' (0-1 float).\n\n"
            f"Text:\n{text}"
        )
        default_system = "You are a precise classification assistant. Return ONLY valid JSON."
        return await self.generate_json(
            prompt,
            system_prompt=system_prompt or default_system,
        )

    # ------------------------------------------------------------------ #
    #  Utilities
    # ------------------------------------------------------------------ #

    async def generate_parsed_json(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
    ) -> Any:
        """Like generate_json but returns parsed Python objects instead of a raw string."""
        raw = await self.generate_json(prompt, system_prompt=system_prompt)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(f"LLMService.generate_parsed_json: JSON decode error — {exc}")
            return raw  # fall back to raw string so callers can still recover

    def __repr__(self) -> str:
        return f"<LLMService provider={self._provider.__class__.__name__}>"


# ------------------------------------------------------------------ #
#  Module-level singleton (preferred import for most consumers)
# ------------------------------------------------------------------ #

def get_llm_service(provider: Optional[BaseLLMProvider] = None) -> LLMService:
    """Factory that returns an LLMService, optionally with a custom provider."""
    return LLMService(provider=provider)


# Default singleton — import this everywhere:
#   from app.llm.service import llm_service
llm_service = LLMService()
