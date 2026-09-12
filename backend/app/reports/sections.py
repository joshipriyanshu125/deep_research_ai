"""Query-driven section selection for structured research reports."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Sequence

from app.database.models.report import ReportSection

if TYPE_CHECKING:
    from app.agents.synthesizer import SynthesisResult


def select_report_section_keys(query: str) -> List[str]:
    """Return report sections relevant to a question, preserving a market default."""
    normalized = query.lower()
    keys = ["executive_summary", "key_findings", "evidence_analysis"]

    market_terms = ("market", "industry", "sales", "revenue", "pricing", "customer", "commercial", "business")
    technical_terms = ("technical", "technology", "engineering", "architecture", "algorithm", "science", "research")
    comparison_terms = ("compare", "comparison", "benchmark", "versus", " vs ", "alternative", "evaluation")
    risk_terms = ("risk", "security", "safety", "regulation", "regulatory", "compliance", "limitation")
    strategy_terms = ("recommend", "strategy", "decision", "roadmap", "investment", "opportunity", "action")

    if any(term in normalized for term in market_terms):
        keys.append("market_analysis")
    if any(term in normalized for term in technical_terms):
        keys.append("technical_analysis")
    if any(term in normalized for term in comparison_terms):
        keys.append("comparative_analysis")
    if any(term in normalized for term in risk_terms):
        keys.append("risks")
    if any(term in normalized for term in strategy_terms):
        keys.append("recommendations")

    if len(keys) == 3:
        keys.extend(("market_analysis", "risks"))
    return keys


def build_report_sections(
    query: str,
    synthesis: SynthesisResult,
    markdown_content: str,
    cited_indices: Sequence[int],
) -> List[ReportSection]:
    """Materialize selected section keys into the existing ReportSection schema."""
    citations = list(cited_indices)
    content = {
        "executive_summary": synthesis.executive_summary
        or "High-level distillation of core empirical findings.",
        "key_findings": "\n".join(f"- {finding}" for finding in synthesis.key_findings),
        "evidence_analysis": markdown_content,
        "market_analysis": synthesis.market_analysis
        or "Evaluation of market structure, adoption, and competitive dynamics.",
        "technical_analysis": "\n".join(
            [f"- **Trend**: {trend}" for trend in synthesis.trends]
            + [f"- **Opportunity**: {item}" for item in synthesis.opportunities]
        ),
        "comparative_analysis": "\n".join(
            [f"- {finding}" for finding in synthesis.key_findings]
            + [f"- **Uncertainty**: {item}" for item in synthesis.uncertainty]
        ),
        "risks": "\n".join(
            [f"- **Risk**: {item}" for item in synthesis.risks]
            + [f"- **Contradiction**: {item}" for item in synthesis.contradictions]
            + [f"- **Uncertainty**: {item}" for item in synthesis.uncertainty]
        ),
        "recommendations": "\n".join(f"- {item}" for item in synthesis.recommendations),
    }
    titles = {
        "executive_summary": "Executive Summary",
        "key_findings": "Key Findings",
        "evidence_analysis": "Evidence & Deep-Dive Analysis",
        "market_analysis": "Market Analysis & Commercial Trajectory",
        "technical_analysis": "Technical & Empirical Analysis",
        "comparative_analysis": "Comparative Metrics & Evaluation",
        "risks": "Risks, Contradictions & Epistemic Uncertainty",
        "recommendations": "Strategic Recommendations",
    }
    return [
        ReportSection(
            title=titles[key],
            content=content[key] or "No specific findings were available for this section.",
            citations=citations if key in {"evidence_analysis", "technical_analysis"} else citations[:3],
        )
        for key in select_report_section_keys(query)
    ]
