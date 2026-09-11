"""
Day 26 — Source Memory (Global URL Registry & Credibility Ledger)

Maintains a cross-run source repository to:
  - Cache scraped source text and PDF evidence blocks across research sessions
  - Prevent redundant network scraping / parsing
  - Track reuse frequency and citation metrics
  - Accumulate historical domain credibility metrics
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.utils.helpers import get_utc_now


class CachedSource(BaseModel):
    url: str
    domain: str
    title: str
    source_type: str = "web"
    clean_text: str = ""
    evidence_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    credibility_score: float = 0.5
    first_seen: datetime = Field(default_factory=get_utc_now)
    last_accessed: datetime = Field(default_factory=get_utc_now)
    reuse_count: int = 1
    cited_count: int = 0
    research_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SourceMemory:
    """
    Global source memory across all research runs.
    """

    def __init__(self):
        self._sources: Dict[str, CachedSource] = {}  # url -> CachedSource
        self._domain_stats: Dict[str, Dict[str, Any]] = {}  # domain -> stats

    def record_source(
        self,
        url: str,
        title: str,
        domain: str,
        clean_text: str,
        source_type: str = "web",
        evidence_blocks: Optional[List[Dict[str, Any]]] = None,
        credibility_score: float = 0.5,
        research_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CachedSource:
        """Register or update a source in the global cache."""
        norm_url = url.strip().lower()
        now = get_utc_now()

        if norm_url in self._sources:
            cached = self._sources[norm_url]
            cached.reuse_count += 1
            cached.last_accessed = now
            if research_id and research_id not in cached.research_ids:
                cached.research_ids.append(research_id)
            if clean_text and len(clean_text) > len(cached.clean_text):
                cached.clean_text = clean_text
            if evidence_blocks:
                cached.evidence_blocks = evidence_blocks
            return cached

        cached = CachedSource(
            url=url,
            domain=domain.lower().strip() if domain else "",
            title=title,
            source_type=source_type,
            clean_text=clean_text,
            evidence_blocks=evidence_blocks or [],
            credibility_score=credibility_score,
            first_seen=now,
            last_accessed=now,
            reuse_count=1,
            research_ids=[research_id] if research_id else [],
            metadata=metadata or {},
        )
        self._sources[norm_url] = cached

        # Update domain stats
        dom = cached.domain
        if dom:
            if dom not in self._domain_stats:
                self._domain_stats[dom] = {"sources_count": 0, "avg_credibility": credibility_score}
            self._domain_stats[dom]["sources_count"] += 1

        return cached

    def find_cached_source(self, url: str) -> Optional[CachedSource]:
        """Lookup previously scraped source by URL."""
        return self._sources.get(url.strip().lower()) if url else None

    def record_citation(self, url: str) -> None:
        """Increment citation counter for a source."""
        cached = self.find_cached_source(url)
        if cached:
            cached.cited_count += 1

    def get_frequently_used_sources(self, limit: int = 10) -> List[CachedSource]:
        """Return sources sorted by reuse & citation count."""
        sources = list(self._sources.values())
        sources.sort(key=lambda s: (s.reuse_count + s.cited_count), reverse=True)
        return sources[:limit]

    def count(self) -> int:
        return len(self._sources)

    def clear(self) -> None:
        self._sources.clear()
        self._domain_stats.clear()


source_memory = SourceMemory()
