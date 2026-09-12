"""
Research package providing orchestration, execution, citation, evidence extraction,
source credibility scoring, agent orchestration, adaptive research loop,
stopping criteria, and quality scoring.

Day 46 — Formalized agent orchestration (agent_orchestrator.py)
Day 47 — Dynamic planning integrated into PlannerAgent (agents/planner.py)
Day 48 — Adaptive research loop (adaptive_loop.py)
Day 49 — Research stopping criteria (stopping_criteria.py)
Day 50 — Research quality scoring (quality_scorer.py)
"""
from app.research.credibility import (
    SourceCredibilityScorer,
    source_credibility_scorer,
    credibility_scorer,
    CredibilityEvaluation,
)
from app.research.agent_orchestrator import (
    AgentRole,
    AgentInvocation,
    OrchestratorPlan,
    ResearchAgentOrchestrator,
    research_agent_orchestrator,
)
from app.research.adaptive_loop import (
    detect_information_gaps,
    detect_contradictions,
    generate_adaptive_tasks,
    build_adaptive_loop_report,
)
from app.research.stopping_criteria import (
    StoppingCriteriaResult,
    ResearchStoppingCriteria,
    research_stopping_criteria,
)
from app.research.quality_scorer import (
    QualityDimension,
    ResearchQualityScore,
    ResearchQualityScorer,
    research_quality_scorer,
)

__all__ = [
    # Day 1–45 existing
    "SourceCredibilityScorer",
    "source_credibility_scorer",
    "credibility_scorer",
    "CredibilityEvaluation",
    # Day 46 — Agent Orchestration
    "AgentRole",
    "AgentInvocation",
    "OrchestratorPlan",
    "ResearchAgentOrchestrator",
    "research_agent_orchestrator",
    # Day 48 — Adaptive Loop
    "detect_information_gaps",
    "detect_contradictions",
    "generate_adaptive_tasks",
    "build_adaptive_loop_report",
    # Day 49 — Stopping Criteria
    "StoppingCriteriaResult",
    "ResearchStoppingCriteria",
    "research_stopping_criteria",
    # Day 50 — Quality Scorer
    "QualityDimension",
    "ResearchQualityScore",
    "ResearchQualityScorer",
    "research_quality_scorer",
]

