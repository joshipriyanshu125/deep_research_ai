import httpx
from typing import Optional
from app.utils.logger import logger

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]


class WebScraper:
    async def fetch_html(self, url: str) -> Optional[str]:
        headers = {
            "User-Agent": USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    return res.text
                logger.warning(f"HTTP {res.status_code} fetching {url}")
        except Exception as e:
            logger.warning(f"Failed to scrape {url}: {e}")
        return None


web_scraper = WebScraper()
