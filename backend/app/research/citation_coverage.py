"""
Day 52 — Citation Coverage

Calculates factual claim provenance and citation coverage:
  Total factual claims = 100
  Supported claims = 94
  Citation coverage = 94%

If coverage falls below the target threshold:
  - Trigger targeted remediation: Research Again (new queries generated)
  - Or: Rewrite/sanitize unsupported sections
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.database.models.evidence import Evidence
from app.database.models.report import ResearchReport, FactCheckResult
from app.research.hallucination import hallucination_detector, HallucinationAuditReport
from app.utils.logger import logger


class CitationCoverageReport(BaseModel):
    """Evaluation of document-level factual grounding and citation completeness."""
    total_claims: int = 0
    supported_claims: int = 0
    unsupported_claims: int = 0
    citation_coverage: float = 1.0  # 0.0 to 1.0 (e.g. 0.94)
    citation_coverage_pct: float = 100.0  # 0.0 to 100.0 (e.g. 94.0)
    threshold: float = 0.85
    meets_threshold: bool = True
    remediation_action: str = "keep"  # "keep", "research_again", "rewrite"
    supported_claims_list: List[str] = Field(default_factory=list)
    unsupported_claims_list: List[str] = Field(default_factory=list)
    suggested_research_queries: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_claims": self.total_claims,
            "supported_claims": self.supported_claims,
            "unsupported_claims": self.unsupported_claims,
            "citation_coverage": round(self.citation_coverage, 4),
            "citation_coverage_pct": round(self.citation_coverage_pct, 2),
            "threshold": self.threshold,
            "meets_threshold": self.meets_threshold,
            "remediation_action": self.remediation_action,
            "supported_claims_count": len(self.supported_claims_list),
            "unsupported_claims_count": len(self.unsupported_claims_list),
            "suggested_research_queries": self.suggested_research_queries,
        }


class CitationCoverageAuditor:
    """
    Day 52 — Automated Citation Coverage Analyzer.
    Evaluates empirical density, validates whether coverage meets target threshold (e.g., >= 85%),
    and recommends automated loop re-triggering or section rewrites.
    """

    def __init__(self, default_threshold: float = 0.85):
        self.default_threshold = default_threshold

    def calculate_coverage(
        self,
        total_claims: int,
        supported_claims: int,
        threshold: Optional[float] = None,
    ) -> CitationCoverageReport:
        """Computes fundamental citation coverage metric."""
        t = threshold if threshold is not None else self.default_threshold
        if total_claims <= 0:
            return CitationCoverageReport(
                total_claims=0,
                supported_claims=0,
                unsupported_claims=0,
                citation_coverage=1.0,
                citation_coverage_pct=100.0,
                threshold=t,
                meets_threshold=True,
                remediation_action="keep",
            )

        unsupported = max(0, total_claims - supported_claims)
        ratio = supported_claims / total_claims
        pct = ratio * 100.0
        meets = ratio >= t

        remediation = "keep" if meets else ("research_again" if ratio < 0.60 else "rewrite")

        return CitationCoverageReport(
            total_claims=total_claims,
            supported_claims=supported_claims,
            unsupported_claims=unsupported,
            citation_coverage=round(ratio, 4),
            citation_coverage_pct=round(pct, 2),
            threshold=t,
            meets_threshold=meets,
            remediation_action=remediation,
        )

    def audit_text(
        self,
        text: str,
        evidence_pool: List[Evidence],
        threshold: Optional[float] = None,
    ) -> CitationCoverageReport:
        """
        Audits markdown or narrative text against the evidence pool,
        extracts claims, checks evidence grounding, and calculates citation coverage.
        """
        audit_rep = hallucination_detector.detect_hallucinations(text, evidence_pool, mode="flag_only")
        t = threshold if threshold is not None else self.default_threshold

        supported_list = [item.claim for item in audit_rep.audit_items if item.is_supported]
        unsupported_list = [item.claim for item in audit_rep.audit_items if not item.is_supported]

        total = len(audit_rep.audit_items)
        supported = len(supported_list)
        unsupported = len(unsupported_list)

        coverage_ratio = (supported / total) if total > 0 else 1.0
        coverage_pct = coverage_ratio * 100.0
        meets = coverage_ratio >= t

        # Remediation strategy:
        # If severe deficit (< 0.60), recommend researching again with targeted queries.
        # If moderate deficit (0.60 <= coverage < threshold), rewrite unsupported claims.
        if meets:
            remediation = "keep"
        elif coverage_ratio < 0.60:
            remediation = "research_again"
        else:
            remediation = "rewrite"

        queries = self.generate_remediation_queries(unsupported_list)

        return CitationCoverageReport(
            total_claims=total,
            supported_claims=supported,
            unsupported_claims=unsupported,
            citation_coverage=round(coverage_ratio, 4),
            citation_coverage_pct=round(coverage_pct, 2),
            threshold=t,
            meets_threshold=meets,
            remediation_action=remediation,
            supported_claims_list=supported_list,
            unsupported_claims_list=unsupported_list,
            suggested_research_queries=queries,
        )

    def audit_report(
        self,
        report: ResearchReport,
        evidence_pool: List[Evidence],
        threshold: Optional[float] = None,
    ) -> CitationCoverageReport:
        """Audits an entire ResearchReport object."""
        return self.audit_text(report.markdown_content, evidence_pool, threshold=threshold)

    def generate_remediation_queries(self, unsupported_claims: List[str], max_queries: int = 5) -> List[str]:
        """
        Transforms unsupported factual assertions into targeted search queries
        to drive supplementary research loops.
        """
        queries: List[str] = []
        for claim in unsupported_claims[:max_queries]:
            # Strip noise and punctuation
            cleaned = re.sub(r"[^\w\s]", " ", claim).strip()
            tokens = [w for w in cleaned.split() if len(w) > 3 and not w.lower() in {
                "this", "that", "these", "those", "have", "been", "with", "from", "report", "suggests"
            }]
            if len(tokens) >= 2:
                q = " ".join(tokens[:7])
                queries.append(f"{q} empirical data evidence")
            elif cleaned:
                queries.append(f"{cleaned[:60]} statistics sources")

        return queries


citation_coverage_auditor = CitationCoverageAuditor()
