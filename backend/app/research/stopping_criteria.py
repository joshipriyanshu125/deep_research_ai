"""
Day 49 — Research Stopping Criteria

Prevents infinite research loops by defining clear conditions under which
the adaptive research loop should stop generating new tasks.

Research stops when ALL of the following are satisfied:
  ✓ Required questions answered (task coverage)
  ✓ Sufficient evidence collected (evidence count threshold)
  ✓ Major claims verified (fact-check pass rate)
  ✓ Source diversity adequate (multiple source types)
  ✓ Confidence threshold reached (composite score)

If any criterion is unmet, the system may generate additional tasks
(up to a hard cap to prevent infinite loops).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.database.models.evidence import Evidence
from app.database.models.research import ResearchTask
from app.database.models.source import Source
from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Thresholds (tunable)
# ---------------------------------------------------------------------------

DEFAULT_MIN_EVIDENCE = 5          # Minimum evidence items
DEFAULT_MIN_SOURCES = 3           # Minimum unique sources
DEFAULT_MIN_SOURCE_TYPES = 2      # Minimum distinct source type categories
DEFAULT_CONFIDENCE_THRESHOLD = 0.55  # Minimum composite confidence score
DEFAULT_FACT_CHECK_PASS_RATE = 0.70  # ≥70% of checked claims must be supported
DEFAULT_MAX_ADAPTIVE_ROUNDS = 3   # Hard cap on adaptive loop iterations
DEFAULT_MAX_TOTAL_TASKS = 50      # Hard cap on total tasks (Day 47 upper bound)


# ---------------------------------------------------------------------------
# Stopping criteria result
# ---------------------------------------------------------------------------

@dataclass
class StoppingCriteriaResult:
    """Result of evaluating stopping criteria for a research session."""
    should_stop: bool
    reasons_to_stop: List[str] = field(default_factory=list)
    reasons_to_continue: List[str] = field(default_factory=list)
    criteria_scores: Dict[str, float] = field(default_factory=dict)
    overall_readiness: float = 0.0  # 0–1, fraction of criteria met

    def to_dict(self) -> Dict[str, Any]:
        return {
            "should_stop": self.should_stop,
            "overall_readiness": round(self.overall_readiness, 3),
            "reasons_to_stop": self.reasons_to_stop,
            "reasons_to_continue": self.reasons_to_continue,
            "criteria_scores": {k: round(v, 3) for k, v in self.criteria_scores.items()},
        }


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class ResearchStoppingCriteria:
    """
    Day 49 — Evaluates whether research should stop or continue.

    Usage::

        criteria = ResearchStoppingCriteria()
        result = criteria.evaluate(
            tasks=tasks,
            evidence=evidence,
            sources=sources,
            confidence_score=0.78,
            fact_checks=fact_check_results,
            adaptive_round=1,
        )
        if result.should_stop:
            # Finalize research
        else:
            # Generate more tasks
    """

    def __init__(
        self,
        min_evidence: int = DEFAULT_MIN_EVIDENCE,
        min_sources: int = DEFAULT_MIN_SOURCES,
        min_source_types: int = DEFAULT_MIN_SOURCE_TYPES,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        fact_check_pass_rate: float = DEFAULT_FACT_CHECK_PASS_RATE,
        max_adaptive_rounds: int = DEFAULT_MAX_ADAPTIVE_ROUNDS,
        max_total_tasks: int = DEFAULT_MAX_TOTAL_TASKS,
    ) -> None:
        self.min_evidence = min_evidence
        self.min_sources = min_sources
        self.min_source_types = min_source_types
        self.confidence_threshold = confidence_threshold
        self.fact_check_pass_rate = fact_check_pass_rate
        self.max_adaptive_rounds = max_adaptive_rounds
        self.max_total_tasks = max_total_tasks

    def evaluate(
        self,
        tasks: List[ResearchTask],
        evidence: List[Evidence],
        sources: List[Source],
        confidence_score: float = 0.0,
        fact_checks: Optional[List[Any]] = None,
        adaptive_round: int = 0,
    ) -> StoppingCriteriaResult:
        """
        Evaluate all stopping criteria and return a decision with reasoning.

        Args:
            tasks:            All tasks (original + adaptive) executed so far.
            evidence:         All evidence collected.
            sources:          All sources collected.
            confidence_score: Composite confidence from confidence.py.
            fact_checks:      List of FactCheckResult objects (optional).
            adaptive_round:   How many adaptive loops have already run.

        Returns:
            StoppingCriteriaResult with should_stop flag and detailed reasoning.
        """
        criteria_scores: Dict[str, float] = {}
        reasons_to_stop: List[str] = []
        reasons_to_continue: List[str] = []

        # ------------------------------------------------------------------
        # 1. Task coverage — are completed tasks sufficient?
        # ------------------------------------------------------------------
        completed = sum(1 for t in tasks if t.status == "completed")
        total_tasks = len(tasks)
        task_coverage = completed / max(1, total_tasks)
        criteria_scores["task_coverage"] = task_coverage

        if task_coverage >= 0.80:
            reasons_to_stop.append(
                f"Task coverage adequate: {completed}/{total_tasks} tasks completed ({task_coverage:.0%})"
            )
        else:
            reasons_to_continue.append(
                f"Only {completed}/{total_tasks} tasks completed ({task_coverage:.0%} coverage)"
            )

        # ------------------------------------------------------------------
        # 2. Evidence sufficiency
        # ------------------------------------------------------------------
        evidence_count = len(evidence)
        evidence_ok = evidence_count >= self.min_evidence
        criteria_scores["evidence_sufficiency"] = min(1.0, evidence_count / max(1, self.min_evidence))

        if evidence_ok:
            reasons_to_stop.append(f"Sufficient evidence: {evidence_count} items collected")
        else:
            reasons_to_continue.append(
                f"Insufficient evidence: {evidence_count}/{self.min_evidence} minimum"
            )

        # ------------------------------------------------------------------
        # 3. Source diversity
        # ------------------------------------------------------------------
        source_types = {
            getattr(s, "source_type", getattr(s, "type", "web")) for s in sources
        }
        type_count = len(source_types)
        diversity_ok = len(sources) >= self.min_sources and type_count >= self.min_source_types
        criteria_scores["source_diversity"] = min(
            1.0, (len(sources) / max(1, self.min_sources)) * 0.5
            + (type_count / max(1, self.min_source_types)) * 0.5
        )

        if diversity_ok:
            reasons_to_stop.append(
                f"Source diversity adequate: {len(sources)} sources, "
                f"{type_count} types ({', '.join(sorted(source_types))})"
            )
        else:
            reasons_to_continue.append(
                f"Source diversity insufficient: {len(sources)} sources, "
                f"{type_count}/{self.min_source_types} types"
            )

        # ------------------------------------------------------------------
        # 4. Fact-check pass rate
        # ------------------------------------------------------------------
        if fact_checks:
            supported = sum(1 for fc in fact_checks if getattr(fc, "supported", True))
            pass_rate = supported / max(1, len(fact_checks))
            fc_ok = pass_rate >= self.fact_check_pass_rate
            criteria_scores["fact_check_pass_rate"] = pass_rate
            if fc_ok:
                reasons_to_stop.append(
                    f"Fact-check pass rate adequate: {pass_rate:.0%} ({supported}/{len(fact_checks)})"
                )
            else:
                reasons_to_continue.append(
                    f"Fact-check pass rate low: {pass_rate:.0%} "
                    f"(need ≥{self.fact_check_pass_rate:.0%})"
                )
        else:
            # No fact checks yet — treat as neutral (0.6)
            criteria_scores["fact_check_pass_rate"] = 0.6
            fc_ok = True  # Don't block on missing fact checks

        # ------------------------------------------------------------------
        # 5. Confidence threshold
        # ------------------------------------------------------------------
        conf_ok = confidence_score >= self.confidence_threshold
        criteria_scores["confidence"] = confidence_score

        if conf_ok:
            reasons_to_stop.append(
                f"Confidence threshold met: {confidence_score:.2f} "
                f"(≥{self.confidence_threshold:.2f})"
            )
        else:
            reasons_to_continue.append(
                f"Confidence below threshold: {confidence_score:.2f} "
                f"(need ≥{self.confidence_threshold:.2f})"
            )

        # ------------------------------------------------------------------
        # 6. Hard caps — always stop to prevent runaway loops
        # ------------------------------------------------------------------
        hard_stop_reason: Optional[str] = None

        if adaptive_round >= self.max_adaptive_rounds:
            hard_stop_reason = (
                f"Maximum adaptive rounds reached ({adaptive_round}/{self.max_adaptive_rounds})"
            )
        if total_tasks >= self.max_total_tasks:
            hard_stop_reason = (
                f"Maximum total tasks reached ({total_tasks}/{self.max_total_tasks})"
            )

        # ------------------------------------------------------------------
        # Decision
        # ------------------------------------------------------------------
        criteria_met = sum([
            task_coverage >= 0.80,
            evidence_ok,
            diversity_ok,
            fc_ok,
            conf_ok,
        ])
        total_criteria = 5
        overall_readiness = criteria_met / total_criteria
        criteria_scores["overall_readiness"] = overall_readiness

        # Stop if: hard cap hit OR all soft criteria met
        should_stop = bool(hard_stop_reason) or (criteria_met == total_criteria)

        if hard_stop_reason:
            reasons_to_stop.append(f"⚠ Hard stop: {hard_stop_reason}")

        result = StoppingCriteriaResult(
            should_stop=should_stop,
            reasons_to_stop=reasons_to_stop,
            reasons_to_continue=reasons_to_continue,
            criteria_scores=criteria_scores,
            overall_readiness=overall_readiness,
        )

        logger.info(
            f"[StoppingCriteria] should_stop={should_stop} | "
            f"readiness={overall_readiness:.0%} | "
            f"criteria_met={criteria_met}/{total_criteria}"
        )
        return result

    def summary_line(self, result: StoppingCriteriaResult) -> str:
        """Return a one-line human-readable summary."""
        status = "✓ STOP" if result.should_stop else "↻ CONTINUE"
        return (
            f"{status} | Readiness: {result.overall_readiness:.0%} | "
            + " | ".join(f"{k}={v:.2f}" for k, v in result.criteria_scores.items())
        )


# Singleton
research_stopping_criteria = ResearchStoppingCriteria()

__all__ = [
    "StoppingCriteriaResult",
    "ResearchStoppingCriteria",
    "research_stopping_criteria",
    "DEFAULT_MIN_EVIDENCE",
    "DEFAULT_MIN_SOURCES",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "DEFAULT_FACT_CHECK_PASS_RATE",
    "DEFAULT_MAX_ADAPTIVE_ROUNDS",
    "DEFAULT_MAX_TOTAL_TASKS",
]
