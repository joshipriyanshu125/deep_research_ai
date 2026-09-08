from typing import Optional, Dict, Any
import trafilatura
from app.scraping.scraper import web_scraper
from app.scraping.cleaner import html_cleaner
from app.utils.logger import logger


class ContentExtractor:
    async def extract_from_url(self, url: str) -> Dict[str, Any]:
        html = await web_scraper.fetch_html(url)
        if not html:
            return {"text": "", "title": "", "success": False}
        
        # 1. Try Trafilatura for clean main article extraction
        extracted_text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False
        )
        
        if not extracted_text:
            # 2. Fallback to BeautifulSoup cleaning
            extracted_text = html_cleaner.clean(html)
            
        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata and metadata.title else ""
        
        return {
            "text": extracted_text or "",
            "title": title,
            "author": metadata.author if metadata else None,
            "date": metadata.date if metadata else None,
            "success": bool(extracted_text)
        }


content_extractor = ContentExtractor()
