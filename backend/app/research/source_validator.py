"""
Source Validator & Filter.
Enforces a rigorous pre-graph source validation stage:
- Discards / invalidates synthetic placeholder sources (e.g. generated TechCrunch news slugs, template snippets)
- Rejects empty, corrupted, or unreachable placeholder artifacts
- Prevents placeholder sources from receiving high credibility or entering the research graph
"""
import re
from typing import List, Tuple, Optional, Any
from dataclasses import dataclass
from app.database.models.source import Source
from app.utils.logger import logger


# Common patterns found in generated placeholder / synthetic fallback sources
_PLACEHOLDER_URL_PATTERNS = [
    re.compile(r"https?://(?:www\.)?techcrunch\.com/news/[a-z0-9-]+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?research\.org/topics/[a-z0-9-]+", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?example\.(?:com|org|net)", re.IGNORECASE),
]

_PLACEHOLDER_SNIPPET_PATTERNS = [
    re.compile(r"Market analysis and commercial roadmap milestones announced for", re.IGNORECASE),
    re.compile(r"Overview, architectural breakthroughs, and quantitative benchmarks regarding", re.IGNORECASE),
    re.compile(r"State-of-the-art developments, scalability analysis, and open challenges in", re.IGNORECASE),
    re.compile(r"Industry Update: Breakthroughs in", re.IGNORECASE),
]


@dataclass
class SourceValidationResult:
    is_valid: bool
    is_placeholder: bool
    reason: str


class SourceValidator:
    """
    Validates Source items before they enter the research graph or evidence extraction.
    """

    def is_placeholder(self, source: Any) -> Tuple[bool, str]:
        """
        Check if a source is a synthetic placeholder or mock artifact.
        """
        url = getattr(source, "url", "") or ""
        snippet = getattr(source, "snippet", "") or ""
        title = getattr(source, "title", "") or ""
        content = getattr(source, "content", "") or getattr(source, "clean_text", "") or ""

        # 1. Check URL patterns
        for pat in _PLACEHOLDER_URL_PATTERNS:
            if pat.search(url):
                return True, f"Matched placeholder URL pattern: {pat.pattern}"

        # 2. Check snippet patterns
        for pat in _PLACEHOLDER_SNIPPET_PATTERNS:
            if pat.search(snippet):
                return True, f"Matched placeholder snippet pattern: {pat.pattern}"
            if pat.search(title):
                return True, f"Matched placeholder title pattern: {pat.pattern}"
            if pat.search(content[:300]):
                return True, f"Matched placeholder content pattern: {pat.pattern}"

        # 3. Check for obvious template artifact URLs (e.g. query embedded in path)
        query = getattr(source, "query", "") or getattr(source, "query_used", "") or ""
        if query and len(query) > 15:
            slug = query.replace(" ", "-").lower()[:30]
            if f"/news/{slug}" in url.lower() or f"/topics/{slug}" in url.lower():
                return True, "URL path contains raw query slug (synthetic artifact)"

        return False, "Legitimate source"

    def validate(self, source: Any) -> SourceValidationResult:
        """
        Validates a single source.
        """
        url = getattr(source, "url", "") or ""
        if not url or not url.startswith(("http://", "https://")):
            return SourceValidationResult(
                is_valid=False,
                is_placeholder=False,
                reason="Invalid or missing URL scheme",
            )

        is_ph, ph_reason = self.is_placeholder(source)
        if is_ph:
            # Set credibility score to 0.0 so it can never achieve 1.0 confidence
            if hasattr(source, "credibility_score"):
                source.credibility_score = 0.0
            return SourceValidationResult(
                is_valid=False,
                is_placeholder=True,
                reason=ph_reason,
            )

        snippet = getattr(source, "snippet", "") or ""
        content = getattr(source, "clean_text", "") or getattr(source, "content", "") or ""
        if not snippet.strip() and not content.strip():
            return SourceValidationResult(
                is_valid=False,
                is_placeholder=False,
                reason="Source has neither snippet nor content",
            )

        return SourceValidationResult(
            is_valid=True,
            is_placeholder=False,
            reason="Valid authoritative source",
        )

    def filter_valid_sources(self, sources: List[Source]) -> List[Source]:
        """
        Filters a batch of sources, removing any placeholders or invalid items.
        """
        valid_sources: List[Source] = []
        for s in sources:
            res = self.validate(s)
            if res.is_valid:
                valid_sources.append(s)
            else:
                logger.info(f"[SourceValidator] Rejected source '{getattr(s, 'url', '')}': {res.reason}")
        return valid_sources


source_validator = SourceValidator()
