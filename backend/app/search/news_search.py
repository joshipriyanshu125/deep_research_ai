import asyncio
from typing import List, Dict, Any
from app.utils.logger import logger
import warnings
warnings.filterwarnings("ignore", message=".*duckduckgo_search.*")
warnings.filterwarnings("ignore", message=".*renamed to.*")
warnings.filterwarnings("ignore", message=".*ddgs.*")
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS



class NewsSearchEngine:
    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        results = []
        try:
            loop = asyncio.get_event_loop()
            def _ddg_news():
                with DDGS() as ddgs:
                    return list(ddgs.news(query, max_results=max_results))
            
            raw = await loop.run_in_executor(None, _ddg_news)
            for item in raw:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("body", ""),
                    "source_type": "news"
                })
            if results:
                return results
        except Exception as e:
            logger.warning(f"DDG news search fallback for '{query}': {e}")

        return []


news_search_engine = NewsSearchEngine()
