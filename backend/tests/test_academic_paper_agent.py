"""
Day 21 & 22 — Academic Paper Agent & PDF Processor Test Suite

Tests:
  - Multi-source academic search (arXiv, Semantic Scholar, Crossref, PubMed)
  - Paper metadata extraction
  - PDF download and text extraction
  - Per-page extraction with section detection
  - Table heuristic extraction
  - Evidence blocks with page + section provenance
  - AcademicPaperAgent full pipeline
  - Backward compatibility with existing pdf_extractor interface
"""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from app.search.academic_search import (
    ArXivSearchEngine,
    SemanticScholarSearchEngine,
    CrossrefSearchEngine,
    PubMedSearchEngine,
    AcademicSearchEngine,
    academic_search_engine,
)
from app.scraping.pdf_extractor import (
    AdvancedPDFExtractor,
    PDFExtractor,
    PDFDownloader,
    advanced_pdf_extractor,
    pdf_downloader,
    pdf_extractor,
    _detect_section,
    _extract_tables_from_page_text,
    _table_lines_to_markdown,
)
from app.agents.paper_agent import AcademicPaperAgent, paper_agent
from app.database.models.source import Source, SourceType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_pdf_bytes() -> bytes:
    """Create a minimal valid PDF in-memory using pypdf."""
    try:
        import pypdf
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)

        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception:
        # Fallback: return PDF magic bytes + minimal structure (will fail extract gracefully)
        return b"%PDF-1.4\n%%EOF"


def _make_test_paper(
    source: str = "arxiv",
    has_pdf: bool = True,
    has_abstract: bool = True,
) -> Dict[str, Any]:
    return {
        "title": "Deep Learning for EV Battery State Estimation",
        "url": "https://arxiv.org/abs/2501.12345",
        "pdf_url": "https://arxiv.org/pdf/2501.12345.pdf" if has_pdf else None,
        "abstract": "We propose a deep learning framework for real-time EV battery SOC estimation achieving 98% accuracy." if has_abstract else "",
        "snippet": "Deep learning for EV battery state estimation.",
        "authors": ["Alice Johnson", "Bob Smith"],
        "year": "2024",
        "doi": "10.1234/evbattery.2024",
        "venue": "Nature Energy",
        "citation_count": 150,
        "source": source,
        "source_type": "academic",
    }


# ---------------------------------------------------------------------------
# 1. Section Detection
# ---------------------------------------------------------------------------

class TestSectionDetection:
    def test_detect_abstract(self):
        text = "Abstract\nThis paper presents a novel..."
        assert _detect_section(text) == "Abstract"

    def test_detect_results(self):
        text = "3. Results\nOur experiments show..."
        assert _detect_section(text) == "Results"

    def test_detect_conclusion(self):
        text = "Conclusions\nIn this work we demonstrated..."
        assert _detect_section(text) == "Conclusion"

    def test_detect_methods(self):
        text = "2. Methods\nWe used a transformer architecture..."
        assert _detect_section(text) == "Methods"

    def test_detect_introduction(self):
        text = "1. Introduction\nRecent advances in..."
        assert _detect_section(text) == "Introduction"

    def test_detect_body_for_unknown(self):
        text = "This is some random paragraph text without a section header."
        assert _detect_section(text) == "Body"

    def test_detect_case_insensitive(self):
        text = "RESULTS AND DISCUSSION"
        assert _detect_section(text) in ("Results", "Discussion", "Body")


# ---------------------------------------------------------------------------
# 2. Table Extraction
# ---------------------------------------------------------------------------

class TestTableExtraction:
    def test_extract_simple_table(self):
        text = (
            "Year    Sales    Growth\n"
            "2022    5000     10%\n"
            "2023    7500     50%\n"
            "2024    10000    33%\n"
            "This is a paragraph after the table."
        )
        tables = _extract_tables_from_page_text(text)
        assert len(tables) >= 1
        assert "Year" in tables[0]
        assert "Sales" in tables[0]

    def test_table_to_markdown_format(self):
        rows = [
            ["Model", "Accuracy", "F1"],
            ["BERT", "0.92", "0.91"],
            ["GPT-4", "0.96", "0.95"],
        ]
        md = _table_lines_to_markdown(rows)
        assert "| Model |" in md
        assert "| --- |" in md
        assert "BERT" in md
        assert "GPT-4" in md

    def test_empty_rows_returns_empty(self):
        assert _table_lines_to_markdown([]) == ""

    def test_single_row_no_data_returns_empty(self):
        rows = [["Header1", "Header2"]]
        # Single row → no data rows → should return empty
        result = _table_lines_to_markdown(rows)
        assert result == ""

    def test_no_table_in_paragraph(self):
        text = "This is a normal paragraph without any tabular data in it at all."
        tables = _extract_tables_from_page_text(text)
        assert tables == []


# ---------------------------------------------------------------------------
# 3. AdvancedPDFExtractor
# ---------------------------------------------------------------------------

class TestAdvancedPDFExtractor:
    def test_empty_bytes_returns_error_result(self):
        extractor = AdvancedPDFExtractor()
        result = extractor.extract(b"")
        assert result["success"] is False
        assert result["is_pdf"] is True
        assert result["error"] is not None
        assert result["page_count"] == 0
        assert result["pages"] == []
        assert result["sections"] == {}

    def test_invalid_bytes_does_not_raise(self):
        extractor = AdvancedPDFExtractor()
        result = extractor.extract(b"not a pdf at all!")
        assert isinstance(result, dict)
        assert result["is_pdf"] is True

    def test_valid_pdf_extracts_structure(self):
        pdf_bytes = _make_minimal_pdf_bytes()
        extractor = AdvancedPDFExtractor()
        result = extractor.extract(pdf_bytes)
        # Minimal blank PDF may have no text but should not crash
        assert "pages" in result
        assert "sections" in result
        assert "tables" in result
        assert "page_count" in result
        assert isinstance(result["pages"], list)

    def test_get_evidence_blocks_returns_list(self):
        pdf_bytes = _make_minimal_pdf_bytes()
        extractor = AdvancedPDFExtractor()
        blocks = extractor.get_evidence_blocks(pdf_bytes)
        assert isinstance(blocks, list)
        # Empty PDF → no blocks, but no exception
        for b in blocks:
            assert "page" in b
            assert "section" in b
            assert "text" in b

    def test_extract_abstract_returns_none_on_blank(self):
        pdf_bytes = _make_minimal_pdf_bytes()
        extractor = AdvancedPDFExtractor()
        abstract = extractor.extract_abstract(pdf_bytes)
        # Blank PDF has no Abstract section
        assert abstract is None or isinstance(abstract, str)

    def test_empty_result_structure(self):
        extractor = AdvancedPDFExtractor()
        result = extractor._empty_result("Test error")
        assert result["success"] is False
        assert result["error"] == "Test error"
        assert result["pages"] == []
        assert result["sections"] == {}
        assert result["tables"] == []
        assert result["text"] == ""

    def test_extract_section_on_empty_pdf(self):
        pdf_bytes = _make_minimal_pdf_bytes()
        extractor = AdvancedPDFExtractor()
        result = extractor.extract_section(pdf_bytes, "Results")
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# 4. Backward Compatibility — pdf_extractor (Day 14 interface)
# ---------------------------------------------------------------------------

class TestBackwardCompatPDFExtractor:
    def test_extract_returns_required_keys(self):
        result = pdf_extractor.extract(b"")
        for key in ("text", "title", "author", "date", "page_count", "success", "is_pdf", "error"):
            assert key in result, f"Missing key: {key}"

    def test_extract_blank_pdf(self):
        pdf_bytes = _make_minimal_pdf_bytes()
        result = pdf_extractor.extract(pdf_bytes)
        assert isinstance(result["text"], str)
        assert isinstance(result["page_count"], int)
        assert result["is_pdf"] is True

    def test_extract_bad_bytes_no_crash(self):
        result = pdf_extractor.extract(b"\x00\xff\xde\xad")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# 5. PDFDownloader
# ---------------------------------------------------------------------------

class TestPDFDownloader:
    @pytest.mark.asyncio
    async def test_download_returns_none_for_empty_url(self):
        downloader = PDFDownloader()
        result = await downloader.download("")
        assert result is None

    @pytest.mark.asyncio
    async def test_download_returns_bytes_on_success(self):
        downloader = PDFDownloader()
        fake_pdf = b"%PDF-1.4 fake pdf content"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "application/pdf"}
            mock_resp.content = fake_pdf

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await downloader.download("https://arxiv.org/pdf/2501.001.pdf")
            assert result == fake_pdf

    @pytest.mark.asyncio
    async def test_download_returns_none_on_404(self):
        downloader = PDFDownloader()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_resp.headers = {"content-type": "text/html"}

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await downloader.download("https://example.com/paper.pdf")
            assert result is None

    @pytest.mark.asyncio
    async def test_download_returns_none_on_html_content_type(self):
        downloader = PDFDownloader()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
            mock_resp.content = b"<html>Not a PDF</html>"

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await downloader.download("https://example.com/paper.pdf")
            assert result is None


# ---------------------------------------------------------------------------
# 6. ArXiv Search Engine
# ---------------------------------------------------------------------------

class TestArXivSearchEngine:
    @pytest.mark.asyncio
    async def test_returns_list_on_success(self):
        engine = ArXivSearchEngine()
        fake_xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2501.00001v1</id>
    <title>EV Battery State Estimation with Deep Learning</title>
    <summary>This paper proposes a deep learning approach for battery SOC estimation.</summary>
    <published>2024-01-15T00:00:00Z</published>
    <author><name>Alice Johnson</name></author>
    <link type="application/pdf" href="https://arxiv.org/pdf/2501.00001.pdf"/>
  </entry>
</feed>"""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = fake_xml

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await engine.search("EV battery deep learning")
            assert len(results) == 1
            assert results[0]["title"] == "EV Battery State Estimation with Deep Learning"
            assert results[0]["source"] == "arxiv"
            assert results[0]["source_type"] == "academic"
            assert results[0]["year"] == "2024"
            assert "Alice Johnson" in results[0]["authors"]
            assert results[0]["pdf_url"] is not None

    @pytest.mark.asyncio
    async def test_returns_empty_on_network_failure(self):
        engine = ArXivSearchEngine()
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await engine.search("quantum computing")
            assert results == []


# ---------------------------------------------------------------------------
# 7. Semantic Scholar Search Engine
# ---------------------------------------------------------------------------

class TestSemanticScholarSearchEngine:
    @pytest.mark.asyncio
    async def test_parses_paper_fields(self):
        engine = SemanticScholarSearchEngine()
        fake_response = {
            "data": [
                {
                    "paperId": "abc123",
                    "title": "Solid-State Battery Technology Review",
                    "abstract": "We review recent advances in solid-state batteries.",
                    "authors": [{"name": "John Doe"}, {"name": "Jane Smith"}],
                    "year": 2024,
                    "externalIds": {"DOI": "10.5678/ssb.2024"},
                    "openAccessPdf": {"url": "https://example.com/ssb.pdf"},
                    "venue": "Nature Materials",
                    "citationCount": 250,
                }
            ]
        }
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json = MagicMock(return_value=fake_response)

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await engine.search("solid-state battery")
            assert len(results) == 1
            r = results[0]
            assert r["title"] == "Solid-State Battery Technology Review"
            assert r["doi"] == "10.5678/ssb.2024"
            assert r["pdf_url"] == "https://example.com/ssb.pdf"
            assert r["citation_count"] == 250
            assert r["source"] == "semantic_scholar"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        engine = SemanticScholarSearchEngine()
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("API timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            results = await engine.search("CRISPR gene editing")
            assert results == []


# ---------------------------------------------------------------------------
# 8. Unified AcademicSearchEngine
# ---------------------------------------------------------------------------

class TestUnifiedAcademicSearchEngine:
    @pytest.mark.asyncio
    async def test_parallel_search_deduplication(self):
        """Unified engine should deduplicate results from multiple sources."""
        engine = AcademicSearchEngine()

        # Both arXiv and Semantic Scholar return the same title
        shared_paper = _make_test_paper(source="arxiv")
        shared_paper_ss = _make_test_paper(source="semantic_scholar")

        unique_paper = {
            **_make_test_paper(source="crossref"),
            "title": "Unique Crossref Paper on Battery Thermal Management",
            "doi": "10.9999/unique",
        }

        with patch.object(engine.arxiv, "search", AsyncMock(return_value=[shared_paper])):
            with patch.object(engine.semantic_scholar, "search", AsyncMock(return_value=[shared_paper_ss])):
                with patch.object(engine.crossref, "search", AsyncMock(return_value=[unique_paper])):
                    with patch.object(engine.pubmed, "search", AsyncMock(return_value=[])):
                        results = await engine.search("EV battery", max_results=5)
                        # Duplicate title should appear only once
                        titles = [r["title"] for r in results]
                        assert titles.count(shared_paper["title"]) == 1

    @pytest.mark.asyncio
    async def test_search_returns_ranked_results(self):
        """Results with abstracts and PDFs rank higher."""
        engine = AcademicSearchEngine()

        # Give all papers unique titles and unique DOIs to avoid deduplication removing them
        paper_with_pdf = {
            **_make_test_paper(has_pdf=True, has_abstract=True),
            "title": "Alpha Paper With PDF And Abstract",
            "doi": "10.1111/alpha",
        }
        paper_no_pdf = {
            **_make_test_paper(has_pdf=False, has_abstract=True),
            "title": "Beta Paper Without PDF Has Abstract",
            "doi": "10.2222/beta",
        }
        paper_no_abstract = {
            **_make_test_paper(has_pdf=False, has_abstract=False),
            "title": "Gamma Paper Without PDF Or Abstract",
            "doi": "10.3333/gamma",
        }

        with patch.object(engine.arxiv, "search", AsyncMock(return_value=[paper_no_abstract])):
            with patch.object(engine.semantic_scholar, "search", AsyncMock(return_value=[paper_no_pdf])):
                with patch.object(engine.crossref, "search", AsyncMock(return_value=[paper_with_pdf])):
                    with patch.object(engine.pubmed, "search", AsyncMock(return_value=[])):
                        results = await engine.search("EV battery", max_results=10)
                        assert len(results) == 3
                        # Paper with PDF and abstract should rank first
                        assert results[0]["title"] == paper_with_pdf["title"]

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_empty(self):
        engine = AcademicSearchEngine()
        with patch.object(engine.arxiv, "search", AsyncMock(return_value=[])):
            with patch.object(engine.semantic_scholar, "search", AsyncMock(return_value=[])):
                with patch.object(engine.crossref, "search", AsyncMock(return_value=[])):
                    with patch.object(engine.pubmed, "search", AsyncMock(return_value=[])):
                        results = await engine.search("obscure topic xyz")
                        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_pdf_urls_only(self):
        engine = AcademicSearchEngine()
        no_pdf = {**_make_test_paper(), "pdf_url": None, "title": "No PDF Paper"}
        has_pdf = _make_test_paper(has_pdf=True)

        with patch.object(engine, "search", AsyncMock(return_value=[no_pdf, has_pdf])):
            results = await engine.search_with_pdf_urls("battery", max_results=5)
            for r in results:
                assert r.get("pdf_url") is not None


# ---------------------------------------------------------------------------
# 9. AcademicPaperAgent Full Pipeline
# ---------------------------------------------------------------------------

class TestAcademicPaperAgent:
    @pytest.mark.asyncio
    async def test_execute_returns_sources(self):
        agent = AcademicPaperAgent(download_pdfs=False)
        papers = [_make_test_paper()]

        with patch.object(academic_search_engine, "search", AsyncMock(return_value=papers)):
            sources = await agent.execute("EV battery deep learning", research_id="res-001")

        assert len(sources) == 1
        src = sources[0]
        assert isinstance(src, Source)
        assert src.source_type == SourceType.ACADEMIC
        assert src.title == papers[0]["title"]
        assert src.credibility_score >= 0.90
        assert src.relevance_score == 0.95

    @pytest.mark.asyncio
    async def test_execute_with_pdf_download(self):
        agent = AcademicPaperAgent(download_pdfs=True)
        paper = _make_test_paper(has_pdf=True)

        fake_pdf_result = {
            "text": "Abstract\nWe propose a novel deep learning framework.\n\nResults\nAccuracy: 98%.",
            "title": "DL EV Battery Paper",
            "author": "Alice Johnson",
            "year": "2024",
            "doi": "10.1234/ev.2024",
            "page_count": 10,
            "success": True,
            "pages": [
                {"page": 1, "section": "Abstract", "text": "We propose a novel approach.", "word_count": 100, "has_table": False, "tables": []},
                {"page": 5, "section": "Results", "text": "Accuracy: 98% on benchmark dataset.", "word_count": 200, "has_table": False, "tables": []},
            ],
            "sections": {
                "Abstract": "We propose a novel approach.",
                "Results": "Accuracy: 98% on benchmark dataset.",
            },
            "tables": [],
        }

        with patch.object(academic_search_engine, "search", AsyncMock(return_value=[paper])):
            with patch.object(pdf_downloader, "download", AsyncMock(return_value=b"%PDF-fake")):
                with patch.object(advanced_pdf_extractor, "extract", return_value=fake_pdf_result):
                    sources = await agent.execute("EV battery", research_id="res-pdf-001")

        assert len(sources) == 1
        src = sources[0]
        assert "Results" in src.content or "Abstract" in src.content
        assert src.metadata.get("page_count") == 10
        assert len(src.metadata.get("evidence_blocks", [])) >= 1

    @pytest.mark.asyncio
    async def test_execute_pdf_failure_falls_back_to_abstract(self):
        agent = AcademicPaperAgent(download_pdfs=True)
        paper = _make_test_paper(has_pdf=True)

        with patch.object(academic_search_engine, "search", AsyncMock(return_value=[paper])):
            with patch.object(pdf_downloader, "download", AsyncMock(return_value=None)):
                sources = await agent.execute("EV battery", research_id="res-fallback")

        assert len(sources) == 1
        # Should fall back to abstract
        assert paper["abstract"] in sources[0].content or sources[0].snippet

    @pytest.mark.asyncio
    async def test_execute_no_results_returns_empty(self):
        agent = AcademicPaperAgent(download_pdfs=False)
        with patch.object(academic_search_engine, "search", AsyncMock(return_value=[])):
            sources = await agent.execute("nonexistent query xyz", research_id="res-empty")
        assert sources == []

    @pytest.mark.asyncio
    async def test_credibility_score_higher_for_cited_papers(self):
        agent = AcademicPaperAgent(download_pdfs=False)

        low_cited = {**_make_test_paper(), "citation_count": 0, "doi": None}
        high_cited = {**_make_test_paper(), "citation_count": 5000, "doi": "10.1234/high"}

        score_low = agent._compute_credibility(low_cited)
        score_high = agent._compute_credibility(high_cited)

        assert score_high > score_low

    @pytest.mark.asyncio
    async def test_evidence_blocks_high_value_sections_prioritized(self):
        agent = AcademicPaperAgent()
        pdf_data = {
            "success": True,
            "pages": [
                {"page": 1, "section": "Introduction", "text": "Intro text here.", "word_count": 80, "has_table": False, "tables": []},
                {"page": 3, "section": "Results", "text": "EV sales grew by 45% YoY in 2024.", "word_count": 120, "has_table": False, "tables": []},
                {"page": 6, "section": "References", "text": "[1] Smith et al., 2023.", "word_count": 50, "has_table": False, "tables": []},
                {"page": 5, "section": "Conclusion", "text": "We conclude that deep learning enables accurate battery estimation.", "word_count": 100, "has_table": False, "tables": []},
            ],
        }
        blocks = agent._extract_evidence_blocks(pdf_data)
        # References section should be excluded
        sections = [b["section"] for b in blocks]
        assert "References" not in sections
        # High-value sections should appear first
        assert blocks[0]["is_high_value"] is True

    @pytest.mark.asyncio
    async def test_search_papers_returns_raw_metadata(self):
        agent = AcademicPaperAgent()
        papers = [_make_test_paper()]
        with patch.object(academic_search_engine, "search", AsyncMock(return_value=papers)):
            results = await agent.search_papers("EV battery")
        assert len(results) == 1
        assert results[0]["title"] == papers[0]["title"]

    @pytest.mark.asyncio
    async def test_get_paper_abstract_from_pdf(self):
        agent = AcademicPaperAgent()
        with patch.object(pdf_downloader, "download", AsyncMock(return_value=b"%PDF-fake")):
            with patch.object(advanced_pdf_extractor, "extract_abstract", return_value="We propose a novel method."):
                abstract = await agent.get_paper_abstract("https://arxiv.org/pdf/2501.001.pdf")
        assert abstract == "We propose a novel method."

    @pytest.mark.asyncio
    async def test_get_paper_sections_returns_dict(self):
        agent = AcademicPaperAgent()
        fake_result = {
            "success": True,
            "sections": {"Abstract": "Abstract text", "Results": "Results text"},
        }
        with patch.object(pdf_downloader, "download", AsyncMock(return_value=b"%PDF-fake")):
            with patch.object(advanced_pdf_extractor, "extract", return_value=fake_result):
                sections = await agent.get_paper_sections("https://arxiv.org/pdf/2501.001.pdf")
        assert "Abstract" in sections
        assert "Results" in sections


# ---------------------------------------------------------------------------
# 10. Paper Agent Backward Compatibility
# ---------------------------------------------------------------------------

class TestPaperAgentBackwardCompatibility:
    """Ensure existing ResearchAgent / ParallelExecutor still works with paper_agent."""

    @pytest.mark.asyncio
    async def test_paper_agent_singleton_execute(self):
        papers = [_make_test_paper()]
        with patch.object(academic_search_engine, "search", AsyncMock(return_value=papers)):
            sources = await paper_agent.execute("battery research", research_id="res-compat")
        assert isinstance(sources, list)
        if sources:
            assert isinstance(sources[0], Source)
            assert sources[0].source_type == SourceType.ACADEMIC
