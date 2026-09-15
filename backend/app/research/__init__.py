"""
Research package providing orchestration, execution, citation, evidence extraction,
source credibility scoring, agent orchestration, adaptive research loop,
stopping criteria, and quality scoring.

Day 46 — Formalized agent orchestration (agent_orchestrator.py)
Day 47 — Dynamic planning integrated into PlannerAgent (agents/planner.py)
Day 48 — Adaptive research loop (adaptive_loop.py)
Day 49 — Research stopping criteria (stopping_criteria.py)
Day 50 — Research quality scoring (quality_scorer.py)
Day 91–95 — Advanced research modes (research_modes.py)
"""
# Day 91–95 — Advanced Research Modes
from app.research.research_modes import (
    ResearchMode,
    ResearchModeConfig,
    RESEARCH_MODE_CONFIGS,
    DEFAULT_MODE,
    get_mode_config,
    list_modes,
    validate_mode,
)
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
from app.research.hallucination import (
    HallucinationDetector,
    HallucinationAuditItem,
    HallucinationAuditReport,
    hallucination_detector,
)
from app.research.citation_coverage import (
    CitationCoverageAuditor,
    CitationCoverageReport,
    citation_coverage_auditor,
)

__all__ = [
    # Day 91–95 — Advanced Research Modes
    "ResearchMode",
    "ResearchModeConfig",
    "RESEARCH_MODE_CONFIGS",
    "DEFAULT_MODE",
    "get_mode_config",
    "list_modes",
    "validate_mode",
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
    # Day 51 — Hallucination Detection
    "HallucinationDetector",
    "HallucinationAuditItem",
    "HallucinationAuditReport",
    "hallucination_detector",
    # Day 52 — Citation Coverage
    "CitationCoverageAuditor",
    "CitationCoverageReport",
    "citation_coverage_auditor",
]


