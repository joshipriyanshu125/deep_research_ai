"""
Day 14 — Content Extractor
Unified extraction layer supporting HTML articles, tables, headings, lists,
PDF documents, author/date metadata parsing, paywall/JS detection, and zero-crash fault tolerance.
"""
import json
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
import trafilatura

from app.scraping.scraper import web_scraper, FetchResponse
from app.scraping.cleaner import html_cleaner
from app.scraping.pdf_extractor import pdf_extractor
from app.scraping.text_normalizer import text_normalizer
from app.utils.logger import logger

_PAYWALL_PATTERNS = re.compile(
    r"(subscribe to read|subscribe for full access|sign in to continue reading|"
    r"you have reached your limit of free articles|this content is for subscribers only|"
    r"exclusive for subscribers|premium subscription required|start your free trial to continue)",
    re.IGNORECASE,
)

_JS_ONLY_PATTERNS = re.compile(
    r"(please enable javascript|you need to enable javascript|javascript is required|"
    r"enable javascript to run this app)",
    re.IGNORECASE,
)


class ContentExtractor:
    """
    Extracts structured clean text and rich metadata from web URLs (HTML and PDF).
    Guaranteed never to throw an uncaught exception.
    """

    async def extract_from_url(self, url: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Extract content, title, author, and publication date from any URL.
        Returns a standardized dictionary with success status and error info.
        """
        try:
            res: FetchResponse = await web_scraper.fetch(url, timeout=timeout)

            # Handle network / HTTP failures (403, 404, 429, 500, timeout)
            if not res.success:
                return {
                    "url": url,
                    "text": "",
                    "title": "",
                    "author": None,
                    "date": None,
                    "content_type": res.content_type,
                    "is_pdf": res.is_pdf,
                    "is_paywall": False,
                    "is_js_required": False,
                    "success": False,
                    "error": res.error or f"HTTP {res.status_code} Failure",
                    "status_code": res.status_code,
                }

            # Route PDFs to PDFExtractor
            if res.is_pdf or url.lower().split("?")[0].endswith(".pdf"):
                extracted_pdf = pdf_extractor.extract(res.content)
                return {
                    "url": url,
                    "text": extracted_pdf.get("text", ""),
                    "title": extracted_pdf.get("title") or url.split("/")[-1],
                    "author": extracted_pdf.get("author"),
                    "date": extracted_pdf.get("date"),
                    "content_type": "application/pdf",
                    "is_pdf": True,
                    "is_paywall": False,
                    "is_js_required": False,
                    "success": extracted_pdf.get("success", False),
                    "error": extracted_pdf.get("error"),
                    "status_code": res.status_code,
                }

            # HTML extraction pipeline
            html = res.text
            if not html or not html.strip():
                return {
                    "url": url,
                    "text": "",
                    "title": "",
                    "author": None,
                    "date": None,
                    "content_type": "text/html",
                    "is_pdf": False,
                    "is_paywall": False,
                    "is_js_required": False,
                    "success": False,
                    "error": "Empty HTML body received",
                    "status_code": res.status_code,
                }

            return self._extract_html_content(url, html, res.status_code)

        except Exception as e:
            logger.warning(f"Unhandled extraction error for {url}: {e}")
            return {
                "url": url,
                "text": "",
                "title": "",
                "author": None,
                "date": None,
                "content_type": "unknown",
                "is_pdf": False,
                "is_paywall": False,
                "is_js_required": False,
                "success": False,
                "error": f"Extraction exception: {e}",
                "status_code": 500,
            }

    def _extract_html_content(self, url: str, html: str, status_code: int) -> Dict[str, Any]:
        """Parse HTML for clean text, headings, tables, metadata, and paywall/JS signals."""
        soup = BeautifulSoup(html, "html.parser")

        # 1. Parse rich metadata (Author, Date, Title, Description)
        meta = self._extract_metadata(soup, html)

        # 2. Check for Paywall & JS-required signals
        is_paywall = bool(_PAYWALL_PATTERNS.search(html[:10000]))
        is_js_required = bool(_JS_ONLY_PATTERNS.search(html[:3000]))

        # 3. Clean HTML with HTMLCleaner (strips cookies, ads, comments, footers, isolates main article)
        extracted_text = html_cleaner.clean(html)

        # 4. If extracted_text is short or empty, try Trafilatura
        if not extracted_text or len(extracted_text.strip()) < 50:
            try:
                traf_text = trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=True,
                    include_formatting=True,
                    no_fallback=False,
                )
                if traf_text:
                    extracted_text = traf_text
            except Exception as te:
                logger.debug(f"Trafilatura extraction warning for {url}: {te}")

        # 5. Fallback to OpenGraph / Meta description if text is still minimal
        if not extracted_text.strip() and meta.get("description"):
            extracted_text = meta["description"]

        clean_text = text_normalizer.normalize(extracted_text)
        success = bool(clean_text)

        title = meta.get("title") or ""
        if not title and soup.title and soup.title.string:
            title = soup.title.string.strip()

        return {
            "url": url,
            "text": clean_text,
            "title": title,
            "author": meta.get("author"),
            "date": meta.get("date"),
            "content_type": "text/html",
            "is_pdf": False,
            "is_paywall": is_paywall,
            "is_js_required": is_js_required,
            "success": success,
            "error": None if success else "No readable content extracted from page",
            "status_code": status_code,
        }

    def _extract_metadata(self, soup: BeautifulSoup, raw_html: str) -> Dict[str, Any]:
        """Extract title, author, date, and description from HTML meta tags and JSON-LD."""
        title = None
        author = None
        date = None
        description = None

        # A. Trafilatura metadata
        try:
            traf_meta = trafilatura.extract_metadata(raw_html)
            if traf_meta:
                title = traf_meta.title or None
                author = traf_meta.author or None
                date = traf_meta.date or None
                description = traf_meta.description or None
        except Exception:
            pass

        # B. OpenGraph & Meta tag overrides
        if not title:
            og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()

        if not author:
            meta_author = (
                soup.find("meta", attrs={"name": "author"})
                or soup.find("meta", property="article:author")
                or soup.find("meta", attrs={"name": "twitter:creator"})
            )
            if meta_author and meta_author.get("content"):
                author = meta_author["content"].strip()

        if not date:
            meta_date = (
                soup.find("meta", property="article:published_time")
                or soup.find("meta", attrs={"name": "pubdate"})
                or soup.find("meta", attrs={"name": "publication_date"})
                or soup.find("meta", attrs={"name": "date"})
            )
            if meta_date and meta_date.get("content"):
                date_val = meta_date["content"].strip()
                # Clean ISO date
                match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", date_val)
                date = match.group(1) if match else date_val[:10]

        if not description:
            meta_desc = (
                soup.find("meta", attrs={"name": "description"})
                or soup.find("meta", property="og:description")
                or soup.find("meta", attrs={"name": "twitter:description"})
            )
            if meta_desc and meta_desc.get("content"):
                description = meta_desc["content"].strip()

        # C. Schema.org JSON-LD parsing
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if script.string:
                    data = json.loads(script.string)
                    if isinstance(data, list) and data:
                        data = data[0]
                    if isinstance(data, dict):
                        if not title and data.get("headline"):
                            title = data["headline"]
                        if not date and data.get("datePublished"):
                            date_str = str(data["datePublished"])
                            match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", date_str)
                            date = match.group(1) if match else date_str[:10]
                        if not author:
                            auth_data = data.get("author")
                            if isinstance(auth_data, dict) and auth_data.get("name"):
                                author = auth_data["name"]
                            elif isinstance(auth_data, list) and auth_data and isinstance(auth_data[0], dict):
                                author = auth_data[0].get("name")
                            elif isinstance(auth_data, str):
                                author = auth_data
            except Exception:
                continue

        return {
            "title": title,
            "author": author,
            "date": date,
            "description": description,
        }


content_extractor = ContentExtractor()
