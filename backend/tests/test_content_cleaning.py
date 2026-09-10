import pytest
from app.scraping.text_normalizer import TextNormalizer, text_normalizer
from app.scraping.cleaner import HTMLCleaner, html_cleaner
from app.scraping.extractor import ContentExtractor, content_extractor
from app.scraping.scraper import FetchResponse
from unittest.mock import patch, AsyncMock


class TestTextNormalizerEntities:
    def test_standard_html_entities(self):
        norm = TextNormalizer()
        raw = "Electric Vehicles &amp; Clean Energy &mdash; India&rsquo;s Plan"
        res = norm.decode_html_entities(raw)
        assert res == "Electric Vehicles & Clean Energy — India’s Plan"

    def test_numeric_and_quote_entities(self):
        norm = TextNormalizer()
        raw = "&quot;Green Hydrogen&#39;s Future&quot; &lt;2026&gt;"
        res = norm.decode_html_entities(raw)
        assert res == '"Green Hydrogen\'s Future" <2026>'

    def test_double_escaped_entities(self):
        norm = TextNormalizer()
        raw = "&amp;quot;Double Escaped Title&amp;quot; &amp;amp; More"
        res = norm.decode_html_entities(raw)
        assert res == '"Double Escaped Title" & More'


class TestTextNormalizerEncoding:
    def test_nfkc_unicode_normalization(self):
        norm = TextNormalizer()
        # Full-width characters
        raw = "Ｔｅｓｔ Ｕｎｉｃｏｄｅ"
        res = norm.normalize_encoding(raw)
        assert res == "Test Unicode"

    def test_zero_width_and_control_characters_removed(self):
        norm = TextNormalizer()
        raw = "Clean\u200BText\x00With\uFEFFInvisible\x08Chars"
        res = norm.normalize_encoding(raw)
        assert res == "CleanTextWithInvisibleChars"


class TestTextNormalizerWhitespace:
    def test_whitespace_and_tabs_collapsing(self):
        norm = TextNormalizer()
        raw = "Market   Size    \t   is    $50B    \n\n   Growth   rate   is   25%  "
        res = norm.normalize_whitespace(raw)
        assert res == "Market Size is $50B\n\nGrowth rate is 25%"

    def test_nbsp_replacement(self):
        norm = TextNormalizer()
        raw = "India\u00a0EV\u00a0Market"
        res = norm.normalize_whitespace(raw)
        assert res == "India EV Market"

    def test_excessive_newlines_collapsed_to_paragraphs(self):
        norm = TextNormalizer()
        raw = "Paragraph 1\n\n\n\n\n\nParagraph 2\n\n\nParagraph 3"
        res = norm.normalize_whitespace(raw)
        assert res == "Paragraph 1\n\nParagraph 2\n\nParagraph 3"


class TestTextNormalizerDeduplication:
    def test_duplicate_paragraphs_removed(self):
        norm = TextNormalizer()
        raw = (
            "India is rapidly adopting electric vehicles across both consumer and commercial transportation.\n\n"
            "The battery manufacturing ecosystem has received significant policy incentives under national schemes.\n\n"
            "India is rapidly adopting electric vehicles across both consumer and commercial transportation.\n\n"
            "India is rapidly adopting electric vehicles across both consumer and commercial transportation."
        )
        res = norm.deduplicate_content(raw)
        paragraphs = res.split("\n\n")
        assert len(paragraphs) == 2
        assert "battery manufacturing" in paragraphs[1]

    def test_headings_preserved_during_deduplication(self):
        norm = TextNormalizer()
        raw = (
            "# Section 1\n\n"
            "Detailed analysis paragraph on electric two-wheelers and government subsidies.\n\n"
            "## Section 2\n\n"
            "Detailed analysis paragraph on electric two-wheelers and government subsidies."
        )
        res = norm.deduplicate_content(raw)
        assert "# Section 1" in res
        assert "## Section 2" in res


class TestHTMLCleanerNoiseStripping:
    def test_strip_navigation_and_menus(self):
        cleaner = HTMLCleaner()
        html = """
        <html>
            <body>
                <nav class="navbar"><a href="/">Home</a><a href="/about">About Us</a></nav>
                <div class="nav-menu">Categories | Products | Pricing</div>
                <main>
                    <h1>Real Article Title</h1>
                    <p>This is the essential article body that contains high value research findings.</p>
                </main>
            </body>
        </html>
        """
        cleaned = cleaner.clean(html)
        assert "Home" not in cleaned
        assert "About Us" not in cleaned
        assert "Categories | Products" not in cleaned
        assert "Real Article Title" in cleaned
        assert "essential article body" in cleaned

    def test_strip_cookie_and_gdpr_notices(self):
        cleaner = HTMLCleaner()
        html = """
        <html>
            <body>
                <div class="cookie-banner">We use cookies to improve your browsing experience. Accept All.</div>
                <div id="gdpr-consent">GDPR Preferences & Privacy Policy</div>
                <article>
                    <h2>Renewable Energy Progress</h2>
                    <p>India added 15 GW of solar and wind capacity during the last fiscal year.</p>
                </article>
            </body>
        </html>
        """
        cleaned = cleaner.clean(html)
        assert "cookies to improve" not in cleaned
        assert "GDPR Preferences" not in cleaned
        assert "Renewable Energy Progress" in cleaned
        assert "15 GW of solar" in cleaned

    def test_strip_advertisements_and_sponsored_content(self):
        cleaner = HTMLCleaner()
        html = """
        <html>
            <body>
                <div class="advertisement">Buy cheap insurance now! Click here.</div>
                <ins class="adsbygoogle">Sponsored Ad Content</ins>
                <div class="sponsored-content">Promoted: Best Loans of 2026</div>
                <article>
                    <h1>Semiconductor Fabrication in India</h1>
                    <p>Three commercial fabs have commenced initial wafer testing.</p>
                </article>
            </body>
        </html>
        """
        cleaned = cleaner.clean(html)
        assert "cheap insurance" not in cleaned
        assert "Sponsored Ad Content" not in cleaned
        assert "Best Loans of 2026" not in cleaned
        assert "Semiconductor Fabrication" in cleaned

    def test_strip_comments_and_footers(self):
        cleaner = HTMLCleaner()
        html = """
        <html>
            <body>
                <article>
                    <h1>Quantum Computing Benchmarks</h1>
                    <p>Logical qubits achieved lower error rates in new quantum processors.</p>
                </article>
                <section id="comments">
                    <h3>Comments</h3>
                    <div class="comment">RandomUser99: First comment! Great article.</div>
                    <div class="disqus">Disqus thread comments here.</div>
                </section>
                <footer>
                    <p>© 2026 Tech Journal. All rights reserved. Terms of Service | Privacy</p>
                </footer>
            </body>
        </html>
        """
        cleaned = cleaner.clean(html)
        assert "RandomUser99" not in cleaned
        assert "Disqus thread" not in cleaned
        assert "Terms of Service" not in cleaned
        assert "Quantum Computing Benchmarks" in cleaned


class TestEndToEndContentCleaning:
    @pytest.mark.asyncio
    async def test_extractor_cleans_and_normalizes_html(self):
        messy_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>EV Industry &amp; Market Dynamics</title>
            <meta name="author" content="Dr. R. &amp; S. Sharma">
        </head>
        <body>
            <div class="cookie-notice">Accept all cookies to continue.</div>
            <nav>Menu 1 | Menu 2</nav>
            <div class="ad-banner">Advertisement: 50% Off Sales</div>
            <article>
                <h1>Indian EV Industry &amp; Market Growth</h1>
                <p>The Indian EV market&rsquo;s valuation reached &dollar;10B in 2026.&nbsp;&nbsp;&nbsp;Growth is accelerating.</p>
                <p>The Indian EV market&rsquo;s valuation reached &dollar;10B in 2026.&nbsp;&nbsp;&nbsp;Growth is accelerating.</p>
            </article>
            <div id="comments">User comments section</div>
            <footer>Footer navigation links</footer>
        </body>
        </html>
        """

        mock_fetch = FetchResponse(
            url="https://insights.com/ev-growth",
            status_code=200,
            content=messy_html.encode("utf-8"),
            text=messy_html,
            content_type="text/html",
            is_pdf=False,
            success=True,
        )

        with patch("app.scraping.scraper.web_scraper.fetch", new_callable=AsyncMock, return_value=mock_fetch):
            res = await content_extractor.extract_from_url("https://insights.com/ev-growth")
            assert res["success"] is True
            assert "Accept all cookies" not in res["text"]
            assert "Advertisement: 50% Off" not in res["text"]
            assert "User comments" not in res["text"]
            assert "Footer navigation" not in res["text"]
            # Entities decoded
            assert "market's valuation reached $10B in 2026. Growth is accelerating." in res["text"]
            # Duplicate paragraph deduplicated
            paragraphs = [p for p in res["text"].split("\n\n") if "market's valuation" in p]
            assert len(paragraphs) == 1
