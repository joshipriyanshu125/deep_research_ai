"""
Centralized LLM Service — the single gateway between agents and model providers.

All LLM interactions MUST flow through this service. Agents call semantic
methods (generate, chat, summarize, extract, classify) instead of reaching
into provider internals.

Architecture:
    Agent  →  LLMService  →  ModelRouter / BaseLLMProvider (OpenAI / Mock / future models)
"""

import asyncio
import copy
import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, Tuple

from app.config.settings import settings
from app.llm.provider import BaseLLMProvider, LLMProviderError
from app.llm.router import model_router, ModelRouter, RoutingDecision, RoutingStrategy, TaskComplexity
from app.utils.logger import logger

T = TypeVar("T")
LLM_CALL_TIMEOUT_SECONDS = 35.0
_usage_capture: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar("llm_usage_capture", default=None)
_last_call: ContextVar[Optional[Dict[str, Any]]] = ContextVar("last_llm_call", default=None)
_operation: ContextVar[str] = ContextVar("llm_operation", default="generation")


@contextmanager
def capture_llm_usage():
    """Collect actual call receipts for this run, including inherited child tasks.

    The list is scoped with ContextVar rather than stored on singleton agents,
    so simultaneous research jobs cannot borrow one another's Gemini usage.
    Receipts contain identifiers/status only, never prompts, responses or keys.
    """
    receipts: List[Dict[str, Any]] = []
    token = _usage_capture.set(receipts)
    try:
        yield receipts
    finally:
        _usage_capture.reset(token)


def llm_provenance(service: Any) -> Dict[str, Any]:
    """Snapshot the current task's last call, without mistaking a key for usage."""
    if isinstance(service, LLMService):
        return dict(service.last_call or {**service.provider_metadata, "llm_used": False, "success": False})
    # Explicitly supplied test doubles have no verified provider identity.
    return {"provider": "unknown", "model": "", "llm_used": False, "success": False}


class LLMService:
    """High-level, provider-agnostic façade for every LLM interaction."""

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        router: Optional[ModelRouter] = None,
        provider_type: Optional[str] = None,
    ):
        if provider is not None:
            self._provider = provider
        else:
            # Lazy import to avoid circular dependency
            from app.llm.openai import get_llm_provider
            self._provider = get_llm_provider(provider_type=provider_type)

        self._router = router or model_router

    # ------------------------------------------------------------------ #
    #  Core primitives
    # ------------------------------------------------------------------ #

    @property
    def provider(self) -> BaseLLMProvider:
        """Expose the underlying provider (useful for advanced / escape-hatch usage)."""
        return self._provider

    @property
    def provider_metadata(self) -> Dict[str, str]:
        """Return stable provider/model identifiers for run provenance."""
        provider = self._provider
        provider_type = getattr(provider, "provider_type", provider.__class__.__name__.lower())
        model = getattr(provider, "model", "") or ""
        return {"provider": str(provider_type), "model": str(model)}

    @property
    def last_call(self) -> Optional[Dict[str, Any]]:
        value = _last_call.get()
        return dict(value) if value else None

    async def _call_provider(self, method: str, prompt: str, *, model=None, **kwargs) -> str:
        provider = self._provider
        if model and hasattr(provider, "model"):
            provider = copy.copy(provider)
            provider.model = model
        provider_type = getattr(provider, "provider_type", "unknown")
        receipt = {
            "operation": _operation.get(),
            "provider": provider_type,
            "model": getattr(provider, "model", "") or "",
            "success": False,
            "llm_used": False,
        }
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                getattr(provider, method)(prompt, **kwargs),
                timeout=LLM_CALL_TIMEOUT_SECONDS,
            )
            if not isinstance(result, str) or not result.strip():
                raise LLMProviderError("LLM provider returned an empty response")
            receipt["success"] = True
            receipt["llm_used"] = provider_type not in {"mock", "unavailable", "unknown"}
            return result
        except BaseException as exc:
            receipt["error_type"] = type(exc).__name__
            raise
        finally:
            receipt["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
            _last_call.set(receipt)
            capture = _usage_capture.get()
            if capture is not None:
                capture.append(dict(receipt))

    @property
    def router(self) -> ModelRouter:
        """Expose the model router."""
        return self._router

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        model: Optional[str] = None,
    ) -> str:
        """General-purpose text generation — the lowest-level public method."""
        try:
            return await self._call_provider(
                "generate_text",
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )
        except Exception as e:
            logger.warning(f"LLMService.generate failed: {type(e).__name__}")
            raise

    async def generate_json(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """Generate a response constrained to valid JSON."""
        try:
            return await self._call_provider(
                "generate_structured_json",
                prompt,
                system_prompt=system_prompt,
                model=model,
            )
        except Exception as e:
            logger.warning(f"LLMService.generate_json failed: {type(e).__name__}")
            raise

    # ------------------------------------------------------------------ #
    #  Intelligent Multi-Model Routed Execution (Day 82–84)
    # ------------------------------------------------------------------ #

    async def generate_routed(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        task_hint: Optional[str] = None,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        preferred_provider: Optional[str] = None,
        max_budget_usd: Optional[float] = None
    ) -> Tuple[str, RoutingDecision]:
        """
        Executes text generation by intelligently routing through ModelRouter.
        Returns a tuple of (generated_text, routing_decision).
        """
        start_t = time.perf_counter()
        decision = self._router.route(
            prompt=prompt,
            system_prompt=system_prompt,
            task_hint=task_hint,
            strategy=strategy,
            preferred_provider=preferred_provider,
            max_budget_usd=max_budget_usd
        )

        logger.info(f"[ModelRouter] {decision.routing_reason}")

        try:
            result = await self.generate(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            self._router.record_success(decision.selected_model, latency_ms=elapsed_ms)
            return result, decision
        except Exception as e:
            self._router.record_failure(decision.selected_model, error=str(e))
            # A routing decision names model profiles, but this service owns a
            # single configured provider instance.  Calling a canned mock for
            # a failed real request would make the report look verified when
            # it was never generated.  Surface the failure instead; agents
            # have deterministic grounded fallbacks.
            logger.warning(
                f"Primary model {decision.selected_model} failed; no synthetic fallback will be used."
            )
            raise

    async def generate_json_routed(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        task_hint: Optional[str] = None,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED
    ) -> Tuple[str, RoutingDecision]:
        """
        Executes JSON generation routed through ModelRouter.
        """
        start_t = time.perf_counter()
        decision = self._router.route(
            prompt=prompt,
            system_prompt=system_prompt,
            task_hint=task_hint or "json_extraction",
            strategy=strategy
        )

        try:
            result = await self.generate_json(prompt, system_prompt=system_prompt)
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            self._router.record_success(decision.selected_model, latency_ms=elapsed_ms)
            return result, decision
        except Exception as e:
            self._router.record_failure(decision.selected_model, error=str(e))
            logger.warning(
                f"Primary model {decision.selected_model} failed; no synthetic JSON fallback will be used."
            )
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
        model_override = model or config.model
        effective_model = model_override or self.provider_metadata["model"]

        logger.debug(
            f"[LLM Operation] Prompt: '{config.name}' (v{config.version}) | "
            f"Model: {effective_model} | Temp: {effective_temp} | MaxTokens: {effective_max_tokens}"
        )

        operation_token = _operation.set(config.name)
        try:
            if is_json:
                return await self.generate_json(user_prompt, system_prompt=system_prompt, model=model_override)
            return await self.generate(
                    user_prompt,
                    system_prompt=system_prompt,
                    temperature=effective_temp,
                    max_tokens=effective_max_tokens,
                    model=model_override,
                )
        finally:
            _operation.reset(operation_token)

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

def get_llm_service(
    provider: Optional[BaseLLMProvider] = None,
    router: Optional[ModelRouter] = None,
    provider_type: Optional[str] = None,
) -> LLMService:
    """Factory that returns an LLMService, optionally with a custom provider or router."""
    return LLMService(provider=provider, router=router, provider_type=provider_type)


# Default singleton — import this everywhere:
#   from app.llm.service import llm_service
llm_service = LLMService()
