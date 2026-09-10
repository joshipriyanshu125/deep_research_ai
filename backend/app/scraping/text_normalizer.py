"""
Day 15 — Text Normalizer
Normalizes raw scraped text across four critical dimensions:
  1. HTML entities decoding (&amp;, &nbsp;, &quot;, &#39;, &mdash;, etc.)
  2. Unicode encoding normalization (NFKC, control characters, smart quotes)
  3. Whitespace normalization (NBSP, tabs, multiple spaces, line endings)
  4. Duplicate content and boilerplate paragraph removal
"""
import html
import re
import unicodedata
from typing import List, Set, Optional


class TextNormalizer:
    """
    Comprehensive text cleaning and normalization pipeline.
    """

    _ZERO_WIDTH_CHARS = re.compile(r"[\u200B-\u200D\uFEFF\u200E\u200F\u00AD]")
    _CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\uFFFD]")

    def normalize(self, text: str) -> str:
        """
        Execute full normalization pipeline on text.
        """
        if not text or not isinstance(text, str):
            return ""

        # 1. Decode HTML entities first
        text = self.decode_html_entities(text)

        # 2. Normalize encoding & Unicode
        text = self.normalize_encoding(text)

        # 3. Normalize whitespace & linebreaks
        text = self.normalize_whitespace(text)

        # 4. Deduplicate repeated content / boilerplate paragraphs
        text = self.deduplicate_content(text)

        # 5. Final whitespace polish
        text = self.normalize_whitespace(text)

        return text.strip()

    def decode_html_entities(self, text: str) -> str:
        """
        Decode standard, numeric, and double-escaped HTML entities.
        """
        if not text:
            return ""

        # First pass unescape
        decoded = html.unescape(text)

        # Handle double-escaped entities (e.g. &amp;quot; -> &quot; -> ")
        if "&" in decoded and re.search(r"&(?:amp|lt|gt|quot|apos|dollar|#\d+|#x[0-9a-fA-F]+);", decoded):
            decoded = html.unescape(decoded)

        # Replace non-breaking space entities specifically if raw
        decoded = decoded.replace("&nbsp;", " ").replace("&#160;", " ")
        decoded = decoded.replace("&dollar;", "$")
        return decoded

    def normalize_encoding(self, text: str) -> str:
        """
        Apply Unicode NFKC normalization, strip null bytes, fix smart quotes, and remove invisible control characters.
        """
        if not text:
            return ""

        # Unicode NFKC normalization (replaces weird compatibility chars with standard forms)
        normalized = unicodedata.normalize("NFKC", text)

        # Strip zero-width spaces and soft hyphens
        normalized = self._ZERO_WIDTH_CHARS.sub("", normalized)

        # Strip non-printable control characters (keeping \n and \t)
        normalized = self._CONTROL_CHARS.sub("", normalized)

        # Standardize smart quotes and apostrophes to standard ASCII quotes
        normalized = normalized.replace("’", "'").replace("‘", "'").replace("`", "'")
        normalized = normalized.replace("“", '"').replace("”", '"')

        return normalized

    def normalize_whitespace(self, text: str) -> str:
        """
        Clean non-breaking spaces, collapse multiple inline spaces, trim lines,
        and normalize paragraph breaks to max 2 newlines.
        """
        if not text:
            return ""

        # Replace non-breaking spaces and tabs
        cleaned = text.replace("\u00a0", " ").replace("\t", " ")

        # Normalize line endings to \n
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

        # Process line by line: collapse inline spaces and trim
        lines = []
        for line in cleaned.splitlines():
            # Collapse multiple spaces within a line
            collapsed_line = re.sub(r"[ ]{2,}", " ", line).strip()
            lines.append(collapsed_line)

        cleaned_text = "\n".join(lines)

        # Collapse 3 or more newlines into double newlines (paragraphs)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

        return cleaned_text.strip()

    def deduplicate_content(self, text: str, min_chars: int = 30) -> str:
        """
        Remove duplicate paragraphs and repeated boilerplate sections
        while preserving headings and document structure.
        """
        if not text:
            return ""

        paragraphs = text.split("\n\n")
        if len(paragraphs) <= 1:
            return text

        seen_fingerprints: Set[str] = set()
        unique_paragraphs: List[str] = []

        for p in paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue

            # Always keep markdown headings
            if p_strip.startswith("#"):
                unique_paragraphs.append(p_strip)
                continue

            # Generate simplified fingerprint for fuzzy duplicate detection
            # Lowercase, alphanumeric only
            fingerprint = re.sub(r"[^a-z0-9]", "", p_strip.lower())

            if fingerprint and len(fingerprint) >= min_chars:
                if fingerprint in seen_fingerprints:
                    continue  # Skip duplicate paragraph
                seen_fingerprints.add(fingerprint)

            unique_paragraphs.append(p_strip)

        return "\n\n".join(unique_paragraphs)


text_normalizer = TextNormalizer()
