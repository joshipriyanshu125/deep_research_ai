"""
Day 12 & 13 — Web Search Agent & Result Processing

Upgraded Web Research Agent implementing the full research loop:
  Research Question
        ↓
  Generate search queries (multi-angle query generation)
        ↓
  Search Web (parallel bounded search)
        ↓
  Collect & Deduplicate results
        ↓
  Rank results (relevance & domain authority)
        ↓
  Open useful pages (top-K parallel extraction)
        ↓
  Extract information & Process structured Search Results & Sources
"""
import asyncio
from typing import List, Dict, Any, Optional
from app.search.web_search import web_search_engine
from app.search.news_search import news_search_engine
from app.search.query_generator import query_generator
from app.search.result_ranker import result_ranker
from app.search.result_processor import search_result_processor
from app.scraping.extractor import content_extractor
from app.database.models.source import Source, SourceType, ProcessedSearchResult
from app.utils.logger import logger


class DeepWebResearchAgent:
    """
    Multi-query web research agent that expands research questions into
    diverse sub-queries, executes parallel searches, ranks results by relevance,
    and extracts full content from top candidate pages with structured processing.
    """

    def __init__(self, max_concurrency: int = 4):
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def execute(
        self,
        query: str,
        research_id: str,
        is_market: bool = False,
        max_queries: int = 6,
        top_k: int = 8,
        category: Optional[str] = None,
    ) -> List[Source]:
        """
        Execute full multi-query research workflow for a question/topic.

        Args:
            query: The research question or topic (e.g. "Indian EV market")
            research_id: ID of the parent research session
            is_market: Whether this is market-focused research (uses news/market sources)
            max_queries: Number of distinct search queries to generate
            top_k: Max number of top-ranked pages to open and extract
            category: Optional template category ("web" | "academic" | "market")
        """
        if category is None:
            category = "market" if is_market else "web"

        default_source_type = SourceType.COMPANY if is_market else SourceType.WEB
        logger.info(f"DeepWebResearchAgent starting research for query: '{query}' (is_market={is_market})")

        # 1. Generate multi-angle search queries
        queries = await query_generator.generate_queries(
            question=query,
            n=max_queries,
            category=category,
        )
        if not queries:
            queries = [query]

        logger.info(f"DeepWebResearchAgent generated {len(queries)} queries: {queries}")

        # 2. Parallel search across queries
        search_tasks = [
            self._search_single_query(q, is_market=is_market)
            for q in queries
        ]
        search_results_by_query = await asyncio.gather(*search_tasks, return_exceptions=True)

        # 3. Collect & deduplicate results across queries by URL
        seen_urls = set()
        deduped_results: List[Dict[str, Any]] = []

        for q, res in zip(queries, search_results_by_query):
            if isinstance(res, Exception):
                logger.warning(f"Search query failed '{q}': {res}")
                continue
            for item in res:
                url = (item.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                item_copy = dict(item)
                item_copy["query"] = q
                item_copy["query_used"] = q
                item_copy["source_type"] = item_copy.get("source_type") or default_source_type
                deduped_results.append(item_copy)

        logger.info(f"Collected {len(deduped_results)} unique search results across all queries.")

        if not deduped_results:
            logger.warning(f"No search results found for query: '{query}'")
            return []

        # 4. Rank results by relevance to original research question
        ranked_results = result_ranker.rank(question=query, results=deduped_results)

        # 5. Select top-K pages to scrape
        top_candidates = ranked_results[:top_k]
        logger.info(f"Selected top {len(top_candidates)} URLs to extract full content.")

        # 6. Parallel scrape & extract content
        scrape_tasks = [
            self._extract_page_content(item)
            for item in top_candidates
        ]
        extractions = await asyncio.gather(*scrape_tasks, return_exceptions=True)

        # 7. Standardize and Build enriched Source objects using SearchResultProcessor
        sources: List[Source] = []
        for idx, (candidate, ext) in enumerate(zip(top_candidates, extractions)):
            if isinstance(ext, Exception):
                logger.warning(f"Failed extraction for {candidate.get('url')}: {ext}")
                ext_data = {}
            else:
                ext_data = ext or {}

            # Process standardized search result
            processed_item: ProcessedSearchResult = search_result_processor.process_result(
                raw_result=candidate,
                query=candidate.get("query_used", query),
                default_source_type=default_source_type,
                relevance_score=candidate.get("relevance_score", 0.8),
            )

            # Override title and date if better info was extracted
            if ext_data.get("title"):
                processed_item.title = ext_data["title"]
            if ext_data.get("date") and not processed_item.publication_date:
                processed_item.publication_date = ext_data["date"]

            text_content = ext_data.get("text") or processed_item.snippet or ""
            author = ext_data.get("author")

            source = search_result_processor.to_source(
                processed=processed_item,
                research_id=research_id,
                clean_text=text_content,
                raw_content=text_content,
                author=author,
                credibility_score=0.8,
                additional_metadata={
                    "rank": idx + 1,
                    "word_count": len(text_content.split()),
                },
            )
            sources.append(source)

        # 8. Score credibility across all 6 dimensions with cross-source agreement
        from app.research.credibility import source_credibility_scorer
        sources = source_credibility_scorer.evaluate_batch(sources, question=query)

        logger.info(f"DeepWebResearchAgent completed with {len(sources)} sources built and scored.")
        return sources

    async def _search_single_query(self, query: str, is_market: bool) -> List[Dict[str, Any]]:
        async with self._semaphore:
            if is_market:
                return await news_search_engine.search(query, max_results=4)
            else:
                return await web_search_engine.search(query, max_results=4)

    async def _extract_page_content(self, item: Dict[str, Any]) -> Dict[str, Any]:
        url = item.get("url")
        if not url:
            return {}
        async with self._semaphore:
            try:
                return await content_extractor.extract_from_url(url)
            except Exception as e:
                logger.warning(f"Extraction error for {url}: {e}")
                return {"text": item.get("snippet", ""), "title": item.get("title", "")}


# Backward-compatible alias
class WebAgent(DeepWebResearchAgent):
    """Alias for DeepWebResearchAgent to maintain backwards compatibility."""
    pass


# Default singleton instance
deep_web_research_agent = DeepWebResearchAgent()
web_agent = deep_web_research_agent
