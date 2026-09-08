from typing import List, Dict, Any
from app.search.web_search import web_search_engine
from app.search.news_search import news_search_engine
from app.scraping.extractor import content_extractor
from app.database.models.source import Source, SourceType


class WebAgent:
    async def execute(self, query: str, research_id: str, is_market: bool = False) -> List[Source]:
        if is_market:
            search_items = await news_search_engine.search(query, max_results=3)
        else:
            search_items = await web_search_engine.search(query, max_results=3)

        sources = []
        for item in search_items:
            url = item.get("url")
            extraction = await content_extractor.extract_from_url(url)
            
            source = Source(
                research_id=research_id,
                url=url,
                title=extraction.get("title") or item.get("title", ""),
                source_type=SourceType.COMPANY if is_market else SourceType.WEB,
                snippet=item.get("snippet", ""),
                raw_content=extraction.get("text", "")[:4000],
                clean_text=extraction.get("text", "")[:4000],
                author=extraction.get("author"),
                published_date=extraction.get("date"),
                relevance_score=0.9
            )
            sources.append(source)
        return sources


web_agent = WebAgent()
