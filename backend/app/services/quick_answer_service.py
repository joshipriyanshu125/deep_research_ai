"""
Quick Answer Service — lightweight direct Gemini API call for simple questions.

Architecture:
    User Query → Query Router → (simple?) → QuickAnswerService → Gemini API → Direct Answer
                                            → (complex?) → Deep Research Pipeline
"""

import asyncio
import json
import os
import re
from typing import Optional

import httpx

from app.config.settings import settings
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Complexity classifier
# ---------------------------------------------------------------------------

_SIMPLE_PATTERNS = [
    r"^what is\b",
    r"^what are\b",
    r"^who is\b",
    r"^who was\b",
    r"^when (was|did|is)\b",
    r"^where (is|was|are)\b",
    r"^how (does|do|did|is|are|many|much|long|far|old)\b",
    r"^define\b",
    r"^explain\b",
    r"^tell me about\b",
    r"^give me a (brief|quick|short)\b",
    r"^can you explain\b",
    r"^what does .+ mean",
    r"^difference between\b",
    r"^compare .+ and .+",
    r"^list (the |some )?(top |main |key )?\d*",
]

_COMPLEX_PATTERNS = [
    r"\banalyze\b",
    r"\bcomprehensive\b",
    r"\bin-depth\b",
    r"\bmarket (size|share|analysis|report)\b",
    r"\bcompetitive (landscape|analysis)\b",
    r"\binvestment (opportunities|risks|analysis)\b",
    r"\btrend analysis\b",
    r"\brecent developments\b",
    r"\blatest news\b",
    r"\bcurrent state of\b",
    r"\bfuture of\b",
    r"\bpredictions? for\b",
    r"\bforecast\b",
    r"\bsources?\b.*\b(provide|cite|include)\b",
    r"\bwith sources\b",
    r"\bdetailed report\b",
    r"\bresearch report\b",
    r"\bfull report\b",
    r"\bimpact of\b",
    r"\brisks? (and|of)\b",
    r"\bopportunities\b",
    r"\bpros and cons\b",
    r"\badvantages and disadvantages\b",
    r"\bstate of the art\b",
    r"\bbreakthrough\b",
    r"\bindustry overview\b",
    r"\bmarket overview\b",
    r"\bcompare .+? (companies|firms|products|solutions|platforms)\b",
]


def classify_query(query: str) -> str:
    """
    Returns 'quick' for simple factual questions or 'deep' for complex research queries.
    Falls back to word-count heuristic.
    """
    q_lower = query.strip().lower()

    # Explicit complexity signals first
    for pattern in _COMPLEX_PATTERNS:
        if re.search(pattern, q_lower):
            logger.debug(f"[QueryRouter] Complex pattern matched: {pattern!r}")
            return "deep"

    # Simple / quick signals
    for pattern in _SIMPLE_PATTERNS:
        if re.search(pattern, q_lower):
            logger.debug(f"[QueryRouter] Simple pattern matched: {pattern!r}")
            return "quick"

    # Heuristic: short queries with no complex markers → quick
    word_count = len(q_lower.split())
    if word_count <= 12:
        return "quick"

    return "deep"


# ---------------------------------------------------------------------------
# Quick Answer Service
# ---------------------------------------------------------------------------

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_QUICK_ANSWER_MODEL = "gemini-flash-lite-latest"
QUICK_ANSWER_FALLBACK_MODELS = (
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
)


def get_quick_answer_models() -> list[str]:
    """Return the configured model followed by current fallback model IDs."""
    configured_model = getattr(settings, "GEMINI_MODEL", None) or os.getenv("GEMINI_MODEL")
    primary_model = (
        configured_model.strip()
        if isinstance(configured_model, str) and configured_model.strip()
        else DEFAULT_QUICK_ANSWER_MODEL
    )
    return list(dict.fromkeys([primary_model, *QUICK_ANSWER_FALLBACK_MODELS]))


def _is_model_unavailable(error: httpx.HTTPStatusError) -> bool:
    """A 404 from Gemini generally means the requested model is unavailable."""
    return error.response.status_code == 404


def _safe_gemini_error(error: httpx.HTTPStatusError) -> RuntimeError:
    """Map upstream failures without exposing the API key or request URL."""
    status = error.response.status_code
    if status in (401, 403):
        return RuntimeError("Gemini API key is invalid or lacks permission.")
    if status == 429:
        return RuntimeError("Gemini API rate limit reached. Please try again shortly.")
    if status >= 500:
        return RuntimeError("Gemini API is temporarily unavailable. Please try again shortly.")
    return RuntimeError("Gemini Quick Answer is unavailable for the configured model.")


class QuickAnswerService:
    """Calls Gemini directly for simple queries without spawning the full pipeline."""

    def __init__(self):
        self._api_key = settings.GEMINI_API_KEY or ""

    async def answer(self, query: str) -> dict:
        """
        Returns a dict:
          {
            "answer": str,
            "model": str,
            "query": str,
            "mode": "quick"
          }
        Raises RuntimeError if the Gemini key is missing.
        """
        if not self._api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. "
                "Please add it to your .env file to enable Quick Answer mode."
            )

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are a knowledgeable, concise assistant. "
                                "Answer the following question clearly and accurately. "
                                "Keep your answer well-structured but succinct — "
                                "prefer 2-4 paragraphs or a short bullet list when appropriate.\n\n"
                                f"Question: {query}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 1024,
            },
        }

        params = {"key": self._api_key}

        last_error = None
        models = get_quick_answer_models()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for model in models:
                url = GEMINI_API_URL.format(model=model)
                try:
                    resp = await client.post(url, json=payload, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    if _is_model_unavailable(exc) and model != models[-1]:
                        logger.warning(
                            f"[QuickAnswer] Gemini model {model!r} unavailable; trying fallback."
                        )
                        continue
                    raise _safe_gemini_error(exc) from None
                except httpx.RequestError as exc:
                    logger.warning(f"[QuickAnswer] Gemini request failed: {type(exc).__name__}")
                    raise RuntimeError(
                        "Could not reach the Gemini API. Please try again shortly."
                    ) from None
            else:
                if last_error:
                    raise _safe_gemini_error(last_error) from None
                raise RuntimeError("Gemini Quick Answer is unavailable. Please try again shortly.")

        try:
            answer_text = (
                data["candidates"][0]["content"]["parts"][0]["text"]
            )
        except (KeyError, IndexError) as exc:
            logger.error(f"[QuickAnswer] Unexpected Gemini response structure: {data}")
            raise RuntimeError(f"Could not parse Gemini response: {exc}") from exc

        return {
            "answer": answer_text,
            "model": model,
            "query": query,
            "mode": "quick",
        }


# Module-level singleton
quick_answer_service = QuickAnswerService()
