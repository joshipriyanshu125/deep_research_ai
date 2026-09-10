"""
Day 13 — Search Result Processing
Standardizes, cleans, and enriches search results gathered across multiple queries
and search providers (web, news, academic) with URL, title, domain, snippet,
publication date, retrieved date, query, source type, and relevance score.
"""
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from app.database.models.source import (
    Source,
    SourceType,
    ProcessedSearchResult,
    extract_domain_from_url,
)
from app.utils.logger import logger
from app.utils.helpers import get_utc_now


def normalize_publication_date(val: Any) -> Optional[str]:
    """
    Attempt to normalize arbitrary date representations to YYYY-MM-DD or ISO string.
    Returns cleaned string or None.
    """
    if not val:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    
    val_str = str(val).strip()
    if not val_str:
        return None

    # Handle standard ISO YYYY-MM-DD
    match = re.search(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b", val_str)
    if match:
        return match.group(1).replace("/", "-")

    # Handle DD-MM-YYYY or DD/MM/YYYY
    match_dmy = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", val_str)
    if match_dmy:
        d, m, y = match_dmy.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    return val_str[:50]


class SearchResultProcessor:
    """
    Processes and standardizes raw search results into rich, validated structures.
    """

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract clean domain name from a URL."""
        return extract_domain_from_url(url)

    @classmethod
    def process_result(
        cls,
        raw_result: Dict[str, Any],
        query: str = "",
        default_source_type: str = SourceType.WEB,
        relevance_score: Optional[float] = None,
    ) -> ProcessedSearchResult:
        """
        Convert a raw result dictionary into a validated ProcessedSearchResult.
        Ensures all 9 mandatory fields are populated:
          - url
          - title
          - domain
          - snippet
          - publication_date
          - retrieved_date
          - query
          - source_type
          - relevance_score
        """
        url = (raw_result.get("url") or raw_result.get("href") or "").strip()
        title = (raw_result.get("title") or "Untitled Source").strip()
        snippet = (raw_result.get("snippet") or raw_result.get("body") or raw_result.get("content") or "").strip()
        
        domain = raw_result.get("domain") or cls.extract_domain(url)
        
        raw_pub_date = (
            raw_result.get("publication_date")
            or raw_result.get("published_date")
            or raw_result.get("date")
        )
        publication_date = normalize_publication_date(raw_pub_date)

        retrieved_date = raw_result.get("retrieved_date") or get_utc_now()
        if isinstance(retrieved_date, str):
            try:
                retrieved_date = datetime.fromisoformat(retrieved_date.replace("Z", "+00:00"))
            except Exception:
                retrieved_date = get_utc_now()

        item_query = raw_result.get("query") or query or ""
        source_type = raw_result.get("source_type") or default_source_type

        # Score resolution
        score = relevance_score if relevance_score is not None else raw_result.get("relevance_score", 0.0)
        try:
            score = float(score)
        except (ValueError, TypeError):
            score = 0.0

        metadata = raw_result.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        return ProcessedSearchResult(
            url=url,
            title=title,
            domain=domain,
            snippet=snippet,
            publication_date=publication_date,
            retrieved_date=retrieved_date,
            query=item_query,
            source_type=source_type,
            relevance_score=round(score, 4),
            metadata=metadata,
        )

    @classmethod
    def process_batch(
        cls,
        raw_results: List[Dict[str, Any]],
        query: str = "",
        default_source_type: str = SourceType.WEB,
    ) -> List[ProcessedSearchResult]:
        """Process a list of raw search results into ProcessedSearchResults."""
        processed = []
        for r in raw_results:
            try:
                item = cls.process_result(
                    r,
                    query=r.get("query", query),
                    default_source_type=r.get("source_type", default_source_type),
                    relevance_score=r.get("relevance_score"),
                )
                processed.append(item)
            except Exception as e:
                logger.warning(f"Failed to process search result item: {e}")
        return processed

    @classmethod
    def to_source(
        cls,
        processed: ProcessedSearchResult,
        research_id: str = "",
        clean_text: Optional[str] = None,
        raw_content: Optional[str] = None,
        author: Optional[str] = None,
        credibility_score: float = 0.8,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> Source:
        """
        Convert a ProcessedSearchResult into a fully-fledged database Source object.
        """
        meta = dict(processed.metadata)
        if additional_metadata:
            meta.update(additional_metadata)
        meta["query_used"] = processed.query

        text_clean = clean_text if clean_text is not None else processed.snippet
        text_raw = raw_content if raw_content is not None else text_clean

        return Source(
            research_id=research_id,
            url=processed.url,
            title=processed.title,
            domain=processed.domain,
            snippet=processed.snippet,
            publication_date=processed.publication_date,
            published_date=processed.publication_date,
            retrieved_date=processed.retrieved_date,
            query=processed.query,
            source_type=processed.source_type,
            relevance_score=processed.relevance_score,
            credibility_score=credibility_score,
            raw_content=text_raw[:4000] if text_raw else "",
            clean_text=text_clean[:4000] if text_clean else "",
            author=author,
            metadata=meta,
        )


search_result_processor = SearchResultProcessor()
result_processor = search_result_processor
