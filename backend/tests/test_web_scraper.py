import io
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from pypdf import PdfWriter

from app.scraping.scraper import WebScraper, FetchResponse, web_scraper
from app.scraping.cleaner import HTMLCleaner, html_cleaner
from app.scraping.pdf_extractor import PDFExtractor, pdf_extractor
from app.scraping.extractor import ContentExtractor, content_extractor


class TestHTMLCleaner:
    def test_headings_preservation(self):
        cleaner = HTMLCleaner()
        html = """
        <html>
            <body>
                <h1>Main Research Title</h1>
                <p>Introduction paragraph.</p>
                <h2>Sub Section Analysis</h2>
                <p>Analysis details.</p>
                <h3>Technical Details</h3>
                <p>Metrics.</p>
            </body>
        </html>
        """
        cleaned = cleaner.clean(html)
        assert "# Main Research Title" in cleaned
        assert "## Sub Section Analysis" in cleaned
        assert "### Technical Details" in cleaned
        assert "Introduction paragraph." in cleaned

    def test_tables_preservation(self):
        cleaner = HTMLCleaner()
        html = """
        <html>
            <body>
                <table>
                    <thead>
                        <tr><th>Year</th><th>Sales (Units)</th><th>Growth</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>2024</td><td>1,500,000</td><td>+45%</td></tr>
                        <tr><td>2025</td><td>2,200,000</td><td>+46%</td></tr>
                    </tbody>
                </table>
            </body>
        </html>
        """
        cleaned = cleaner.clean(html)
        assert "| Year | Sales (Units) | Growth |" in cleaned
        assert "| --- | --- | --- |" in cleaned
        assert "| 2024 | 1,500,000 | +45% |" in cleaned
        assert "| 2025 | 2,200,000 | +46% |" in cleaned

    def test_lists_preservation(self):
        cleaner = HTMLCleaner()
        html = """
        <html>
            <body>
                <ul>
                    <li>First bullet point</li>
                    <li>Second bullet point</li>
                </ul>
                <ol>
                    <li>Step one</li>
                    <li>Step two</li>
                </ol>
            </body>
        </html>
        """
        cleaned = cleaner.clean(html)
        assert "- First bullet point" in cleaned
        assert "- Second bullet point" in cleaned
        assert "1. Step one" in cleaned
        assert "2. Step two" in cleaned

    def test_unwanted_tags_stripped(self):
        cleaner = HTMLCleaner()
        html = """
        <html>
            <head><style>.ad { color: red; }</style></head>
            <body>
                <header><nav>Home | About</nav></header>
                <script>console.log("tracker");</script>
                <article><p>Real valuable content here.</p></article>
                <footer>Copyright 2026</footer>
            </body>
        </html>
        """
        cleaned = cleaner.clean(html)
        assert "Real valuable content here." in cleaned
        assert "console.log" not in cleaned
        assert ".ad {" not in cleaned
        assert "Home | About" not in cleaned
        assert "Copyright 2026" not in cleaned


class TestPDFExtractor:
    def _create_sample_pdf_bytes(self) -> bytes:
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        # Note: PdfWriter can set metadata
        writer.add_metadata({
            "/Title": "Electric Vehicle Market Research",
            "/Author": "Dr. A. Sharma",
        })
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def test_extract_pdf_metadata(self):
        pdf_bytes = self._create_sample_pdf_bytes()
        res = pdf_extractor.extract(pdf_bytes)
        assert res["is_pdf"] is True
        assert res["title"] == "Electric Vehicle Market Research"
        assert res["author"] == "Dr. A. Sharma"
        assert res["page_count"] == 1

    def test_corrupt_pdf_bytes_does_not_crash(self):
        res = pdf_extractor.extract(b"Not a valid PDF header stream content")
        assert res["success"] is False
        assert res["is_pdf"] is True
        assert res["error"] is not None

    def test_empty_pdf_bytes_does_not_crash(self):
        res = pdf_extractor.extract(b"")
        assert res["success"] is False
        assert res["page_count"] == 0


class TestWebScraper:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        scraper = WebScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
        mock_resp.content = b"<html><body><p>Hello World</p></body></html>"
        mock_resp.text = "<html><body><p>Hello World</p></body></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            res = await scraper.fetch("https://example.com/test")
            assert res.success is True
            assert res.status_code == 200
            assert "Hello World" in res.text
            assert res.is_pdf is False

    @pytest.mark.asyncio
    async def test_fetch_403_forbidden(self):
        scraper = WebScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.headers = {}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            res = await scraper.fetch("https://paywalled-site.com/locked")
            assert res.success is False
            assert res.status_code == 403
            assert "403 Forbidden" in res.error

    @pytest.mark.asyncio
    async def test_fetch_404_not_found(self):
        scraper = WebScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            res = await scraper.fetch("https://example.com/missing-page")
            assert res.success is False
            assert res.status_code == 404
            assert "404 Not Found" in res.error

    @pytest.mark.asyncio
    async def test_fetch_timeout(self):
        scraper = WebScraper()
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Read timeout")):
            res = await scraper.fetch("https://slow-site.com", timeout=1.0)
            assert res.success is False
            assert res.status_code == 408
            assert "Timeout" in res.error

    @pytest.mark.asyncio
    async def test_invalid_url_no_crash(self):
        scraper = WebScraper()
        res = await scraper.fetch("")
        assert res.success is False
        assert res.status_code == 400


class TestContentExtractor:
    @pytest.mark.asyncio
    async def test_extract_html_with_metadata_and_tables(self):
        html_doc = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>India EV Market Report 2026</title>
            <meta name="author" content="Priyanshu Joshi">
            <meta property="article:published_time" content="2026-03-01">
        </head>
        <body>
            <h1>Comprehensive EV Industry Analysis</h1>
            <p>India is rapidly accelerating EV infrastructure across commercial and personal segments.</p>
            <table>
                <tr><th>Segment</th><th>Share</th></tr>
                <tr><td>2-Wheelers</td><td>55%</td></tr>
                <tr><td>4-Wheelers</td><td>25%</td></tr>
            </table>
            <ul>
                <li>Government subsidies under FAME III</li>
                <li>Battery cell manufacturing local hubs</li>
            </ul>
        </body>
        </html>
        """

        mock_fetch = FetchResponse(
            url="https://industry-insights.com/ev-report",
            status_code=200,
            content=html_doc.encode("utf-8"),
            text=html_doc,
            content_type="text/html",
            is_pdf=False,
            success=True,
        )

        with patch("app.scraping.scraper.web_scraper.fetch", new_callable=AsyncMock, return_value=mock_fetch):
            result = await content_extractor.extract_from_url("https://industry-insights.com/ev-report")

            assert result["success"] is True
            assert result["author"] == "Priyanshu Joshi"
            assert result["date"] == "2026-03-01"
            assert "EV infrastructure" in result["text"]
            assert "| Segment | Share |" in result["text"] or "2-Wheelers" in result["text"]
            assert "FAME III" in result["text"]

    @pytest.mark.asyncio
    async def test_extract_json_ld_metadata(self):
        html_doc = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "NewsArticle",
                "headline": "Breakthrough in Solid-State Battery Tech",
                "datePublished": "2026-02-20T08:00:00Z",
                "author": {"@type": "Person", "name": "Elena Vance"}
            }
            </script>
        </head>
        <body>
            <article>
                <p>Solid-state batteries achieve 500 Wh/kg density in commercial trials.</p>
            </article>
        </body>
        </html>
        """
        mock_fetch = FetchResponse(
            url="https://battery-tech.org/solid-state",
            status_code=200,
            content=html_doc.encode("utf-8"),
            text=html_doc,
            content_type="text/html",
            is_pdf=False,
            success=True,
        )

        with patch("app.scraping.scraper.web_scraper.fetch", new_callable=AsyncMock, return_value=mock_fetch):
            result = await content_extractor.extract_from_url("https://battery-tech.org/solid-state")
            assert result["success"] is True
            assert result["title"] == "Breakthrough in Solid-State Battery Tech"
            assert result["author"] == "Elena Vance"
            assert result["date"] == "2026-02-20"

    @pytest.mark.asyncio
    async def test_paywall_detection(self):
        html_doc = """
        <html>
        <body>
            <h1>Premium Energy Analysis</h1>
            <p>Subscribe to read the full market report.</p>
            <div class="paywall">You have reached your limit of free articles. Exclusive for subscribers.</div>
        </body>
        </html>
        """
        mock_fetch = FetchResponse(
            url="https://paywalled.com/article",
            status_code=200,
            content=html_doc.encode("utf-8"),
            text=html_doc,
            content_type="text/html",
            is_pdf=False,
            success=True,
        )

        with patch("app.scraping.scraper.web_scraper.fetch", new_callable=AsyncMock, return_value=mock_fetch):
            result = await content_extractor.extract_from_url("https://paywalled.com/article")
            assert result["is_paywall"] is True

    @pytest.mark.asyncio
    async def test_js_required_detection(self):
        html_doc = """
        <html>
        <body>
            <noscript>Please enable JavaScript to view this page content properly.</noscript>
            <div id="root"></div>
        </body>
        </html>
        """
        mock_fetch = FetchResponse(
            url="https://spa-app.com/view",
            status_code=200,
            content=html_doc.encode("utf-8"),
            text=html_doc,
            content_type="text/html",
            is_pdf=False,
            success=True,
        )

        with patch("app.scraping.scraper.web_scraper.fetch", new_callable=AsyncMock, return_value=mock_fetch):
            result = await content_extractor.extract_from_url("https://spa-app.com/view")
            assert result["is_js_required"] is True

    @pytest.mark.asyncio
    async def test_zero_crash_on_network_failure(self):
        # 403, 404, or 500 should never raise exceptions
        mock_fetch = FetchResponse(
            url="https://broken-site.com/error",
            status_code=500,
            content=b"",
            text="",
            content_type="text/html",
            is_pdf=False,
            success=False,
            error="HTTP 500 Server Error",
        )

        with patch("app.scraping.scraper.web_scraper.fetch", new_callable=AsyncMock, return_value=mock_fetch):
            result = await content_extractor.extract_from_url("https://broken-site.com/error")
            assert result["success"] is False
            assert result["status_code"] == 500
            assert result["text"] == ""
            assert "HTTP 500" in result["error"]
