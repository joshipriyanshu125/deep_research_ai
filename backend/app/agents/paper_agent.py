"""
Day 21 — Academic / Paper Research Agent

Full pipeline:
  Question
    ↓
  Academic Query (from question)
    ↓
  Multi-source Paper Search (arXiv, Semantic Scholar, Crossref, PubMed)
    ↓
  Paper Metadata (title, authors, DOI, year, venue, citation count)
    ↓
  Abstract extraction (always available)
    ↓
  PDF download (when open-access URL available)
    ↓
  Full-text extraction (page-by-page, section-aware)
    ↓
  Relevant Section Identification (Abstract, Results, Conclusion)
    ↓
  Evidence (with page + section provenance)

The agent enriches Source objects with:
  - paper metadata (authors, DOI, venue, citation_count, year)
  - full extracted text from PDF
  - per-page section evidence blocks
"""

import asyncio
from typing import List, Dict, Any, Optional
from app.search.academic_search import academic_search_engine
from app.scraping.pdf_extractor import advanced_pdf_extractor, pdf_downloader
from app.database.models.source import Source, SourceType
from app.utils.logger import logger
from app.utils.helpers import generate_uuid


# Sections with highest evidence density in academic papers
_HIGH_EVIDENCE_SECTIONS = {"Results", "Findings", "Discussion", "Conclusion", "Abstract"}
# Sections to skip (low information density for research purposes)
_LOW_VALUE_SECTIONS = {"References", "Bibliography", "Acknowledgments", "Appendix"}


class AcademicPaperAgent:
    """
    Day 21 — Autonomous Academic Paper Research Agent.
    Searches multiple academic databases, downloads open-access PDFs,
    extracts structured evidence with page/section provenance, and
    returns enriched Source objects ready for the evidence pipeline.
    """

    def __init__(
        self,
        download_pdfs: bool = True,
        max_pdf_size_mb: float = 15.0,
        pdf_timeout: float = 25.0,
    ):
        self.download_pdfs = download_pdfs
        self.max_pdf_size_mb = max_pdf_size_mb
        self.pdf_timeout = pdf_timeout

    # ------------------------------------------------------------------
    # Public API (used by ResearchAgent)
    # ------------------------------------------------------------------

    async def execute(
        self,
        query: str,
        research_id: str,
        max_results: int = 6,
        sources: Optional[List[str]] = None,
    ) -> List[Source]:
        """
        Main entry point. Run the full pipeline:
        query → search → enrich with PDF → return Source list.
        """
        logger.info(f"AcademicPaperAgent executing query: {query!r}")

        # 1. Search across multiple academic databases
        papers = await academic_search_engine.search(
            query=query,
            max_results=max_results,
            sources=sources,
        )
        if not papers:
            logger.warning(f"No academic results for '{query}'")
            return []

        # 2. Enrich papers with PDF content (parallel where possible)
        enrich_tasks = [
            self._enrich_paper(paper, research_id)
            for paper in papers
        ]
        enriched = await asyncio.gather(*enrich_tasks, return_exceptions=True)

        sources_out: List[Source] = []
        for result in enriched:
            if isinstance(result, Exception):
                logger.warning(f"Paper enrichment error: {result}")
                continue
            if result is not None:
                sources_out.append(result)

        logger.info(
            f"AcademicPaperAgent completed: {len(sources_out)} sources "
            f"from {len(papers)} papers for '{query}'"
        )
        return sources_out

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _enrich_paper(
        self,
        paper: Dict[str, Any],
        research_id: str,
    ) -> Optional[Source]:
        """
        Turn a raw academic search result into a full Source object.
        Tries to download the PDF for richer content; falls back to abstract.
        """
        url = paper.get("url", "")
        pdf_url = paper.get("pdf_url")
        title = paper.get("title", "Untitled Academic Paper")
        abstract = paper.get("abstract", "") or paper.get("snippet", "")
        authors = paper.get("authors", [])
        year = paper.get("year", "")
        doi = paper.get("doi", "")
        venue = paper.get("venue", "")
        citation_count = paper.get("citation_count", 0)
        source_db = paper.get("source", "academic")

        # Build base metadata
        metadata: Dict[str, Any] = {
            "authors": authors,
            "year": year,
            "doi": doi,
            "venue": venue,
            "citation_count": citation_count,
            "source_database": source_db,
            "pdf_url": pdf_url,
            "evidence_blocks": [],
        }

        # Content defaults to abstract
        content = abstract
        clean_text = abstract
        pdf_data: Optional[Dict[str, Any]] = None

        # Attempt PDF download and full-text extraction
        if self.download_pdfs and pdf_url:
            try:
                pdf_bytes = await pdf_downloader.download(
                    pdf_url,
                    timeout=self.pdf_timeout,
                    max_size_mb=self.max_pdf_size_mb,
                )
                if pdf_bytes:
                    pdf_data = advanced_pdf_extractor.extract(pdf_bytes)
                    if pdf_data.get("success") and pdf_data.get("text"):
                        # Use full extracted text
                        content = pdf_data["text"]
                        clean_text = pdf_data["text"]

                        # Override metadata from PDF if better
                        if pdf_data.get("title") and not title:
                            title = pdf_data["title"]
                        if pdf_data.get("author") and not authors:
                            authors = [pdf_data["author"]]
                            metadata["authors"] = authors
                        if pdf_data.get("year") and not year:
                            year = pdf_data["year"]
                            metadata["year"] = year
                        if pdf_data.get("doi") and not doi:
                            doi = pdf_data["doi"]
                            metadata["doi"] = doi

                        # Store structured evidence blocks (page + section provenance)
                        evidence_blocks = self._extract_evidence_blocks(pdf_data)
                        metadata["evidence_blocks"] = evidence_blocks
                        metadata["page_count"] = pdf_data.get("page_count", 0)
                        metadata["sections_found"] = list(
                            pdf_data.get("sections", {}).keys()
                        )
                        metadata["tables_count"] = len(pdf_data.get("tables", []))
            except Exception as pdf_err:
                logger.warning(
                    f"PDF processing failed for {pdf_url!r}: {pdf_err}, "
                    f"using abstract fallback"
                )

        # Ensure content is not empty
        if not content.strip():
            content = f"Academic paper: {title}. Authors: {', '.join(authors)}."
            if doi:
                content += f" DOI: {doi}."

        # Build author credit string
        author_str = None
        if authors:
            if len(authors) <= 3:
                author_str = ", ".join(authors)
            else:
                author_str = f"{authors[0]} et al."

        source = Source(
            source_id=generate_uuid(),
            research_id=research_id,
            url=url,
            title=title,
            source_type=SourceType.ACADEMIC,
            content=content,
            clean_text=clean_text,
            snippet=abstract[:500] if abstract else content[:500],
            author=author_str,
            published_at=year if year else None,
            relevance_score=0.95,
            credibility_score=self._compute_credibility(paper),
            metadata=metadata,
        )
        return source

    def _extract_evidence_blocks(self, pdf_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract high-value evidence blocks with page + section provenance.
        Returns:
            [{"page": 5, "section": "Results", "text": "...", "tables": [...]}, ...]
        """
        pages = pdf_data.get("pages", [])
        evidence_blocks = []

        for page in pages:
            section = page.get("section", "Body")
            if section in _LOW_VALUE_SECTIONS:
                continue

            text = page.get("text", "").strip()
            if not text or page.get("word_count", 0) < 40:
                continue

            block = {
                "page": page["page"],
                "section": section,
                "text": text[:2000],  # cap per-page text
                "tables": page.get("tables", []),
                "is_high_value": section in _HIGH_EVIDENCE_SECTIONS,
            }
            evidence_blocks.append(block)

        # Prioritize: high-value sections first
        evidence_blocks.sort(key=lambda b: (0 if b["is_high_value"] else 1, b["page"]))
        return evidence_blocks

    def _compute_credibility(self, paper: Dict[str, Any]) -> float:
        """
        Score academic source credibility based on:
        - citation count (highly cited → more credible)
        - has abstract (peer-reviewed quality signal)
        - has DOI (formally published)
        - source database (peer-reviewed venues score higher)
        """
        score = 0.90  # Academic baseline is high

        if paper.get("doi"):
            score = min(1.0, score + 0.03)

        citation_count = paper.get("citation_count", 0)
        if citation_count and citation_count > 0:
            score = min(1.0, score + min(0.05, citation_count / 2000))

        if paper.get("abstract") and len(paper["abstract"]) > 100:
            score = min(1.0, score + 0.01)

        db = paper.get("source", "")
        if db in ("semantic_scholar", "pubmed", "crossref"):
            score = min(1.0, score + 0.01)

        return round(score, 4)

    async def search_papers(
        self,
        query: str,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return raw paper metadata without building Source objects."""
        return await academic_search_engine.search(query, max_results=max_results)

    async def get_paper_abstract(self, pdf_url: str) -> Optional[str]:
        """Download a PDF and return only the abstract."""
        try:
            pdf_bytes = await pdf_downloader.download(pdf_url, timeout=25.0)
            if pdf_bytes:
                return advanced_pdf_extractor.extract_abstract(pdf_bytes)
        except Exception as e:
            logger.warning(f"Abstract extraction failed for {pdf_url}: {e}")
        return None

    async def get_paper_sections(self, pdf_url: str) -> Dict[str, str]:
        """Download a PDF and return all detected sections."""
        try:
            pdf_bytes = await pdf_downloader.download(pdf_url, timeout=25.0)
            if pdf_bytes:
                result = advanced_pdf_extractor.extract(pdf_bytes)
                return result.get("sections", {})
        except Exception as e:
            logger.warning(f"Section extraction failed for {pdf_url}: {e}")
        return {}


# Singleton — backward compatible
paper_agent = AcademicPaperAgent()
