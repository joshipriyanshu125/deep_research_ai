"""
Day 12 — Result Ranker
Ranks a flat list of search results by relevance to the original research
question, using lightweight keyword overlap + domain authority heuristics.
No external dependencies — pure Python.
"""
import re
from typing import List, Dict, Any
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Domain authority bonuses / penalties
# ---------------------------------------------------------------------------

_HIGH_AUTHORITY_DOMAINS = {
    # Government / policy
    ".gov", ".gov.in", ".nic.in",
    # Academia
    ".edu", "arxiv.org", "scholar.google", "pubmed.ncbi", "researchgate.net",
    "jstor.org", "springer.com", "nature.com", "sciencedirect.com",
    # Trusted publishers / data sources
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "economist.com", "hbr.org", "mckinsey.com", "bcg.com",
    "statista.com", "iea.org", "worldbank.org", "imf.org",
    "niti.gov.in", "pib.gov.in",
}

_LOW_QUALITY_PATTERNS = {
    "pinterest.com", "reddit.com/r/", "quora.com", "yahoo.com/answers",
    "ehow.com", "answers.com", "wikihow.com", "reference.com",
}

_SPAM_SIGNAL_PATTERNS = re.compile(
    r"(buy now|click here|free download|sign up|subscribe now|"
    r"casino|forex|crypto trading|weight loss|adult)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need",
    "of", "in", "on", "at", "by", "for", "with", "to", "from",
    "as", "and", "or", "but", "not", "no", "nor", "so", "yet",
    "both", "either", "neither", "than", "that", "this", "these",
    "those", "what", "which", "who", "when", "where", "why", "how",
}


def _tokenise(text: str) -> List[str]:
    """Lower-case, split on non-alphanumeric, filter stop words."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _keyword_overlap_score(query_tokens: List[str], text: str) -> float:
    """Fraction of query tokens present in text (Jaccard-style recall)."""
    if not query_tokens:
        return 0.0
    text_tokens = set(_tokenise(text))
    hits = sum(1 for t in query_tokens if t in text_tokens)
    return hits / len(query_tokens)


# ---------------------------------------------------------------------------
# Ranker
# ---------------------------------------------------------------------------

class ResultRanker:
    """
    Score-and-sort a list of raw search result dicts.

    Each result dict is expected to have at least:
        title    (str)
        url      (str)
        snippet  (str)

    The ranker injects a `relevance_score` (0.0–1.0) into each result
    and returns them sorted descending.
    """

    # Scoring weights
    _W_TITLE = 0.40
    _W_SNIPPET = 0.35
    _W_SNIPPET_LEN = 0.10   # reward longer, more informative snippets
    _W_DOMAIN = 0.15         # domain authority bonus/penalty

    def rank(
        self,
        question: str,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Rank results by relevance to `question`.

        Returns a new list sorted highest relevance_score first.
        Each item has `relevance_score` field added/overwritten.
        """
        if not results:
            return []

        query_tokens = _tokenise(question)
        scored = [self._score(r, query_tokens) for r in results]
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        logger.debug(
            f"ResultRanker: ranked {len(scored)} results. "
            f"Top score={scored[0]['relevance_score']:.2f}"
        )
        return scored

    def _score(self, result: Dict[str, Any], query_tokens: List[str]) -> Dict[str, Any]:
        result = dict(result)  # shallow copy — don't mutate original
        title = result.get("title") or ""
        snippet = result.get("snippet") or ""
        url = result.get("url") or ""

        # --- Spam gate: immediately zero-score spam ---
        combined = f"{title} {snippet}"
        if _SPAM_SIGNAL_PATTERNS.search(combined):
            result["relevance_score"] = 0.0
            return result

        # --- Keyword overlap ---
        title_score = _keyword_overlap_score(query_tokens, title)
        snippet_score = _keyword_overlap_score(query_tokens, snippet)

        # --- Snippet length signal (normalised to ~300 chars = 1.0) ---
        snippet_len_score = min(len(snippet) / 300.0, 1.0)

        # --- Domain authority ---
        domain_score = self._domain_score(url)

        # --- Composite ---
        score = (
            self._W_TITLE * title_score
            + self._W_SNIPPET * snippet_score
            + self._W_SNIPPET_LEN * snippet_len_score
            + self._W_DOMAIN * domain_score
        )
        result["relevance_score"] = round(min(score, 1.0), 4)
        return result

    def _domain_score(self, url: str) -> float:
        url_lower = url.lower()

        for pattern in _LOW_QUALITY_PATTERNS:
            if pattern in url_lower:
                return 0.0

        for domain in _HIGH_AUTHORITY_DOMAINS:
            if domain in url_lower:
                return 1.0

        # Wikipedia — good general reference
        if "wikipedia.org" in url_lower:
            return 0.75

        # HTTPS bonus
        if url_lower.startswith("https://"):
            return 0.5

        return 0.3   # unknown HTTP domain


result_ranker = ResultRanker()
