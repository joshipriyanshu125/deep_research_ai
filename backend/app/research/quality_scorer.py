"""
Day 50 — Research Quality Scorer

Computes a multi-dimensional quality score for a completed research session.

Research Quality
----------------
Source Quality       92
Evidence Coverage    87
Citation Coverage    94
Recency              89
Consistency           91
Completeness          86
----------------
Overall              90

Each dimension is scored 0–100 and the weighted average is the Overall score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database.models.evidence import Evidence
from app.database.models.report import Citation, FactCheckResult, ResearchReport
from app.database.models.research import ResearchTask
from app.database.models.source import Source


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class QualityDimension:
    """A single scored dimension of research quality."""
    name: str
    score: float          # 0–100
    weight: float         # 0–1 (weights must sum to 1)
    rationale: str = ""   # Human-readable explanation

    def weighted(self) -> float:
        return self.score * self.weight


@dataclass
class ResearchQualityScore:
    """
    Complete multi-dimensional quality assessment.

    Dimensions:
      - source_quality:     Credibility and authority of sources used.
      - evidence_coverage:  How well evidence covers the research questions.
      - citation_coverage:  What fraction of claims are backed by citations.
      - recency:            How up-to-date the sources are.
      - consistency:        Degree of agreement / low contradiction rate.
      - completeness:       Whether all planned tasks were completed.

    Overall = weighted average of all dimensions.
    """
    source_quality: float = 0.0
    evidence_coverage: float = 0.0
    citation_coverage: float = 0.0
    recency: float = 0.0
    consistency: float = 0.0
    completeness: float = 0.0
    overall: float = 0.0
    dimensions: List[QualityDimension] = field(default_factory=list)
    grade: str = "F"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": round(self.overall, 1),
            "grade": self.grade,
            "dimensions": {
                "source_quality": round(self.source_quality, 1),
                "evidence_coverage": round(self.evidence_coverage, 1),
                "citation_coverage": round(self.citation_coverage, 1),
                "recency": round(self.recency, 1),
                "consistency": round(self.consistency, 1),
                "completeness": round(self.completeness, 1),
            },
            "metadata": self.metadata,
        }

    def format_report(self) -> str:
        """Return a pretty-printed quality scorecard."""
        lines = [
            "Research Quality",
            "----------------",
            f"Source Quality       {self.source_quality:>5.0f}",
            f"Evidence Coverage    {self.evidence_coverage:>5.0f}",
            f"Citation Coverage    {self.citation_coverage:>5.0f}",
            f"Recency              {self.recency:>5.0f}",
            f"Consistency          {self.consistency:>5.0f}",
            f"Completeness         {self.completeness:>5.0f}",
            "----------------",
            f"Overall              {self.overall:>5.0f}  [{self.grade}]",
        ]
        return "\n".join(lines)


def _letter_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class ResearchQualityScorer:
    """
    Day 50 — Computes a multi-dimensional research quality score.

    Usage::

        scorer = ResearchQualityScorer()
        quality = scorer.score(
            sources=sources,
            evidence=evidence,
            tasks=tasks,
            citations=citations,
            fact_checks=fact_checks,
        )
        print(quality.format_report())
    """

    # Dimension weights (must sum to 1.0)
    WEIGHTS = {
        "source_quality":    0.25,
        "evidence_coverage": 0.20,
        "citation_coverage": 0.20,
        "recency":           0.15,
        "consistency":       0.10,
        "completeness":      0.10,
    }

    def score(
        self,
        sources: List[Source],
        evidence: List[Evidence],
        tasks: List[ResearchTask],
        citations: Optional[List[Citation]] = None,
        fact_checks: Optional[List[FactCheckResult]] = None,
        report: Optional[ResearchReport] = None,
    ) -> ResearchQualityScore:
        """
        Compute the full multi-dimensional quality score.

        Args:
            sources:     All sources collected.
            evidence:    All evidence items.
            tasks:       All research tasks (original + adaptive).
            citations:   Citation objects (for citation coverage).
            fact_checks: Fact-check results (for consistency score).
            report:      Final ResearchReport if available (extra signals).

        Returns:
            ResearchQualityScore with individual dimension scores and overall.
        """
        citations = citations or []
        fact_checks = fact_checks or []

        sq  = self._score_source_quality(sources)
        ec  = self._score_evidence_coverage(evidence, tasks)
        cc  = self._score_citation_coverage(evidence, citations)
        rec = self._score_recency(sources)
        con = self._score_consistency(fact_checks, evidence)
        com = self._score_completeness(tasks)

        dimensions = [
            QualityDimension("Source Quality",    sq,  self.WEIGHTS["source_quality"],    sq.get("rationale", "")),
            QualityDimension("Evidence Coverage", ec,  self.WEIGHTS["evidence_coverage"],  ec.get("rationale", "")),
            QualityDimension("Citation Coverage", cc,  self.WEIGHTS["citation_coverage"],  cc.get("rationale", "")),
            QualityDimension("Recency",           rec, self.WEIGHTS["recency"],            rec.get("rationale", "")),
            QualityDimension("Consistency",       con, self.WEIGHTS["consistency"],        con.get("rationale", "")),
            QualityDimension("Completeness",      com, self.WEIGHTS["completeness"],       com.get("rationale", "")),
        ] if False else []  # replaced below

        sq_val  = sq["score"]
        ec_val  = ec["score"]
        cc_val  = cc["score"]
        rec_val = rec["score"]
        con_val = con["score"]
        com_val = com["score"]

        dimensions = [
            QualityDimension("Source Quality",    sq_val,  self.WEIGHTS["source_quality"],    sq["rationale"]),
            QualityDimension("Evidence Coverage", ec_val,  self.WEIGHTS["evidence_coverage"],  ec["rationale"]),
            QualityDimension("Citation Coverage", cc_val,  self.WEIGHTS["citation_coverage"],  cc["rationale"]),
            QualityDimension("Recency",           rec_val, self.WEIGHTS["recency"],            rec["rationale"]),
            QualityDimension("Consistency",       con_val, self.WEIGHTS["consistency"],        con["rationale"]),
            QualityDimension("Completeness",      com_val, self.WEIGHTS["completeness"],       com["rationale"]),
        ]

        overall = sum(d.weighted() for d in dimensions)

        return ResearchQualityScore(
            source_quality=sq_val,
            evidence_coverage=ec_val,
            citation_coverage=cc_val,
            recency=rec_val,
            consistency=con_val,
            completeness=com_val,
            overall=round(overall, 1),
            dimensions=dimensions,
            grade=_letter_grade(overall),
            metadata={
                "source_count": len(sources),
                "evidence_count": len(evidence),
                "task_count": len(tasks),
                "citation_count": len(citations),
                "fact_check_count": len(fact_checks),
            },
        )

    # ------------------------------------------------------------------
    # Dimension scorers (each returns {"score": 0–100, "rationale": str})
    # ------------------------------------------------------------------

    def _score_source_quality(self, sources: List[Source]) -> Dict[str, Any]:
        if not sources:
            return {"score": 0.0, "rationale": "No sources collected"}

        credibility_scores = [
            float(getattr(s, "credibility_score", 0.5))
            for s in sources
        ]
        avg_credibility = sum(credibility_scores) / len(credibility_scores)

        # Bonus for source type diversity
        source_types = {getattr(s, "source_type", getattr(s, "type", "web")) for s in sources}
        diversity_bonus = min(10.0, len(source_types) * 3.0)

        # Bonus for source count
        count_bonus = min(10.0, len(sources) * 1.0)

        score = avg_credibility * 80.0 + diversity_bonus + count_bonus
        score = min(100.0, score)

        return {
            "score": round(score, 1),
            "rationale": (
                f"Avg credibility {avg_credibility:.2f} across {len(sources)} sources "
                f"({len(source_types)} types)"
            ),
        }

    def _score_evidence_coverage(
        self, evidence: List[Evidence], tasks: List[ResearchTask]
    ) -> Dict[str, Any]:
        if not tasks:
            return {"score": 0.0, "rationale": "No tasks defined"}

        task_count = len(tasks)
        # Heuristic: aim for ~3 evidence items per task
        target_evidence = task_count * 3
        actual_evidence = len(evidence)
        ratio = min(1.0, actual_evidence / max(1, target_evidence))

        # High-confidence evidence bonus
        high_conf = sum(1 for ev in evidence if float(ev.confidence) >= 0.85)
        conf_bonus = min(15.0, high_conf * 1.5)

        score = ratio * 85.0 + conf_bonus
        score = min(100.0, score)

        return {
            "score": round(score, 1),
            "rationale": (
                f"{actual_evidence} evidence items for {task_count} tasks "
                f"({high_conf} high-confidence)"
            ),
        }

    def _score_citation_coverage(
        self, evidence: List[Evidence], citations: List[Citation]
    ) -> Dict[str, Any]:
        if not evidence:
            return {"score": 0.0, "rationale": "No evidence to cite"}

        cited_evidence = sum(
            1 for ev in evidence if ev.source_id and any(
                getattr(c, "source_id", None) == ev.source_id for c in citations
            )
        )
        # Fallback: just check citation count vs evidence count
        if not citations:
            ratio = 0.0
        else:
            ratio = min(1.0, len(citations) / max(1, len(evidence)))

        score = ratio * 100.0

        return {
            "score": round(score, 1),
            "rationale": (
                f"{len(citations)} citations for {len(evidence)} evidence items "
                f"({ratio:.0%} coverage)"
            ),
        }

    def _score_recency(self, sources: List[Source]) -> Dict[str, Any]:
        if not sources:
            return {"score": 0.0, "rationale": "No sources"}

        current_year = datetime.now().year
        recency_scores = []

        for s in sources:
            date_str = str(
                getattr(s, "published_at", None)
                or getattr(s, "publication_date", None)
                or ""
            )
            match = re.search(r"\b(20\d{2})\b", date_str)
            if match:
                year = int(match.group(1))
                age = current_year - year
                # Full score for ≤1 year old, declining by 10% per year, min 30
                recency_scores.append(max(30.0, 100.0 - age * 10.0))

        if not recency_scores:
            # No dates found — give neutral score
            return {"score": 65.0, "rationale": "Publication dates not available; neutral score applied"}

        avg = sum(recency_scores) / len(recency_scores)
        return {
            "score": round(avg, 1),
            "rationale": (
                f"Average source recency {avg:.0f}/100 across {len(recency_scores)} dated sources"
            ),
        }

    def _score_consistency(
        self, fact_checks: List[FactCheckResult], evidence: List[Evidence]
    ) -> Dict[str, Any]:
        # Use fact-check pass rate as primary consistency signal
        if fact_checks:
            supported = sum(1 for fc in fact_checks if getattr(fc, "supported", True))
            pass_rate = supported / max(1, len(fact_checks))
            score = pass_rate * 100.0
            rationale = (
                f"{supported}/{len(fact_checks)} claims verified "
                f"({pass_rate:.0%} consistency)"
            )
        else:
            # Estimate from evidence verification status
            verified = sum(
                1 for ev in evidence
                if getattr(ev, "verification_status", "verified") == "verified"
            )
            if evidence:
                rate = verified / len(evidence)
                score = rate * 80.0 + 10.0  # slight boost for having evidence
                rationale = (
                    f"{verified}/{len(evidence)} evidence items verified "
                    f"(no explicit fact checks)"
                )
            else:
                score = 50.0
                rationale = "No fact checks or evidence available"

        return {"score": round(min(100.0, score), 1), "rationale": rationale}

    def _score_completeness(self, tasks: List[ResearchTask]) -> Dict[str, Any]:
        if not tasks:
            return {"score": 0.0, "rationale": "No tasks defined"}

        completed = sum(1 for t in tasks if t.status == "completed")
        total = len(tasks)
        rate = completed / total

        # Bonus for having multiple categories covered
        categories = {t.category for t in tasks if t.status == "completed"}
        cat_bonus = min(15.0, len(categories) * 5.0)

        score = rate * 85.0 + cat_bonus
        score = min(100.0, score)

        return {
            "score": round(score, 1),
            "rationale": (
                f"{completed}/{total} tasks completed "
                f"({len(categories)} categories: {', '.join(sorted(categories))})"
            ),
        }


# Singleton
research_quality_scorer = ResearchQualityScorer()

__all__ = [
    "QualityDimension",
    "ResearchQualityScore",
    "ResearchQualityScorer",
    "research_quality_scorer",
]
