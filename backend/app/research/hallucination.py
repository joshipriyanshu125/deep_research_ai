"""
Day 51 — Hallucination Detection

Pipeline:
Generated Report
       ↓
 Extract Claims
       ↓
 Find Evidence
       ↓
Evidence Match?
       ↓
YES → Keep
NO  → Rewrite/remove

Audits synthesized reports to detect and sanitize unsupported assertions or factual hallucinations.
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Optional, Tuple, Set
from pydantic import BaseModel, Field

from app.database.models.evidence import Evidence
from app.database.models.report import ResearchReport
from app.utils.logger import logger


class HallucinationAuditItem(BaseModel):
    """Audit record for an individual statement or claim in the report."""
    claim: str
    is_supported: bool
    confidence: float = 0.0
    matched_evidence_id: Optional[str] = None
    matched_source_title: Optional[str] = None
    matched_quote: Optional[str] = None
    action_taken: str = "keep"  # "keep", "removed", "rewritten"
    rewritten_text: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "is_supported": self.is_supported,
            "confidence": round(self.confidence, 4),
            "matched_evidence_id": self.matched_evidence_id,
            "matched_source_title": self.matched_source_title,
            "matched_quote": self.matched_quote,
            "action_taken": self.action_taken,
            "rewritten_text": self.rewritten_text,
            "reason": self.reason,
        }


class HallucinationAuditReport(BaseModel):
    """Aggregate hallucination evaluation report for a complete document."""
    total_claims: int = 0
    supported_claims: int = 0
    unsupported_claims: int = 0
    hallucination_rate: float = 0.0  # (unsupported_claims / total_claims)
    citation_coverage: float = 1.0  # (supported_claims / total_claims)
    passed: bool = True
    audit_items: List[HallucinationAuditItem] = Field(default_factory=list)
    sanitized_content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_claims": self.total_claims,
            "supported_claims": self.supported_claims,
            "unsupported_claims": self.unsupported_claims,
            "hallucination_rate": round(self.hallucination_rate, 4),
            "citation_coverage": round(self.citation_coverage, 4),
            "passed": self.passed,
            "audit_items": [item.to_dict() for item in self.audit_items],
            "sanitized_content": self.sanitized_content,
        }


class HallucinationDetector:
    """
    Day 51 — Hallucination Detection & Report Verification Engine.
    Executes the 5-stage verification pipeline:
      1. Extract Claims from Markdown / Sections
      2. Match against Verified Evidence Pool
      3. Determine Evidence Match & Confidence
      4. Filter or Rewrite Unsupported Statements
      5. Produce Sanitized Output and Audit Log
    """

    def __init__(self, confidence_threshold: float = 0.45, max_hallucination_rate: float = 0.20):
        self.confidence_threshold = confidence_threshold
        self.max_hallucination_rate = max_hallucination_rate

    def extract_claims(self, markdown_text: str) -> List[str]:
        """
        Extracts factual sentences and assertions from markdown,
        ignoring headers, lists of links, bibliographies, and table borders.
        """
        if not markdown_text or not isinstance(markdown_text, str):
            return []

        # Remove sources / bibliography block at bottom
        cleaned = re.sub(r"##\s*(?:Sources|References|Citations)[\s\S]*$", "", markdown_text, flags=re.IGNORECASE)

        # Split into lines
        lines = cleaned.split("\n")
        sentences: List[str] = []

        for line in lines:
            stripped = line.strip()
            # Ignore headers, table markdown, image markdown, dividers
            if not stripped:
                continue
            if stripped.startswith(("#", "|", "---", "***", "```", "![", "<")):
                continue
            # Remove markdown bullets
            if stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+\.\s+", stripped):
                stripped = re.sub(r"^[-*+]\s+|^\d+\.\s+", "", stripped)

            # Split line into sentences
            raw_sents = re.split(r"(?<=[.!?])\s+", stripped)
            for s in raw_sents:
                clean_s = s.strip()
                # Ignore very short sentence fragments or structural headers
                if len(clean_s) >= 15 and re.search(r"[a-zA-Z]", clean_s):
                    sentences.append(clean_s)

        return sentences

    def verify_claim(
        self,
        claim: str,
        evidence_pool: List[Evidence],
    ) -> Dict[str, Any]:
        """
        Matches a single claim against the evidence pool.
        Evaluates token overlap, entity mentions, numerical metric matches, and source credibility.
        """
        if not evidence_pool or not claim:
            return {
                "is_supported": False,
                "confidence": 0.0,
                "matched_evidence": None,
                "reason": "Empty evidence pool or empty claim.",
            }

        clean_claim = re.sub(r"[^\w\s]", " ", claim.lower())
        # Remove citation annotations e.g. [1], [2]
        clean_claim = re.sub(r"\[\d+\]", "", clean_claim)
        claim_tokens = set([w for w in clean_claim.split() if len(w) > 2])

        if not claim_tokens:
            return {
                "is_supported": False,
                "confidence": 0.0,
                "matched_evidence": None,
                "reason": "Claim has no significant tokens.",
            }

        best_score = 0.0
        best_ev: Optional[Evidence] = None
        best_reason = ""

        for ev in evidence_pool:
            # Exact claim match
            if ev.claim and ev.claim.strip().lower() == claim.strip().lower():
                return {
                    "is_supported": True,
                    "confidence": ev.confidence or 0.95,
                    "matched_evidence": ev,
                    "reason": "Exact claim match in evidence pool.",
                }

            # Textual match against evidence quote, passage, and claim
            ev_body = f"{ev.claim or ''} {ev.quote or ''} {ev.evidence or ''} {ev.passage or ''}".lower()
            ev_tokens = set([w for w in re.sub(r"[^\w\s]", " ", ev_body).split() if len(w) > 2])

            overlap = claim_tokens.intersection(ev_tokens)
            score = len(overlap) / max(len(claim_tokens), 1)

            # Metric verification bonus
            if ev.metrics:
                for metric in ev.metrics:
                    if metric.lower() in clean_claim:
                        score += 0.25

            # Supporting entity bonus
            if ev.supporting_entities:
                for ent in ev.supporting_entities:
                    if ent.lower() in clean_claim:
                        score += 0.20

            # Confidence weighting
            ev_conf = ev.confidence if ev.confidence is not None else 0.85
            composite_score = score * (0.7 + 0.3 * ev_conf)

            # Check if evidence is disputed/refuted
            if ev.verification_status in ("disputed", "refuted"):
                composite_score *= 0.3

            if composite_score > best_score:
                best_score = composite_score
                best_ev = ev
                best_reason = f"Supported by evidence '{ev.claim[:60]}' with {len(overlap)} matching terms."

        is_supported = best_score >= self.confidence_threshold and (best_ev is not None)
        return {
            "is_supported": is_supported,
            "confidence": round(min(1.0, best_score), 4),
            "matched_evidence": best_ev if is_supported else None,
            "reason": best_reason if is_supported else "Insufficient matching evidence found in knowledge pool.",
        }

    def detect_hallucinations(
        self,
        report_content: str,
        evidence_pool: List[Evidence],
        mode: str = "rewrite_or_remove",  # "rewrite_or_remove", "remove", "flag_only"
    ) -> HallucinationAuditReport:
        """
        Executes the hallucination detection pipeline over generated text.
        Pipeline:
          Extract Claims -> Find Evidence -> Evidence Match?
          YES -> Keep
          NO  -> Rewrite/remove
        """
        claims = self.extract_claims(report_content)
        if not claims:
            return HallucinationAuditReport(
                total_claims=0,
                supported_claims=0,
                unsupported_claims=0,
                hallucination_rate=0.0,
                citation_coverage=1.0,
                passed=True,
                audit_items=[],
                sanitized_content=report_content,
            )

        audit_items: List[HallucinationAuditItem] = []
        supported_count = 0
        unsupported_count = 0

        # Track replacements for sanitization
        replacements: Dict[str, str] = {}

        for claim in claims:
            res = self.verify_claim(claim, evidence_pool)
            is_supported = res["is_supported"]
            conf = res["confidence"]
            matched_ev: Optional[Evidence] = res["matched_evidence"]
            reason = res["reason"]

            if is_supported:
                supported_count += 1
                audit_items.append(
                    HallucinationAuditItem(
                        claim=claim,
                        is_supported=True,
                        confidence=conf,
                        matched_evidence_id=matched_ev.id if matched_ev else None,
                        matched_source_title=matched_ev.source_title if matched_ev else None,
                        matched_quote=matched_ev.quote or matched_ev.evidence if matched_ev else None,
                        action_taken="keep",
                        rewritten_text=None,
                        reason=reason,
                    )
                )
            else:
                unsupported_count += 1
                if mode == "remove":
                    action = "removed"
                    rewritten = ""
                elif mode == "rewrite_or_remove":
                    # If partially relevant or general, soften with qualifying language or remove
                    if conf >= 0.25:
                        action = "rewritten"
                        rewritten = self._rewrite_claim_as_unverified(claim)
                    else:
                        action = "removed"
                        rewritten = ""
                else:
                    action = "flagged"
                    rewritten = claim

                replacements[claim] = rewritten
                audit_items.append(
                    HallucinationAuditItem(
                        claim=claim,
                        is_supported=False,
                        confidence=conf,
                        matched_evidence_id=None,
                        matched_source_title=None,
                        matched_quote=None,
                        action_taken=action,
                        rewritten_text=rewritten if action == "rewritten" else None,
                        reason=reason,
                    )
                )

        total_claims = len(claims)
        hallucination_rate = (unsupported_count / total_claims) if total_claims > 0 else 0.0
        citation_coverage = (supported_count / total_claims) if total_claims > 0 else 1.0
        passed = hallucination_rate <= self.max_hallucination_rate

        sanitized = self._apply_sanitization(report_content, replacements)

        return HallucinationAuditReport(
            total_claims=total_claims,
            supported_claims=supported_count,
            unsupported_claims=unsupported_count,
            hallucination_rate=hallucination_rate,
            citation_coverage=citation_coverage,
            passed=passed,
            audit_items=audit_items,
            sanitized_content=sanitized,
        )

    def _rewrite_claim_as_unverified(self, claim: str) -> str:
        """Softens an uncorroborated claim with speculative or preliminary context."""
        cleaned = re.sub(r"\[\d+\]", "", claim).strip()
        # Prefix with cautious qualifier if not already present
        if not re.match(r"^(According to preliminary|Unverified reports suggest|Further research is needed to confirm)", cleaned, re.IGNORECASE):
            return f"Preliminary estimates suggest that {cleaned[:1].lower() + cleaned[1:] if len(cleaned) > 1 else cleaned}"
        return cleaned

    def _apply_sanitization(self, original_text: str, replacements: Dict[str, str]) -> str:
        """Replaces or removes unsupported claims in the document body."""
        result = original_text
        for orig, replacement in replacements.items():
            if replacement:
                result = result.replace(orig, replacement)
            else:
                # Remove sentence and tidy up leftover double whitespace
                pattern = re.escape(orig) + r"\s*"
                result = re.sub(pattern, "", result)

        # Clean up empty bullet points or double blank lines
        result = re.sub(r"\n\s*[-*+]\s*\n", "\n", result)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    async def audit_and_sanitize_report(
        self,
        report: ResearchReport,
        evidence_pool: List[Evidence],
    ) -> Tuple[ResearchReport, HallucinationAuditReport]:
        """
        Full post-processing step for Day 51:
        Audits the ResearchReport markdown content and executive summary,
        updates the markdown with sanitized content, and appends audit results to metadata.
        """
        audit_report = self.detect_hallucinations(report.markdown_content, evidence_pool)
        report.markdown_content = audit_report.sanitized_content

        # Also sanitize executive summary if needed
        exec_audit = self.detect_hallucinations(report.executive_summary, evidence_pool)
        if exec_audit.unsupported_claims > 0:
            report.executive_summary = exec_audit.sanitized_content

        return report, audit_report


hallucination_detector = HallucinationDetector()
