"""
Day 48 — Adaptive Research Loop

Instead of a fixed workflow, the system discovers gaps, contradictions, and
missing information mid-research and spawns new tasks dynamically.

Adaptive loop:
  Planner
    ↓
  Research
    ↓
  Finds missing information  →  Creates new task  →  Researches it
    ↓
  Discovers contradiction    →  Creates verification task  →  Verifies
    ↓
  Continues until stopping criteria met

Works alongside Day 49 stopping criteria.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from app.database.models.evidence import Evidence
from app.database.models.research import ResearchTask
from app.database.models.source import Source
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Gap / Contradiction detectors
# ---------------------------------------------------------------------------

# Simple keyword signals that indicate missing information in evidence text
_MISSING_INFO_SIGNALS = [
    r"\bno data\b", r"\bnot available\b", r"\bunavailable\b",
    r"\bfurther research needed\b", r"\blimited evidence\b",
    r"\binsufficient data\b", r"\bmore studies needed\b",
    r"\bunclear\b", r"\bunknown\b", r"\bnot yet studied\b",
]
_MISSING_PATTERN = re.compile("|".join(_MISSING_INFO_SIGNALS), re.IGNORECASE)

# Contradiction signals
_CONTRADICTION_SIGNALS = [
    r"\bcontradicts\b", r"\bconflicts with\b", r"\bdisputed\b",
    r"\bdiscrepancy\b", r"\binconsistent\b", r"\bnot supported by\b",
    r"\brefuted\b", r"\bcontroversial\b",
]
_CONTRADICTION_PATTERN = re.compile("|".join(_CONTRADICTION_SIGNALS), re.IGNORECASE)


def detect_information_gaps(
    evidence: List[Evidence],
    existing_task_queries: Set[str],
) -> List[str]:
    """
    Scan evidence for signals that important information is missing.
    Returns a list of suggested follow-up queries (deduplicated against existing tasks).

    Args:
        evidence:              Evidence items collected so far.
        existing_task_queries: Set of query strings already planned / executed.

    Returns:
        List of new query strings that should be investigated.
    """
    gap_queries: List[str] = []

    for ev in evidence:
        text = (ev.claim or "") + " " + (ev.context or "")
        if not _MISSING_PATTERN.search(text):
            continue

        # Build a targeted follow-up query from the claim context
        # Strip the generic words and use the noun phrase
        follow_up = _build_gap_query(ev)
        if follow_up and follow_up.lower() not in {q.lower() for q in existing_task_queries}:
            gap_queries.append(follow_up)
            logger.debug(f"[AdaptiveLoop] Gap detected in evidence → follow-up: '{follow_up}'")

    return list(dict.fromkeys(gap_queries))  # deduplicate while preserving order


def detect_contradictions(evidence: List[Evidence]) -> List[Dict[str, Any]]:
    """
    Find pairs / groups of evidence that potentially contradict each other.

    Returns:
        List of contradiction records: {claim_a, claim_b, reason}
    """
    contradictions: List[Dict[str, Any]] = []

    for ev in evidence:
        text = (ev.claim or "") + " " + (ev.context or "")
        if _CONTRADICTION_PATTERN.search(text):
            contradictions.append({
                "evidence_id": ev.id,
                "claim": ev.claim,
                "signal": "contradiction keyword detected",
                "source_id": ev.source_id,
            })

    # Also detect numeric contradictions: same metric, wildly different values
    metric_claims: Dict[str, List[Evidence]] = {}
    for ev in evidence:
        for m in (ev.metrics or []):
            metric_claims.setdefault(m, []).append(ev)

    for metric, evs in metric_claims.items():
        if len(evs) >= 2:
            # Check if the claims for the same metric differ significantly
            conflicting = [
                e for e in evs
                if e.claim and any(
                    other.claim and other.claim != e.claim and other.source_id != e.source_id
                    for other in evs
                )
            ]
            if conflicting:
                contradictions.append({
                    "metric": metric,
                    "conflicting_claims": [e.claim for e in conflicting[:3]],
                    "signal": "same metric reported differently across sources",
                })

    return contradictions


# ---------------------------------------------------------------------------
# Adaptive task generator
# ---------------------------------------------------------------------------

def generate_adaptive_tasks(
    query: str,
    evidence: List[Evidence],
    sources: List[Source],
    existing_tasks: List[ResearchTask],
    max_new_tasks: int = 5,
) -> List[ResearchTask]:
    """
    Day 48 core: Given collected evidence and sources, decide if more research
    tasks should be spawned to fill gaps or resolve contradictions.

    Args:
        query:          Original research query.
        evidence:       Evidence collected so far.
        sources:        Sources collected so far.
        existing_tasks: Tasks already run or planned.
        max_new_tasks:  Cap on how many new tasks to generate.

    Returns:
        List of new ResearchTask objects (empty if no gaps found).
    """
    existing_queries = {t.query.lower() for t in existing_tasks}
    new_tasks: List[ResearchTask] = []

    # 1. Fill information gaps
    gap_queries = detect_information_gaps(evidence, existing_queries)
    for i, gap_q in enumerate(gap_queries):
        if len(new_tasks) >= max_new_tasks:
            break
        task = ResearchTask(
            id=f"adaptive_gap_{i + 1}",
            query=gap_q,
            question=f"Fill information gap: {gap_q}",
            category="web",
            depth=1,
        )
        new_tasks.append(task)
        logger.info(f"[AdaptiveLoop] ➕ New gap-fill task: '{gap_q}'")

    # 2. Create verification tasks for contradictions
    contradictions = detect_contradictions(evidence)
    for j, contradiction in enumerate(contradictions[:max_new_tasks]):
        if len(new_tasks) >= max_new_tasks:
            break

        metric = contradiction.get("metric") or contradiction.get("claim", "")
        verify_q = f"Verify and resolve conflicting information about: {metric} — {query}"
        if verify_q.lower() in existing_queries:
            continue

        task = ResearchTask(
            id=f"adaptive_verify_{j + 1}",
            query=verify_q,
            question=f"Resolve contradiction: {metric}",
            category="academic",
            depth=2,
        )
        new_tasks.append(task)
        logger.info(f"[AdaptiveLoop] 🔍 New verification task: '{verify_q[:80]}'")

    # 3. Source diversity gap: if no academic sources, add an academic task
    source_types = {getattr(s, "source_type", "web") for s in sources}
    if "academic" not in source_types and len(new_tasks) < max_new_tasks:
        academic_q = f"Academic research and peer-reviewed studies on: {query}"
        if academic_q.lower() not in existing_queries:
            new_tasks.append(ResearchTask(
                id="adaptive_academic_diversity",
                query=academic_q,
                question="Improve source diversity with academic literature",
                category="academic",
                depth=2,
            ))
            logger.info("[AdaptiveLoop] 📚 Adding academic diversity task")

    return new_tasks


def build_adaptive_loop_report(
    original_tasks: List[ResearchTask],
    adaptive_tasks: List[ResearchTask],
    contradictions: List[Dict[str, Any]],
    gaps_found: int,
) -> Dict[str, Any]:
    """Return a structured summary of the adaptive loop's decisions."""
    return {
        "original_task_count": len(original_tasks),
        "adaptive_task_count": len(adaptive_tasks),
        "gaps_detected": gaps_found,
        "contradictions_detected": len(contradictions),
        "adaptive_task_categories": {
            "gap_fill": sum(1 for t in adaptive_tasks if "gap" in t.id),
            "verification": sum(1 for t in adaptive_tasks if "verify" in t.id),
            "diversity": sum(1 for t in adaptive_tasks if "diversity" in t.id),
        },
        "total_tasks_executed": len(original_tasks) + len(adaptive_tasks),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_gap_query(ev: Evidence) -> str:
    """Extract a meaningful follow-up query from a gap-signalling evidence item."""
    claim = (ev.claim or "").strip()
    if not claim:
        return ""
    # Remove generic phrases and return a focused query
    for phrase in [
        "no data", "not available", "further research needed",
        "more studies needed", "unclear", "unknown",
    ]:
        claim = re.sub(phrase, "", claim, flags=re.IGNORECASE).strip()
    # Limit length
    return claim[:120].strip(" .,;") or ""


__all__ = [
    "detect_information_gaps",
    "detect_contradictions",
    "generate_adaptive_tasks",
    "build_adaptive_loop_report",
]
