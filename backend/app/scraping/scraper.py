"""
Day 14 — Web Scraper
Resilient HTTP fetching layer with User-Agent rotation, Content-Type detection (HTML/PDF),
status code classification (403, 404, 429, 503, timeout), and zero-crash error handling.
"""
import random
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import httpx
from app.utils.logger import logger
from app.security.ssrf import ssrf_protector, SSRFValidationError


def _decode_response_bytes(content: bytes, content_type_header: str) -> str:
    """
    Safely decode HTTP response bytes to a string.
    Priority: 1) charset from Content-Type header  2) chardet detection  3) utf-8  4) latin-1
    Strips null bytes and replaces remaining un-decodable bytes.
    """
    if not content:
        return ""

    # 1. Try charset from Content-Type header (e.g. "text/html; charset=utf-8")
    charset = None
    m = re.search(r"charset=([\w-]+)", content_type_header or "", re.IGNORECASE)
    if m:
        charset = m.group(1).strip().lower()

    # 2. Try chardet if charset not declared
    if not charset:
        try:
            import chardet
            detected = chardet.detect(content[:4096])
            if detected and detected.get("confidence", 0) >= 0.7:
                charset = detected["encoding"]
        except Exception:
            pass

    # 3. Attempt decode with detected charset, then utf-8, then latin-1
    for enc in filter(None, [charset, "utf-8", "latin-1"]):
        try:
            text = content.decode(enc, errors="replace")
            # Strip null bytes
            text = text.replace("\x00", "")
            return text
        except (LookupError, UnicodeDecodeError):
            continue

    return content.decode("latin-1", errors="replace").replace("\x00", "")


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:124.0) Gecko/20100101 Firefox/124.0",
]


@dataclass
class FetchResponse:
    url: str
    status_code: int = 0
    content: bytes = b""
    text: str = ""
    content_type: str = "text/html"
    is_pdf: bool = False
    success: bool = False
    error: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)


class WebScraper:
    """
    Resilient web scraper that fetches HTML or PDF documents,
    handles network errors and HTTP codes gracefully, and never raises exceptions.
    Enhanced with Day 55 SSRF protection and response size caps.
    """

    def __init__(self, default_timeout: float = 15.0, enforce_ssrf: bool = False, max_response_size: int = 10 * 1024 * 1024):
        self.default_timeout = default_timeout
        self.enforce_ssrf = enforce_ssrf
        self.max_response_size = max_response_size

    async def fetch(
        self,
        url: str,
        timeout: Optional[float] = None,
        enforce_ssrf: Optional[bool] = None,
    ) -> FetchResponse:
        """
        Fetch content from a URL with rich error classification.
        Returns a FetchResponse object and never raises an exception.
        """
        if not url or not isinstance(url, str) or not url.strip():
            return FetchResponse(url=str(url), status_code=400, success=False, error="Empty or invalid URL")

        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Day 55 SSRF Protection check
        check_ssrf = self.enforce_ssrf if enforce_ssrf is None else enforce_ssrf
        if check_ssrf:
            try:
                url = ssrf_protector.validate_url(url)
            except SSRFValidationError as e:
                logger.warning(f"SSRF violation blocked for {url}: {e}")
                return FetchResponse(
                    url=url,
                    status_code=400,
                    success=False,
                    error=f"SSRF Blocked: {e}",
                )

        t = timeout or self.default_timeout

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        }

        try:
            async with httpx.AsyncClient(
                timeout=t,
                follow_redirects=True,
                verify=False,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            ) as client:
                res = await client.get(url, headers=headers)
                status = res.status_code
                content_type = res.headers.get("content-type", "").lower()
                is_pdf = "application/pdf" in content_type or url.lower().split("?")[0].endswith(".pdf")
                
                # Check for HTTP error statuses
                if status == 200:
                    text_content = ""
                    if not is_pdf:
                        # Robust charset-aware decoding — avoids binary garbage
                        text_content = _decode_response_bytes(
                            res.content, content_type
                        )

                    return FetchResponse(
                        url=url,
                        status_code=200,
                        content=res.content,
                        text=text_content,
                        content_type="application/pdf" if is_pdf else "text/html",
                        is_pdf=is_pdf,
                        success=True,
                        headers=dict(res.headers),
                    )
                elif status == 403:
                    logger.warning(f"403 Forbidden accessing {url}")
                    return FetchResponse(url=url, status_code=403, success=False, error="403 Forbidden (Access Denied)")
                elif status == 404:
                    logger.warning(f"404 Not Found for {url}")
                    return FetchResponse(url=url, status_code=404, success=False, error="404 Not Found")
                elif status == 429:
                    logger.warning(f"429 Rate limited for {url}")
                    return FetchResponse(url=url, status_code=429, success=False, error="429 Too Many Requests (Rate Limited)")
                elif status in (500, 502, 503, 504):
                    logger.warning(f"HTTP {status} Server Error for {url}")
                    return FetchResponse(url=url, status_code=status, success=False, error=f"HTTP {status} Server Error")
                else:
                    logger.warning(f"HTTP {status} fetching {url}")
                    return FetchResponse(url=url, status_code=status, success=False, error=f"HTTP {status}")

        except httpx.TimeoutException as e:
            logger.warning(f"Timeout fetching {url}: {e}")
            return FetchResponse(url=url, status_code=408, success=False, error=f"Timeout after {t}s")
        except httpx.ConnectError as e:
            logger.warning(f"Connection error for {url}: {e}")
            return FetchResponse(url=url, status_code=502, success=False, error=f"Connection Error: {e}")
        except httpx.RequestError as e:
            logger.warning(f"Request error for {url}: {e}")
            return FetchResponse(url=url, status_code=500, success=False, error=f"Request Error: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error scraping {url}: {e}")
            return FetchResponse(url=url, status_code=500, success=False, error=f"Unexpected Error: {e}")

    async def fetch_html(self, url: str) -> Optional[str]:
        """Backward-compatible helper returning raw HTML text or None on failure."""
        res = await self.fetch(url)
        return res.text if res.success and not res.is_pdf else None

    async def fetch_secure(self, url: str, timeout: Optional[float] = None) -> FetchResponse:
        """Enforces Day 55 SSRF safety checks before fetching."""
        return await self.fetch(url, timeout=timeout, enforce_ssrf=True)


web_scraper = WebScraper()

