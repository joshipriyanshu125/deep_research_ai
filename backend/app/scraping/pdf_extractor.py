"""
Day 22 — Advanced PDF Processor

Full pipeline:
  PDF URL / bytes
    ↓
  PDF Download (with redirect, user-agent, timeout handling)
    ↓
  Page-by-page text extraction
    ↓
  Section detection (Abstract, Introduction, Methods, Results, Conclusion)
    ↓
  Table extraction (markdown format)
    ↓
  Metadata (title, authors, year, DOI, page count)
    ↓
  Structured evidence with page + section provenance:
      {
        "page": 12,
        "section": "Results",
        "text": "..."
      }

This makes citations much stronger — every evidence item knows exactly
which page and section it came from.
"""

import io
import re
import asyncio
import httpx
from typing import Dict, Any, List, Optional, Tuple
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Section Detection Patterns
# ---------------------------------------------------------------------------

_SECTION_HEADERS = re.compile(
    r"^(?:(?:\d+[\.\s]+)?)"
    r"(abstract|introduction|background|related\s+work|literature\s+review|"
    r"methodology|methods?|approach|experimental\s+setup|experiments?|"
    r"results?|findings?|discussion|analysis|evaluation|"
    r"conclusion(?:s)?|future\s+work|references?|bibliography|"
    r"acknowledgments?|appendix|supplementary)"
    r"[\s\n:]*$",
    re.IGNORECASE | re.MULTILINE,
)

_INLINE_SECTION = re.compile(
    r"^(?:\d+\.?\s+)?(abstract|introduction|background|methodology|methods?|"
    r"results?|discussion|conclusion(?:s)?|references?)\s*[:.]?\s*$",
    re.IGNORECASE,
)


def _detect_section(text: str) -> str:
    """Detect the section name from a block of text (first 5 lines)."""
    first_lines = text.strip().split("\n")[:5]
    for line in first_lines:
        stripped = line.strip()
        if _SECTION_HEADERS.match(stripped) or _INLINE_SECTION.match(stripped):
            # Normalize section name
            match = re.match(
                r"(?:\d+[\.\s]+)?([\w\s]+)",
                stripped,
                re.IGNORECASE,
            )
            if match:
                raw = match.group(1).strip().lower()
                if "abstract" in raw:
                    return "Abstract"
                if "intro" in raw:
                    return "Introduction"
                if "method" in raw or "methodology" in raw:
                    return "Methods"
                if "result" in raw or "finding" in raw:
                    return "Results"
                if "discussion" in raw:
                    return "Discussion"
                if "conclusion" in raw:
                    return "Conclusion"
                if "reference" in raw or "bibliog" in raw:
                    return "References"
                if "background" in raw or "related" in raw:
                    return "Background"
                return raw.title()
    return "Body"


# ---------------------------------------------------------------------------
# Page-Level Extraction Result
# ---------------------------------------------------------------------------

class PageExtract:
    """Result of extracting a single PDF page."""

    def __init__(
        self,
        page_num: int,
        text: str,
        section: str = "Body",
        word_count: int = 0,
        has_table: bool = False,
        tables: Optional[List[str]] = None,
    ):
        self.page_num = page_num
        self.text = text
        self.section = section
        self.word_count = word_count
        self.has_table = has_table
        self.tables = tables or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page": self.page_num,
            "section": self.section,
            "text": self.text,
            "word_count": self.word_count,
            "has_table": self.has_table,
            "tables": self.tables,
        }


# ---------------------------------------------------------------------------
# Table Extraction (heuristic, no ML required)
# ---------------------------------------------------------------------------

def _extract_tables_from_page_text(text: str) -> List[str]:
    """
    Heuristic table extractor from raw PDF page text.
    Looks for lines that have consistent tab/space-aligned columns
    and converts them into markdown table format.
    """
    lines = text.split("\n")
    tables = []
    in_table = False
    table_lines: List[str] = []

    for line in lines:
        # A table-like line has ≥ 2 segments separated by 2+ spaces or tabs
        segments = re.split(r"\s{2,}|\t", line.strip())
        is_table_line = len(segments) >= 2 and all(len(s) > 0 for s in segments)

        if is_table_line:
            table_lines.append(segments)
            in_table = True
        else:
            if in_table and len(table_lines) >= 2:
                # Convert to markdown
                md_table = _table_lines_to_markdown(table_lines)
                if md_table:
                    tables.append(md_table)
            table_lines = []
            in_table = False

    if in_table and len(table_lines) >= 2:
        md_table = _table_lines_to_markdown(table_lines)
        if md_table:
            tables.append(md_table)

    return tables


def _table_lines_to_markdown(rows: List[List[str]]) -> str:
    """Convert list of row segments into markdown table."""
    if not rows:
        return ""

    col_count = max(len(r) for r in rows)
    # Normalize row lengths
    normalized = [r + [""] * (col_count - len(r)) for r in rows]

    header = "| " + " | ".join(normalized[0]) + " |"
    separator = "| " + " | ".join(["---"] * col_count) + " |"
    data_rows = [
        "| " + " | ".join(row) + " |"
        for row in normalized[1:]
        if any(cell.strip() for cell in row)
    ]

    if not data_rows:
        return ""

    return "\n".join([header, separator] + data_rows)


# ---------------------------------------------------------------------------
# Enhanced PDF Extractor (Day 22)
# ---------------------------------------------------------------------------

class AdvancedPDFExtractor:
    """
    Day 22 — Advanced PDF Processor.
    Extracts per-page text, detects sections, extracts tables,
    and produces structured evidence with page + section provenance.
    """

    def extract(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Full synchronous extraction from PDF bytes.

        Returns:
            {
              "text": full_text,
              "title": "",
              "author": "",
              "year": "",
              "doi": "",
              "page_count": N,
              "pages": [{"page": 1, "section": "Abstract", "text": "...", "tables": []}, ...],
              "sections": {"Abstract": "text", "Results": "text", ...},
              "tables": [...all tables across all pages...],
              "success": True,
              "is_pdf": True,
              "error": None
            }
        """
        if not pdf_bytes or not isinstance(pdf_bytes, (bytes, bytearray)):
            return self._empty_result("Empty or invalid PDF byte stream")

        try:
            import pypdf
        except ImportError:
            logger.error("pypdf is not installed. Run: pip install pypdf")
            return self._empty_result("pypdf not installed")

        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

            # Decrypt if needed
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    return self._empty_result("Encrypted PDF — cannot decrypt")

            total_pages = len(reader.pages)

            # --- Metadata ---
            title = ""
            author = None
            date_str = None
            doi = None
            if reader.metadata:
                title = (reader.metadata.title or "").strip()
                author = reader.metadata.author
                raw_date = reader.metadata.creation_date
                if raw_date:
                    if hasattr(raw_date, "strftime"):
                        date_str = raw_date.strftime("%Y-%m-%d")
                    else:
                        m = re.search(r"D:(\d{4})(\d{2})(\d{2})", str(raw_date))
                        if m:
                            date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

            # --- Per-Page Extraction ---
            pages: List[PageExtract] = []
            current_section = "Body"
            full_text_parts: List[str] = []
            all_tables: List[Dict[str, Any]] = []
            section_texts: Dict[str, List[str]] = {}

            for page_idx, page in enumerate(reader.pages):
                page_num = page_idx + 1
                try:
                    raw_text = page.extract_text() or ""
                except Exception as pe:
                    logger.warning(f"Page {page_num} extraction error: {pe}")
                    raw_text = ""

                if not raw_text.strip():
                    continue

                # Detect section from page content
                detected_section = _detect_section(raw_text)
                if detected_section != "Body":
                    current_section = detected_section

                # Table extraction
                tables = _extract_tables_from_page_text(raw_text)
                for tbl in tables:
                    all_tables.append({
                        "page": page_num,
                        "section": current_section,
                        "markdown": tbl,
                    })

                # DOI extraction (look in first 2 pages)
                if doi is None and page_num <= 2:
                    doi_match = re.search(
                        r"(?:doi|DOI)[:\s]*?(10\.\d{4,}/\S+)", raw_text
                    )
                    if doi_match:
                        doi = doi_match.group(1).rstrip(".")

                # Year extraction (if not from metadata)
                if not date_str and page_num <= 2:
                    year_match = re.search(r"\b(20[0-2]\d|19[89]\d)\b", raw_text)
                    if year_match:
                        date_str = year_match.group(1)

                word_count = len(raw_text.split())
                page_extract = PageExtract(
                    page_num=page_num,
                    text=raw_text.strip(),
                    section=current_section,
                    word_count=word_count,
                    has_table=bool(tables),
                    tables=tables,
                )
                pages.append(page_extract)
                full_text_parts.append(raw_text.strip())

                # Accumulate section texts
                if current_section not in section_texts:
                    section_texts[current_section] = []
                section_texts[current_section].append(raw_text.strip())

            full_text = "\n\n".join(full_text_parts)
            sections = {
                sec: "\n\n".join(texts)
                for sec, texts in section_texts.items()
            }

            return {
                "text": full_text,
                "title": title,
                "author": author,
                "date": date_str,
                "year": date_str[:4] if date_str and len(date_str) >= 4 else None,
                "doi": doi,
                "page_count": total_pages,
                "pages": [p.to_dict() for p in pages],
                "sections": sections,
                "tables": all_tables,
                "success": bool(full_text),
                "is_pdf": True,
                "error": None if full_text else "No text found in PDF",
            }

        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
            return self._empty_result(f"PDF parsing error: {e}")

    def extract_section(self, pdf_bytes: bytes, section_name: str) -> Optional[str]:
        """Extract a specific section from a PDF (e.g., 'Abstract', 'Results')."""
        result = self.extract(pdf_bytes)
        if not result["success"]:
            return None
        sections = result.get("sections", {})
        # Case-insensitive section lookup
        for key, text in sections.items():
            if key.lower() == section_name.lower():
                return text
        return None

    def extract_abstract(self, pdf_bytes: bytes) -> Optional[str]:
        """Extract only the abstract section from a PDF."""
        return self.extract_section(pdf_bytes, "Abstract")

    def get_evidence_blocks(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Returns structured evidence blocks with page + section provenance.
        Each block:
            {
              "page": 12,
              "section": "Results",
              "text": "...",
              "tables": [...]
            }
        Only returns content-rich pages (min 50 words).
        """
        result = self.extract(pdf_bytes)
        if not result["success"]:
            return []

        return [
            {
                "page": p["page"],
                "section": p["section"],
                "text": p["text"],
                "tables": p.get("tables", []),
            }
            for p in result.get("pages", [])
            if p.get("word_count", 0) >= 50
        ]

    def _empty_result(self, error: str) -> Dict[str, Any]:
        return {
            "text": "",
            "title": "",
            "author": None,
            "date": None,
            "year": None,
            "doi": None,
            "page_count": 0,
            "pages": [],
            "sections": {},
            "tables": [],
            "success": False,
            "is_pdf": True,
            "error": error,
        }


# ---------------------------------------------------------------------------
# PDF Downloader (async, with UA spoofing for open-access PDFs)
# ---------------------------------------------------------------------------

class PDFDownloader:
    """
    Async PDF downloader with:
      - Browser-like User-Agent to avoid 403s from institutional repos
      - Follow redirects (important for arXiv, Semantic Scholar PDFs)
      - Timeout control
      - Content-Type validation
    """

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/pdf,*/*",
    }

    async def download(
        self,
        url: str,
        timeout: float = 30.0,
        max_size_mb: float = 20.0,
    ) -> Optional[bytes]:
        """
        Download a PDF from a URL, returning raw bytes or None on failure.
        Validates Content-Type to ensure we got a PDF, not HTML error page.
        """
        if not url:
            return None

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                headers=self.HEADERS,
                follow_redirects=True,
                max_redirects=5,
            ) as client:
                resp = await client.get(url)

                if resp.status_code != 200:
                    logger.warning(f"PDF download returned {resp.status_code} for {url}")
                    return None

                content_type = resp.headers.get("content-type", "").lower()
                if "pdf" not in content_type and "octet-stream" not in content_type:
                    logger.warning(f"Non-PDF content-type '{content_type}' for {url}")
                    return None

                content_len = len(resp.content)
                max_bytes = int(max_size_mb * 1024 * 1024)
                if content_len > max_bytes:
                    logger.warning(f"PDF too large ({content_len} bytes) for {url}, skipping")
                    return None

                return resp.content

        except httpx.TimeoutException:
            logger.warning(f"PDF download timed out for {url}")
        except Exception as e:
            logger.warning(f"PDF download error for {url}: {e}")
        return None

    async def download_and_extract(
        self,
        url: str,
        extractor: Optional[AdvancedPDFExtractor] = None,
    ) -> Dict[str, Any]:
        """Download and extract a PDF in one step."""
        if extractor is None:
            extractor = advanced_pdf_extractor

        pdf_bytes = await self.download(url)
        if not pdf_bytes:
            return extractor._empty_result(f"Download failed for {url}")

        result = extractor.extract(pdf_bytes)
        result["pdf_url"] = url
        return result


# Singletons
advanced_pdf_extractor = AdvancedPDFExtractor()
pdf_downloader = PDFDownloader()


# ---------------------------------------------------------------------------
# Backward-Compatible pdf_extractor Wrapper
# ---------------------------------------------------------------------------

class PDFExtractor:
    """
    Backward-compatible wrapper.
    Day 14 tests use pdf_extractor.extract(pdf_bytes) returning
    {"text", "title", "author", "date", "page_count", "success", "is_pdf", "error"}.
    This thin wrapper delegates to AdvancedPDFExtractor.
    """

    def extract(self, pdf_bytes: bytes) -> Dict[str, Any]:
        result = advanced_pdf_extractor.extract(pdf_bytes)
        # Ensure backward-compat keys
        return {
            "text": result.get("text", ""),
            "title": result.get("title", ""),
            "author": result.get("author"),
            "date": result.get("date"),
            "page_count": result.get("page_count", 0),
            "success": result.get("success", False),
            "is_pdf": True,
            "error": result.get("error"),
        }


pdf_extractor = PDFExtractor()
