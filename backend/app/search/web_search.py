import asyncio
import re
import httpx
from typing import List, Dict, Any
from app.config.settings import settings
from app.utils.logger import logger
import warnings
warnings.filterwarnings("ignore", message=".*duckduckgo_search.*")
warnings.filterwarnings("ignore", message=".*renamed to.*")
warnings.filterwarnings("ignore", message=".*ddgs.*")
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


SEARCH_PROVIDER_TIMEOUT_SECONDS = 15.0
DDG_TIMEOUT_SECONDS = 10.0


class WebSearchEngine:
    async def _wikipedia_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Use Wikipedia's public search API as a real, citation-safe fallback."""
        try:
            async with httpx.AsyncClient(
                timeout=SEARCH_PROVIDER_TIMEOUT_SECONDS,
                headers={"User-Agent": "DeepResearchAI/1.0"},
            ) as client:
                res = await asyncio.wait_for(
                    client.get(
                        "https://en.wikipedia.org/w/api.php",
                        params={
                            "action": "query",
                            "list": "search",
                            "srsearch": query,
                            "srlimit": max_results,
                            "format": "json",
                        },
                    ),
                    timeout=SEARCH_PROVIDER_TIMEOUT_SECONDS,
                )
                if res.status_code != 200:
                    return []
                data = res.json()
                results = []
                for item in data.get("query", {}).get("search", []):
                    title = (item.get("title") or "").strip()
                    if not title:
                        continue
                    snippet = re.sub(r"<[^>]+>", "", item.get("snippet") or "")
                    results.append({
                        "title": title,
                        "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                        "snippet": snippet,
                        "source_type": "web",
                        "engine": "wikipedia",
                    })
                return results
        except Exception as e:
            logger.warning(f"Wikipedia search notice for '{query}': {e}")
            return []

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        seen_urls = set()

        # 1. Tavily AI Search (Deep Research optimized)
        if settings.TAVILY_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=SEARCH_PROVIDER_TIMEOUT_SECONDS) as client:
                    res = await asyncio.wait_for(
                        client.post(
                            "https://api.tavily.com/search",
                            json={"query": query, "api_key": settings.TAVILY_API_KEY, "max_results": max_results},
                        ),
                        timeout=SEARCH_PROVIDER_TIMEOUT_SECONDS,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        for r in data.get("results", []):
                            url = r.get("url", "")
                            if url and url not in seen_urls:
                                seen_urls.add(url)
                                results.append({
                                    "title": r.get("title", ""),
                                    "url": url,
                                    "snippet": r.get("content", ""),
                                    "source_type": "web",
                                    "engine": "tavily"
                                })
            except Exception as e:
                logger.warning(f"Tavily search notice for '{query}': {e}")

        # 2. Serper Google Search (Live Google Index)
        if settings.SERPER_API_KEY and len(results) < max_results:
            try:
                headers = {"X-API-KEY": settings.SERPER_API_KEY, "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=SEARCH_PROVIDER_TIMEOUT_SECONDS) as client:
                    res = await asyncio.wait_for(
                        client.post(
                            "https://google.serper.dev/search",
                            headers=headers,
                            json={"q": query, "num": max_results},
                        ),
                        timeout=SEARCH_PROVIDER_TIMEOUT_SECONDS,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        for r in data.get("organic", []):
                            url = r.get("link", "")
                            if url and url not in seen_urls:
                                seen_urls.add(url)
                                results.append({
                                    "title": r.get("title", ""),
                                    "url": url,
                                    "snippet": r.get("snippet", ""),
                                    "source_type": "web",
                                    "engine": "serper"
                                })
            except Exception as e:
                logger.warning(f"Serper search notice for '{query}': {e}")

        # 3. DuckDuckGo Search (Fallback live engine)
        if len(results) < max_results:
            try:
                loop = asyncio.get_event_loop()
                def _ddg():
                    with DDGS() as ddgs:
                        return list(ddgs.text(query, max_results=max_results))
                
                raw_results = await asyncio.wait_for(
                    loop.run_in_executor(None, _ddg),
                    timeout=DDG_TIMEOUT_SECONDS,
                )
                for item in raw_results:
                    url = item.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        results.append({
                            "title": item.get("title", ""),
                            "url": url,
                            "snippet": item.get("body", ""),
                            "source_type": "web",
                            "engine": "duckduckgo"
                        })
            except Exception as e:
                logger.warning(f"DuckDuckGo search notice for '{query}': {e}")

        if results:
            return results[:max_results]

        # Never manufacture source records when live providers fail. A public
        # Wikipedia lookup is still a real, traceable source; if it also fails,
        # return an empty list so the orchestrator can mark the run failed
        # instead of publishing a report with invented evidence.
        return await self._wikipedia_search(query, max_results)


web_search_engine = WebSearchEngine()
