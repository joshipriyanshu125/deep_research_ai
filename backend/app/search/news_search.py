import asyncio
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
import httpx
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


NEWS_PROVIDER_TIMEOUT_SECONDS = 15.0
DDG_TIMEOUT_SECONDS = 10.0


class NewsSearchEngine:
    async def _google_news_rss(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Public RSS fallback for market/news tracks when DDG is unavailable."""
        try:
            url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
            async with httpx.AsyncClient(
                timeout=NEWS_PROVIDER_TIMEOUT_SECONDS,
                headers={"User-Agent": "DeepResearchAI/1.0"},
            ) as client:
                response = await asyncio.wait_for(
                    client.get(url),
                    timeout=NEWS_PROVIDER_TIMEOUT_SECONDS,
                )
            if response.status_code != 200:
                return []

            root = ET.fromstring(response.text)
            results = []
            for item in root.findall(".//item")[:max_results]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                description = (item.findtext("description") or "").strip()
                if title and link:
                    results.append({
                        "title": title,
                        "url": link,
                        "snippet": description,
                        "source_type": "news",
                        "engine": "google-news-rss",
                    })
            return results
        except Exception as e:
            logger.warning(f"Google News RSS notice for '{query}': {e}")
            return []

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        results = []
        try:
            loop = asyncio.get_event_loop()
            def _ddg_news():
                with DDGS() as ddgs:
                    return list(ddgs.news(query, max_results=max_results))
            
            raw = await asyncio.wait_for(
                loop.run_in_executor(None, _ddg_news),
                timeout=DDG_TIMEOUT_SECONDS,
            )
            for item in raw:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("body", ""),
                    "source_type": "news",
                    "engine": "duckduckgo",
                })
            if results:
                return results
        except Exception as e:
            logger.warning(f"DDG news search fallback for '{query}': {e}")

        return await self._google_news_rss(query, max_results)


news_search_engine = NewsSearchEngine()
