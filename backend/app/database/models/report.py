from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_serializer
from app.utils.helpers import generate_uuid, get_utc_now


class Citation(BaseModel):
    """
    Day 19 — Traceable Source Citation
    Maps back across the hierarchy: Claim -> Evidence -> Source -> URL.
    """
    index: int
    title: str
    url: str
    source_id: Optional[str] = None
    evidence_id: Optional[str] = None
    domain: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[str] = None
    source_type: str = "web"
    snippet: Optional[str] = None
    quote: Optional[str] = None
    claim: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def format_reference(self, style: str = "standard") -> str:
        """
        Format citation entry.
        Standard format: [1] Source Name — URL
        Markdown link format: [1] [Source Name](URL) — domain
        """
        if style == "markdown_link":
            return f"[{self.index}] **[{self.title}]({self.url})**"
        return f"[{self.index}] {self.title} — {self.url}"

    def to_trace_dict(self) -> Dict[str, Any]:
        """Returns the complete provenance record for verification audit."""
        return {
            "index": self.index,
            "claim": self.claim,
            "evidence": self.quote or self.snippet,
            "source_title": self.title,
            "source_id": self.source_id,
            "url": self.url,
            "domain": self.domain,
            "confidence": self.confidence,
        }


class CitationTrace(BaseModel):
    """
    Explicit 4-tier provenance link:
    Claim -> Evidence -> Source -> URL
    """
    claim: str
    evidence: str
    source_title: str
    url: str
    citation_index: int
    evidence_id: Optional[str] = None
    source_id: Optional[str] = None
    confidence: float = 0.90


class FactCheckResult(BaseModel):
    """
    Day 28 — Claim Fact Check Verification Record
    Audits an atomic claim by retrieving supporting evidence, cross-comparing sources,
    checking contradictions, and computing a calibrated confidence score.
    """
    claim: str
    supported: bool = True
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    confidence_level: str = "HIGH"
    confidence_factors: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    verification_status: str = "verified"  # verified, questionable, refuted, unverified
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "supported": self.supported,
            "confidence": round(self.confidence, 4),
            "confidence_level": self.confidence_level,
            "confidence_factors": self.confidence_factors,
            "sources": self.sources,
            "contradictions": self.contradictions,
            "supporting_evidence": self.supporting_evidence,
            "reasoning": self.reasoning,
        }


class ReportSection(BaseModel):
    title: str
    content: str
    citations: List[int] = Field(default_factory=list)


class ResearchReport(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    research_id: str
    title: str
    executive_summary: str
    markdown_content: str
    sections: List[ReportSection] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    traceability_matrix: List[CitationTrace] = Field(default_factory=list)
    key_findings: List[str] = Field(default_factory=list)
    market_analysis: Optional[str] = None
    trends: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    uncertainty: List[str] = Field(default_factory=list)
    fact_checks: List[FactCheckResult] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_level: str = "LOW"
    confidence_factors: List[str] = Field(default_factory=list)
    quality_score: float = 9.5
    created_at: datetime = Field(default_factory=get_utc_now)

    @field_serializer("created_at")
    def _serialize_dt(self, dt: datetime) -> str:
        return dt.isoformat()

