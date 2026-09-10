"""
Scraping package providing web scraper, HTML cleaner, PDF extractor,
content extractor, and text normalizer.
"""
from app.scraping.scraper import WebScraper, web_scraper, FetchResponse
from app.scraping.cleaner import HTMLCleaner, html_cleaner
from app.scraping.pdf_extractor import PDFExtractor, pdf_extractor
from app.scraping.extractor import ContentExtractor, content_extractor
from app.scraping.text_normalizer import TextNormalizer, text_normalizer

__all__ = [
    "WebScraper",
    "web_scraper",
    "FetchResponse",
    "HTMLCleaner",
    "html_cleaner",
    "PDFExtractor",
    "pdf_extractor",
    "ContentExtractor",
    "content_extractor",
    "TextNormalizer",
    "text_normalizer",
]
