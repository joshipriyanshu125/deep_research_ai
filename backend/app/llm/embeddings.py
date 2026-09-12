"""
Day 24 — Production Embedding Service

Multi-provider routing:
  Gemini text-embedding-004  (best quality, 768-dim)
    ↓ fallback
  OpenAI text-embedding-3-small  (reliable, 1536-dim → projected to 768)
    ↓ fallback
  sentence-transformers  (local, no API key required)
    ↓ fallback
  Deterministic hash-based pseudo-embedding  (always available, reproducible)

Features:
  - Single embed:  get_embedding(text)  → List[float]
  - Batch embed:   get_embeddings(texts) → List[List[float]]  (1 API call)
  - LRU cache:     identical text never re-embedded within a session
  - Unit normalization: all vectors are L2-normalized (cosine-ready)
  - Consistent 768-dim output regardless of provider
"""

import asyncio
import hashlib
import re
from collections import Counter

import numpy as np
import httpx
from functools import lru_cache
from typing import List, Optional, Dict, Any
from app.config.settings import settings
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 768          # canonical output dimension for all providers
_CACHE_MAX_SIZE = 1024       # max entries in the in-process LRU cache


# ---------------------------------------------------------------------------
# Deterministic Fallback (always available — no API key required)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "and", "for", "in", "of", "to", "by", "a", "an", "is", "are", "was", "were",
    "be", "been", "being", "with", "on", "at", "from", "as", "it", "its", "this", "that",
    "these", "those", "into", "over", "under", "after", "before", "between", "through", "during",
}


def _tokenize(text: str) -> List[str]:
    return [token for token in _TOKEN_RE.findall((text or "").lower()) if len(token) > 1 and token not in _STOPWORDS]


def _deterministic_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """
    Produce a stable, token-aware pseudo-embedding so text with shared terms
    remains semantically aligned even without an external embedding model.
    """
    tokens = _tokenize(text)
    if not tokens:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2 ** 32)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        return (vec / (norm + 1e-9)).tolist()

    counts = Counter(tokens)
    vec = np.zeros(dim, dtype=np.float32)
    for token, count in counts.items():
        seed = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        idx = seed % dim
        vec[idx] += float(count)
        vec[(seed >> 7) % dim] += float(count) * 0.5
        vec[(seed >> 13) % dim] += float(count) * 0.25

    if not np.any(vec):
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2 ** 32)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dim).astype(np.float32)

    return _normalize(vec.tolist())


def _normalize(vec: List[float]) -> List[float]:
    """L2-normalize a float vector."""
    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm < 1e-9:
        return arr.tolist()
    return (arr / norm).tolist()


def _project_to_dim(vec: List[float], target_dim: int) -> List[float]:
    """
    Project a vector to target_dim via deterministic linear projection.
    Used when a provider returns a different dimension than our canonical 768-dim.
    """
    src = np.array(vec, dtype=np.float32)
    src_dim = len(src)
    if src_dim == target_dim:
        return _normalize(vec)
    if src_dim > target_dim:
        # Truncate and re-normalize
        return _normalize(src[:target_dim].tolist())
    # Pad with zeros and re-normalize
    padded = np.zeros(target_dim, dtype=np.float32)
    padded[:src_dim] = src
    return _normalize(padded.tolist())


# ---------------------------------------------------------------------------
# Provider: Gemini text-embedding-004
# ---------------------------------------------------------------------------

class GeminiEmbeddingProvider:
    """
    Google Gemini Embeddings API.
    Model: text-embedding-004 → 768-dim natively.
    """
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def embed_one(self, text: str) -> Optional[List[float]]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    self.BASE_URL,
                    params={"key": self.api_key},
                    json={
                        "model": "models/text-embedding-004",
                        "content": {"parts": [{"text": text[:8192]}]},
                        "taskType": "RETRIEVAL_DOCUMENT",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    values = data.get("embedding", {}).get("values", [])
                    if values:
                        return _normalize(values)
        except Exception as e:
            logger.debug(f"Gemini embed failed: {e}")
        return None

    async def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Batch using individual calls (Gemini v1beta has no native batch API)."""
        tasks = [self.embed_one(t) for t in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        vecs: List[Optional[List[float]]] = []
        for r in results:
            if isinstance(r, Exception) or r is None:
                return None  # any failure → fall through to next provider
            vecs.append(r)
        return vecs


# ---------------------------------------------------------------------------
# Provider: OpenAI / OpenRouter text-embedding-3-small
# ---------------------------------------------------------------------------

class OpenAIEmbeddingProvider:
    """
    OpenAI Embeddings API (also used via OpenRouter).
    text-embedding-3-small → 1536-dim; projected to 768-dim.
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"input": [t[:8192] for t in texts], "model": self.model},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = sorted(data["data"], key=lambda x: x["index"])
                    return [_project_to_dim(item["embedding"], EMBEDDING_DIM) for item in items]
        except Exception as e:
            logger.debug(f"OpenAI embed failed: {e}")
        return None

    async def embed_one(self, text: str) -> Optional[List[float]]:
        result = await self.embed_batch([text])
        return result[0] if result else None


# ---------------------------------------------------------------------------
# Provider: Local sentence-transformers (optional dependency)
# ---------------------------------------------------------------------------

class LocalEmbeddingProvider:
    """
    Uses sentence-transformers locally (no API key required).
    Loads 'all-MiniLM-L6-v2' which produces 384-dim → projected to 768-dim.
    Only activated if sentence-transformers is installed.
    """
    _model = None
    _loaded = False

    @classmethod
    def _load(cls) -> bool:
        if cls._loaded:
            return cls._model is not None
        try:
            from sentence_transformers import SentenceTransformer
            cls._model = SentenceTransformer("all-MiniLM-L6-v2")
            cls._loaded = True
            logger.info("Loaded local sentence-transformer: all-MiniLM-L6-v2")
            return True
        except ImportError:
            cls._loaded = True  # mark as tried
            return False
        except Exception as e:
            logger.debug(f"sentence-transformers load failed: {e}")
            cls._loaded = True
            return False

    async def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        if not self._load() or self._model is None:
            return None
        try:
            loop = asyncio.get_event_loop()
            vecs = await loop.run_in_executor(
                None,
                lambda: self._model.encode(texts, normalize_embeddings=True).tolist(),
            )
            return [_project_to_dim(v, EMBEDDING_DIM) for v in vecs]
        except Exception as e:
            logger.debug(f"Local embed failed: {e}")
        return None

    async def embed_one(self, text: str) -> Optional[List[float]]:
        result = await self.embed_batch([text])
        return result[0] if result else None


# ---------------------------------------------------------------------------
# Main EmbeddingService — multi-provider with cache
# ---------------------------------------------------------------------------

class EmbeddingService:
    """
    Day 24 — Production Embedding Service.

    Provider routing (highest quality first):
      Gemini → OpenAI/OpenRouter → sentence-transformers → deterministic fallback

    Caching:
      In-process LRU cache of up to 1024 text → vector pairs.
      Eliminates redundant API calls for repeated chunks.

    Output:
      All providers return 768-dim unit-normalized float32 vectors.
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        # Resolve keys from settings
        self._gemini_key = gemini_api_key or settings.GEMINI_API_KEY or ""
        self._openai_key = openai_api_key or settings.OPENAI_API_KEY or ""
        self._openrouter_key = openrouter_api_key or settings.OPENROUTER_API_KEY or ""

        self.model = model or settings.EMBEDDING_MODEL or "text-embedding-3-small"
        base = base_url or settings.LLM_BASE_URL or "https://openrouter.ai/api/v1"

        # Decide which OpenAI-compat base to use
        openai_base = "https://api.openai.com/v1" if self._openai_key else base
        active_openai_key = self._openai_key or self._openrouter_key

        # Build provider chain
        self._gemini: Optional[GeminiEmbeddingProvider] = (
            GeminiEmbeddingProvider(self._gemini_key) if self._gemini_key else None
        )
        self._openai: Optional[OpenAIEmbeddingProvider] = (
            OpenAIEmbeddingProvider(active_openai_key, openai_base, self.model)
            if active_openai_key else None
        )
        self._local = LocalEmbeddingProvider()

        # In-process LRU cache (text hash → vector)
        self._cache: Dict[str, List[float]] = {}
        self._cache_order: List[str] = []  # for LRU eviction

        # Introspection
        self.embedding_dim = EMBEDDING_DIM
        self._provider_used: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_embedding(self, text: str) -> List[float]:
        """
        Embed a single text, returning a 768-dim unit-normalized vector.
        Results are cached — repeated calls for the same text are free.
        """
        if not text or not text.strip():
            return _deterministic_embedding("", EMBEDDING_DIM)

        text = text.strip()
        cache_key = self._cache_key(text)

        # Cache hit
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Single embed via batch of 1
        results = await self._embed_batch_internal([text])
        vec = results[0]
        self._put_cache(cache_key, vec)
        return vec

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embed a list of texts in a single API call.
        Per-text caching: only uncached texts hit the API.
        """
        if not texts:
            return []

        normalized = [t.strip() if t else "" for t in texts]
        cache_keys = [self._cache_key(t) for t in normalized]

        # Separate cached from uncached
        to_embed_indices: List[int] = []
        to_embed_texts: List[str] = []
        for i, (key, t) in enumerate(zip(cache_keys, normalized)):
            if key not in self._cache:
                to_embed_indices.append(i)
                to_embed_texts.append(t)

        # Batch embed only the uncached ones
        if to_embed_texts:
            new_vecs = await self._embed_batch_internal(to_embed_texts)
            for idx, vec in zip(to_embed_indices, new_vecs):
                self._put_cache(cache_keys[idx], vec)

        # Assemble final results (all from cache now)
        return [self._cache[k] for k in cache_keys]

    @property
    def provider(self) -> str:
        """Which provider was last used."""
        return self._provider_used or "fallback"

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()
        self._cache_order.clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "embedding_dim": self.embedding_dim,
            "cache_size": self.cache_size,
            "provider": self.provider,
            "model": self.model,
            "has_gemini": self._gemini is not None,
            "has_openai": self._openai is not None,
        }

    # ------------------------------------------------------------------
    # Internal: provider routing
    # ------------------------------------------------------------------

    async def _embed_batch_internal(self, texts: List[str]) -> List[List[float]]:
        """Try providers in order, fall back to deterministic on all failures."""

        # 1. Gemini
        if self._gemini:
            result = await self._gemini.embed_batch(texts)
            if result is not None:
                self._provider_used = "gemini"
                return result

        # 2. OpenAI / OpenRouter
        if self._openai:
            result = await self._openai.embed_batch(texts)
            if result is not None:
                self._provider_used = "openai"
                return result

        # 3. Local sentence-transformers
        result = await self._local.embed_batch(texts)
        if result is not None:
            self._provider_used = "sentence_transformers"
            return result

        # 4. Deterministic fallback (always succeeds)
        self._provider_used = "deterministic_fallback"
        return [_deterministic_embedding(t, EMBEDDING_DIM) for t in texts]

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def _put_cache(self, key: str, vec: List[float]) -> None:
        if key in self._cache:
            # Move to end (most recently used)
            self._cache_order.remove(key)
            self._cache_order.append(key)
            return
        # LRU eviction if at capacity
        if len(self._cache) >= _CACHE_MAX_SIZE:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]
        self._cache[key] = vec
        self._cache_order.append(key)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

embedding_service = EmbeddingService()


# ---------------------------------------------------------------------------
# Convenience helper for batch embedding outside the service
# ---------------------------------------------------------------------------

async def batch_embed(texts: List[str]) -> List[List[float]]:
    """Module-level convenience function for batch embedding."""
    return await embedding_service.get_embeddings(texts)
