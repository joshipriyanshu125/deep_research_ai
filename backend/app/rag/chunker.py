"""
Day 23 — Semantic Chunking

Architecture:
    Document
      ↓
    Sections (Abstract / Introduction / Methods / Results / Conclusion / ...)
      ↓
    Chunks (sentence-boundary-aware, within each section)

Every chunk retains full provenance:
    {
      "document_id": "src_abc123",
      "chunk_id":    "src_abc123_chunk_003",
      "text":        "EV sales grew by 45% YoY...",
      "page":        12,
      "section":     "Results",
      "chunk_index": 3,
      "total_chunks": 18,
      "metadata": { "url": "...", "title": "...", "source_type": "academic" }
    }

Chunking priority:
  1. Respect section boundaries from PDF extractor (Day 22 page/section blocks)
  2. Within each section — split at sentence boundaries (never mid-sentence)
  3. Apply configurable token overlap for retrieval continuity
  4. Skip degenerate chunks (< min_chars)
  5. Fallback: paragraph → sentence-aware character splitting
"""

import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from app.utils.helpers import generate_uuid


# ---------------------------------------------------------------------------
# Chunk Model — the atomic unit of chunked knowledge
# ---------------------------------------------------------------------------

class Chunk(BaseModel):
    """
    Day 23 — Semantic Chunk with full provenance metadata.
    """
    document_id: str                        # Source / document ID
    chunk_id: str = Field(default_factory=generate_uuid)  # Unique chunk ID
    text: str                               # The chunk text content
    page: Optional[int] = None             # Page number (from PDF, if available)
    section: str = "Body"                  # Section name (Abstract, Results, etc.)
    chunk_index: int = 0                   # Position in the sequence for this document
    total_chunks: int = 1                  # Total chunks for this document
    char_start: int = 0                    # Character offset in original document
    char_end: int = 0                      # Character end offset
    word_count: int = 0                    # Word count of this chunk
    has_overlap: bool = False              # True if overlap text from previous chunk is prepended
    metadata: Dict[str, Any] = Field(default_factory=dict)  # URL, title, source_type, etc.

    model_config = {"populate_by_name": True}

    def to_rag_document(self) -> Dict[str, Any]:
        """Convert to the flat dict format used by VectorStore / RAG pipeline."""
        return {
            "content": self.text,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "page": self.page,
            "section": self.section,
            "chunk_index": self.chunk_index,
            "metadata": {
                **self.metadata,
                "document_id": self.document_id,
                "chunk_id": self.chunk_id,
                "page": self.page,
                "section": self.section,
            },
        }


# ---------------------------------------------------------------------------
# Sentence splitter — respects punctuation, avoids mid-sentence cuts
# ---------------------------------------------------------------------------

_SENTENCE_BOUNDARY = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z\"\'\(])"  # classic EOS + capital start
    r"|(?<=\n)\s*\n"                  # blank lines (paragraph breaks)
)

_PARA_BREAK = re.compile(r"\n\s*\n+")


def _split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentence-level segments preserving punctuation.
    Falls back to paragraph-based splitting when no sentence markers found.
    """
    if not text:
        return []

    parts = _SENTENCE_BOUNDARY.split(text.strip())
    sentences = [p.strip() for p in parts if p.strip()]

    # If splitting returned just one block, try paragraph split
    if len(sentences) <= 1:
        paras = [p.strip() for p in _PARA_BREAK.split(text) if p.strip()]
        if len(paras) > 1:
            sentences = paras

    return sentences


def _build_chunks_from_sentences(
    sentences: List[str],
    document_id: str,
    section: str,
    page: Optional[int],
    metadata: Dict[str, Any],
    max_chunk_chars: int,
    overlap_chars: int,
    min_chunk_chars: int,
    chunk_index_start: int = 0,
) -> List[Chunk]:
    """
    Greedily pack sentences into chunks bounded by max_chunk_chars.
    Adds overlap_chars of trailing text from the previous chunk for context continuity.
    """
    chunks: List[Chunk] = []
    current_sentences: List[str] = []
    current_len = 0
    overlap_tail = ""
    char_cursor = 0

    def _flush(is_overlap: bool = False) -> None:
        nonlocal overlap_tail, char_cursor

        if not current_sentences:
            return

        raw = " ".join(current_sentences)
        if is_overlap and overlap_tail:
            text = overlap_tail + " " + raw
        else:
            text = raw

        text = text.strip()
        if len(text) < min_chunk_chars:
            return

        word_count = len(text.split())
        c = Chunk(
            document_id=document_id,
            chunk_id=f"{document_id}_chunk_{chunk_index_start + len(chunks):04d}",
            text=text,
            page=page,
            section=section,
            chunk_index=chunk_index_start + len(chunks),
            char_start=char_cursor,
            char_end=char_cursor + len(text),
            word_count=word_count,
            has_overlap=is_overlap and bool(overlap_tail),
            metadata=metadata,
        )
        chunks.append(c)
        char_cursor += len(raw)

        # Compute overlap tail for the next chunk
        if overlap_chars > 0:
            tail = raw[-overlap_chars:].strip()
            # Trim to sentence boundary to avoid cutting mid-word
            last_sent_end = max(tail.rfind(". "), tail.rfind("? "), tail.rfind("! "))
            if last_sent_end > len(tail) // 3:
                tail = tail[last_sent_end + 2:].strip()
            overlap_tail = tail
        else:
            overlap_tail = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        sent_len = len(sent)

        # Single sentence exceeds max — force-split it at word boundary
        if sent_len > max_chunk_chars:
            _flush(is_overlap=bool(overlap_tail))
            current_sentences = []
            current_len = 0

            # Split oversized sentence at word boundaries
            words = sent.split()
            word_buf: List[str] = []
            word_len = 0
            for word in words:
                if word_len + len(word) + 1 > max_chunk_chars and word_buf:
                    current_sentences = [" ".join(word_buf)]
                    current_len = word_len
                    _flush(is_overlap=bool(overlap_tail))
                    current_sentences = []
                    current_len = 0
                    word_buf = []
                    word_len = 0
                word_buf.append(word)
                word_len += len(word) + 1
            if word_buf:
                current_sentences = [" ".join(word_buf)]
                current_len = word_len
            continue

        # Would exceed limit — flush current buffer first
        if current_len + sent_len + 1 > max_chunk_chars and current_sentences:
            _flush(is_overlap=bool(overlap_tail))
            current_sentences = []
            current_len = 0

        current_sentences.append(sent)
        current_len += sent_len + 1

    # Flush remainder
    _flush(is_overlap=bool(overlap_tail))

    return chunks


# ---------------------------------------------------------------------------
# SemanticChunker — Day 23 main class
# ---------------------------------------------------------------------------

# Sections that are almost never useful for RAG retrieval — skip them
_SKIP_SECTIONS = {"References", "Bibliography", "Acknowledgments", "Appendix"}

# Section order for consistent provenance labeling
_KNOWN_SECTIONS = [
    "Abstract", "Introduction", "Background", "Literature Review",
    "Methods", "Methodology", "Experimental Setup",
    "Results", "Findings", "Discussion", "Analysis",
    "Conclusion", "Future Work",
]


class SemanticChunker:
    """
    Day 23 — Section-aware, sentence-boundary-preserving document chunker.

    Supports two input modes:
      1. Plain text document  →  paragraph-split → sentence-split → chunks
      2. PDF page blocks      →  each block has (page, section, text)
                                 section boundaries are respected directly

    Each output Chunk has: document_id, chunk_id, text, page, section, metadata.
    """

    def __init__(
        self,
        max_chunk_chars: int = 1200,
        overlap_chars: int = 120,
        min_chunk_chars: int = 60,
    ):
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars
        self.min_chunk_chars = min_chunk_chars

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def chunk_document(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        section: str = "Body",
        page: Optional[int] = None,
    ) -> List[Chunk]:
        """
        Chunk a plain-text document.
        Detects section headings within the text and respects them as boundaries.
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        # Try to split on section headings first
        section_blocks = self._split_on_section_headings(text, default_section=section)

        all_chunks: List[Chunk] = []
        for sec_name, sec_text in section_blocks:
            if sec_name in _SKIP_SECTIONS:
                continue
            sentences = _split_into_sentences(sec_text)
            new_chunks = _build_chunks_from_sentences(
                sentences=sentences,
                document_id=document_id,
                section=sec_name,
                page=page,
                metadata=metadata,
                max_chunk_chars=self.max_chunk_chars,
                overlap_chars=self.overlap_chars,
                min_chunk_chars=self.min_chunk_chars,
                chunk_index_start=len(all_chunks),
            )
            all_chunks.extend(new_chunks)

        # Patch total_chunks now that we know the final count
        total = len(all_chunks)
        for c in all_chunks:
            c.total_chunks = total

        return all_chunks

    def chunk_pdf_blocks(
        self,
        page_blocks: List[Dict[str, Any]],
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        """
        Chunk structured page/section blocks from the Day 22 PDF extractor.

        Each block is:
            {"page": 5, "section": "Results", "text": "...", "tables": [...]}

        Section boundaries from the PDF are respected directly — no re-detection needed.
        """
        if not page_blocks:
            return []

        metadata = metadata or {}
        all_chunks: List[Chunk] = []

        for block in page_blocks:
            section = block.get("section", "Body")
            if section in _SKIP_SECTIONS:
                continue

            page = block.get("page")
            text = (block.get("text") or "").strip()
            tables = block.get("tables", [])

            # Add table markdown inline after text
            if tables:
                table_text = "\n\n".join(tables)
                text = text + "\n\n" + table_text if text else table_text

            if not text or len(text) < self.min_chunk_chars:
                continue

            sentences = _split_into_sentences(text)
            new_chunks = _build_chunks_from_sentences(
                sentences=sentences,
                document_id=document_id,
                section=section,
                page=page,
                metadata={**metadata, "page": page},
                max_chunk_chars=self.max_chunk_chars,
                overlap_chars=self.overlap_chars,
                min_chunk_chars=self.min_chunk_chars,
                chunk_index_start=len(all_chunks),
            )
            all_chunks.extend(new_chunks)

        total = len(all_chunks)
        for c in all_chunks:
            c.total_chunks = total

        return all_chunks

    def chunk_source(
        self,
        source: Dict[str, Any],
        document_id: Optional[str] = None,
    ) -> List[Chunk]:
        """
        Convenience method: chunk any Source dict.
        Auto-detects if it has PDF page blocks (from Day 22) or plain text.
        """
        doc_id = document_id or source.get("source_id") or source.get("id") or generate_uuid()
        metadata = {
            "source_id": doc_id,
            "url": source.get("url", ""),
            "title": source.get("title", ""),
            "source_type": source.get("source_type", "web"),
            "domain": source.get("domain", ""),
            "published_at": source.get("published_at"),
        }

        # If the source has PDF page blocks (from Day 22 AcademicPaperAgent)
        evidence_blocks = (source.get("metadata") or {}).get("evidence_blocks", [])
        if evidence_blocks:
            return self.chunk_pdf_blocks(evidence_blocks, document_id=doc_id, metadata=metadata)

        # Otherwise chunk the plain text
        text = source.get("clean_text") or source.get("content") or source.get("snippet") or ""
        return self.chunk_document(text, document_id=doc_id, metadata=metadata)

    def chunk_sources(
        self,
        sources: List[Dict[str, Any]],
    ) -> List[Chunk]:
        """Batch chunk a list of source dicts."""
        all_chunks: List[Chunk] = []
        for s in sources:
            all_chunks.extend(self.chunk_source(s))
        return all_chunks

    # ------------------------------------------------------------------
    # Section heading detection
    # ------------------------------------------------------------------

    _HEADING_PATTERN = re.compile(
        r"^(?:#{1,6}\s+|(?:\d+[\.\s]+))?"
        r"(abstract|introduction|background|related\s+work|literature\s+review|"
        r"methods?|methodology|approach|experimental(?:\s+setup)?|experiments?|"
        r"results?|findings?|discussion|analysis|evaluation|"
        r"conclusion(?:s)?|future\s+work|references?|bibliography|"
        r"acknowledgments?|appendix)"
        r"[\s:#]*$",
        re.IGNORECASE | re.MULTILINE,
    )

    def _split_on_section_headings(
        self,
        text: str,
        default_section: str = "Body",
    ) -> List[tuple]:
        """
        Split text on detected section headings.
        Returns list of (section_name, section_text) pairs.
        If no headings found, returns [(default_section, full_text)].
        """
        lines = text.split("\n")
        sections: List[tuple] = []
        current_section = default_section
        current_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            match = self._HEADING_PATTERN.match(stripped)
            if match and len(stripped) < 80:
                # Save the accumulated lines under the current section
                if current_lines:
                    sec_text = "\n".join(current_lines).strip()
                    if sec_text:
                        sections.append((current_section, sec_text))
                current_section = self._normalize_section_name(match.group(1))
                current_lines = []
            else:
                current_lines.append(line)

        # Flush last section
        if current_lines:
            sec_text = "\n".join(current_lines).strip()
            if sec_text:
                sections.append((current_section, sec_text))

        # No headings found — treat as single section
        if not sections:
            sections = [(default_section, text.strip())]

        return sections

    @staticmethod
    def _normalize_section_name(raw: str) -> str:
        raw = raw.strip().lower()
        if "abstract" in raw:
            return "Abstract"
        if "intro" in raw:
            return "Introduction"
        if "background" in raw or "related" in raw or "literature" in raw:
            return "Background"
        if "method" in raw or "methodology" in raw or "approach" in raw or "experiment" in raw:
            return "Methods"
        if "result" in raw or "finding" in raw:
            return "Results"
        if "discussion" in raw:
            return "Discussion"
        if "analysis" in raw or "evaluat" in raw:
            return "Analysis"
        if "conclusion" in raw or "future" in raw:
            return "Conclusion"
        if "reference" in raw or "bibliog" in raw:
            return "References"
        if "acknowledge" in raw:
            return "Acknowledgments"
        if "appendix" in raw:
            return "Appendix"
        return raw.title()


# ---------------------------------------------------------------------------
# Backward-Compatible TextChunker (wraps SemanticChunker)
# ---------------------------------------------------------------------------

class TextChunker:
    """
    Backward-compatible wrapper around SemanticChunker.
    Existing code that calls text_chunker.chunk_text(text, metadata) continues to work,
    returning the old flat dict format: {"content", "metadata", "start_idx", "end_idx"}.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        overlap: int = 200,
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self._chunker = SemanticChunker(
            max_chunk_chars=chunk_size,
            overlap_chars=overlap,
            min_chunk_chars=50,
        )

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Backward-compatible chunk_text method.
        Returns flat dicts with keys: content, metadata, start_idx, end_idx.
        """
        if not text:
            return []

        metadata = metadata or {}
        doc_id = metadata.get("source_id") or generate_uuid()
        chunks = self._chunker.chunk_document(text, document_id=doc_id, metadata=metadata)

        # Convert to legacy format
        return [
            {
                "content": c.text,
                "metadata": c.metadata,
                "start_idx": c.char_start,
                "end_idx": c.char_end,
                # Extra provenance keys (non-breaking additions)
                "document_id": c.document_id,
                "chunk_id": c.chunk_id,
                "page": c.page,
                "section": c.section,
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ]


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

semantic_chunker = SemanticChunker()
text_chunker = TextChunker()      # backward-compat singleton
