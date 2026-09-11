"""
Day 19 — Citation System

Core Architecture:
    Claim
      ↓
    Evidence
      ↓
    Source
      ↓
    URL

Final Report Format:
    India's EV market grew significantly during the period studied.[1]

    ## Sources & References

    [1] Source Name — URL
"""

import re
from typing import List, Dict, Any, Optional, Set, Tuple
from app.database.models.source import Source
from app.database.models.evidence import Evidence
from app.database.models.report import Citation, CitationTrace
from app.utils.logger import logger


class CitationEngine:
    """
    Day 19 Automated Citation and Provenance Engine.
    Handles citation index assignment, Claim->Evidence->Source->URL traceability,
    automated inline citation injection, bibliography generation, and integrity verification.
    """

    def build_citations(
        self,
        sources: List[Source],
        evidence_list: Optional[List[Evidence]] = None,
    ) -> List[Citation]:
        """
        Construct a normalized, deduplicated list of sequential citations (indexed [1], [2], ...).
        """
        citations: List[Citation] = []
        seen_urls: Set[str] = set()
        seen_source_ids: Set[str] = set()

        evidence_by_source: Dict[str, List[Evidence]] = {}
        if evidence_list:
            for ev in evidence_list:
                sid = ev.source_id
                if sid not in evidence_by_source:
                    evidence_by_source[sid] = []
                evidence_by_source[sid].append(ev)

        idx = 1
        for s in sources:
            canonical_url = (s.url or "").strip().rstrip("/")
            sid = s.source_id or s.id

            # Deduplicate by URL and source_id
            if canonical_url and canonical_url in seen_urls:
                continue
            if sid and sid in seen_source_ids:
                continue

            if canonical_url:
                seen_urls.add(canonical_url)
            if sid:
                seen_source_ids.add(sid)

            # Link relevant evidence if available
            ev_items = evidence_by_source.get(sid, [])
            sample_quote = ev_items[0].quote if ev_items else (s.snippet or "")
            sample_claim = ev_items[0].claim if ev_items else None
            conf = ev_items[0].confidence if ev_items else getattr(s, "credibility_score", 0.90)

            title = (s.title or "").strip() or f"Source {idx}"
            domain = getattr(s, "domain", "") or ""

            citations.append(
                Citation(
                    index=idx,
                    title=title,
                    url=s.url,
                    source_id=sid,
                    domain=domain,
                    author=getattr(s, "author", None),
                    published_at=getattr(s, "published_at", None) or getattr(s, "publication_date", None),
                    source_type=getattr(s, "source_type", "web") or "web",
                    snippet=s.snippet or "",
                    quote=sample_quote,
                    claim=sample_claim,
                    confidence=conf,
                )
            )
            idx += 1

        return citations

    def build_traceability_matrix(
        self,
        evidence_list: List[Evidence],
        sources: List[Source],
        citations: Optional[List[Citation]] = None,
    ) -> List[CitationTrace]:
        """
        Construct explicit 4-tier provenance chains:
        Claim -> Evidence -> Source -> URL
        """
        if citations is None:
            citations = self.build_citations(sources, evidence_list)

        # Index citations by source_id and URL
        cit_by_source_id: Dict[str, Citation] = {c.source_id: c for c in citations if c.source_id}
        cit_by_url: Dict[str, Citation] = {c.url.strip().rstrip("/"): c for c in citations if c.url}

        # Index sources by source_id
        src_by_id: Dict[str, Source] = {s.source_id or s.id: s for s in sources}

        traces: List[CitationTrace] = []
        for ev in evidence_list:
            matched_cit = cit_by_source_id.get(ev.source_id)
            if not matched_cit and ev.source_url:
                matched_cit = cit_by_url.get(ev.source_url.strip().rstrip("/"))

            src_obj = src_by_id.get(ev.source_id)

            source_title = (
                (matched_cit.title if matched_cit else None)
                or (src_obj.title if src_obj else None)
                or ev.source_title
                or "Unknown Source"
            )
            url = (
                (matched_cit.url if matched_cit else None)
                or (src_obj.url if src_obj else None)
                or ev.source_url
                or ""
            )
            cit_idx = matched_cit.index if matched_cit else 1

            traces.append(
                CitationTrace(
                    claim=ev.claim,
                    evidence=ev.evidence or ev.quote,
                    source_title=source_title,
                    url=url,
                    citation_index=cit_idx,
                    evidence_id=ev.id,
                    source_id=ev.source_id,
                    confidence=ev.confidence,
                )
            )

        return traces

    def format_bibliography_markdown(
        self,
        citations: List[Citation],
        style: str = "standard",
    ) -> str:
        """
        Format the bibliography section in Markdown.
        Standard format produces:
            ## Sources & References

            [1] Source Name — URL
            [2] Second Source — URL
        """
        if not citations:
            return ""

        lines = ["## Sources & References\n"]
        for c in citations:
            lines.append(c.format_reference(style=style))
        return "\n".join(lines) + "\n"

    def inject_citations_to_text(
        self,
        text: str,
        evidence_list: List[Evidence],
        citations: List[Citation],
    ) -> str:
        """
        Automatically attaches inline citations e.g. 'India's EV market grew significantly.[1]'
        Matches key evidence phrases or claims in narrative sentences.
        """
        if not text or not citations:
            return text

        # Map evidence / claim keywords to citation indices
        cit_by_source_id = {c.source_id: c.index for c in citations if c.source_id}

        sentences = re.split(r"(?<=[.!?])\s+", text)
        annotated_sentences = []

        for sent in sentences:
            stripped = sent.strip()
            if not stripped or len(stripped) < 20 or "[" in stripped:
                annotated_sentences.append(sent)
                continue

            matched_idx: Optional[int] = None
            sent_lower = stripped.lower()

            # Find matching evidence for this sentence
            for ev in evidence_list:
                claim_tokens = [w for w in re.findall(r"\w+", ev.claim.lower()) if len(w) > 3]
                if not claim_tokens:
                    continue
                match_count = sum(1 for tok in claim_tokens if tok in sent_lower)
                overlap_ratio = match_count / len(claim_tokens)

                if overlap_ratio >= 0.55 or (ev.metrics and any(m.lower() in sent_lower for m in ev.metrics)):
                    matched_idx = cit_by_source_id.get(ev.source_id)
                    if matched_idx:
                        break

            if matched_idx:
                # Attach citation before or after punctuation cleanly: Statement.[1]
                if stripped.endswith((".", "!", "?")):
                    punc = stripped[-1]
                    body = stripped[:-1].rstrip()
                    annotated_sentences.append(f"{body}.[{matched_idx}]")
                else:
                    annotated_sentences.append(f"{stripped} [{matched_idx}]")
            else:
                annotated_sentences.append(sent)

        return " ".join(annotated_sentences)

    def extract_citation_indices(self, text: str) -> List[int]:
        """
        Extract all citation numbers [1], [2] referenced in markdown text.
        """
        if not text:
            return []
        matches = re.findall(r"\[(\d+)\]", text)
        indices = sorted(list({int(m) for m in matches}))
        return indices

    def verify_citations(
        self,
        markdown_content: str,
        citations: List[Citation],
    ) -> Dict[str, Any]:
        """
        Audit citation consistency between inline anchors and bibliography.
        Detects orphaned citation markers and missing entries.
        """
        cited_indices = set(self.extract_citation_indices(markdown_content))
        valid_indices = {c.index for c in citations}

        # Indices cited in body text that have no corresponding source in bibliography
        orphan_indices = sorted(list(cited_indices - valid_indices))
        # Indices in bibliography not referenced anywhere in text
        unused_indices = sorted(list(valid_indices - cited_indices))

        return {
            "valid": len(orphan_indices) == 0,
            "cited_indices": sorted(list(cited_indices)),
            "available_indices": sorted(list(valid_indices)),
            "orphan_indices": orphan_indices,
            "unused_indices": unused_indices,
            "total_citations": len(citations),
        }

    def append_bibliography_if_missing(
        self,
        markdown_body: str,
        citations: List[Citation],
        style: str = "standard",
    ) -> str:
        """
        Ensures standardized bibliography is present in markdown:
            ## Sources & References

            [1] Source Name — URL
        """
        if not citations:
            return markdown_body

        body = (markdown_body or "").strip()
        if "## Sources & References" in body:
            return body

        # Remove any ad-hoc LLM-generated citations block at the end and append standard format
        cleaned_body = re.sub(r"##\s*(?:Sources|References|Citations)[\s\S]*$", "", body, flags=re.IGNORECASE).rstrip()
        bib = self.format_bibliography_markdown(citations, style=style)
        return f"{cleaned_body}\n\n{bib}"



# Global singleton instance
citation_engine = CitationEngine()

