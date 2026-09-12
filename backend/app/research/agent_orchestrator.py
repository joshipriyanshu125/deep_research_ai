"""
Day 46 — Formalized Agent Orchestration System

Defines the Research Orchestrator that manages a hierarchy of specialized agents:

Research Orchestrator
│
├── Planner Agent        — Decomposes query into tasks
├── Web Research Agent   — Searches and scrapes web sources
├── Academic Agent       — Searches academic databases (ArXiv, PubMed)
├── Data Agent           — Market/structured data gathering
├── Source Evaluation Agent — Credibility and diversity scoring
├── Evidence Agent       — Extracts atomic evidence from sources
├── Analysis Agent       — Pattern and theme analysis
├── Fact Checker         — Verifies and cross-checks claims
├── Citation Agent       — Builds citation graph and traceability
└── Report Agent         — Synthesizes final publication-grade report

The orchestrator decides:
  - which agent runs
  - when it runs
  - with what input / context
  - what output it produces
  - what happens on failure (retry / fallback)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from app.utils.logger import logger


# ---------------------------------------------------------------------------
# Agent Role Registry
# ---------------------------------------------------------------------------

class AgentRole(str, Enum):
    PLANNER = "planner"
    WEB_RESEARCH = "web_research"
    ACADEMIC = "academic"
    DATA = "data"
    SOURCE_EVALUATION = "source_evaluation"
    EVIDENCE = "evidence"
    ANALYSIS = "analysis"
    FACT_CHECKER = "fact_checker"
    CITATION = "citation"
    REPORT = "report"


# ---------------------------------------------------------------------------
# Agent Result / Execution record
# ---------------------------------------------------------------------------

@dataclass
class AgentInvocation:
    """Records a single agent call with its inputs, outputs and timing."""
    role: AgentRole
    input_summary: str
    output_summary: str = ""
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    retries: int = 0


@dataclass
class OrchestratorPlan:
    """
    Decides which agents will run, in what order, with what inputs.
    Each step lists the agent role, its input getter (callable) and
    optional failure handler.
    """

    @dataclass
    class Step:
        role: AgentRole
        description: str
        # Whether this step can be skipped on failure without aborting the pipeline
        optional: bool = False
        # Maximum retries on transient failure
        max_retries: int = 1

    steps: List["OrchestratorPlan.Step"] = field(default_factory=list)

    @classmethod
    def default_pipeline(cls) -> "OrchestratorPlan":
        """Standard deep-research pipeline covering all agent roles."""
        Step = cls.Step
        return cls(steps=[
            Step(AgentRole.PLANNER,          "Decompose query into research tasks",            optional=False),
            Step(AgentRole.WEB_RESEARCH,     "Search & scrape web sources",                   optional=False),
            Step(AgentRole.ACADEMIC,         "Search academic databases",                     optional=True),
            Step(AgentRole.DATA,             "Gather market / structured data",               optional=True),
            Step(AgentRole.SOURCE_EVALUATION,"Score source credibility and diversity",        optional=True),
            Step(AgentRole.EVIDENCE,         "Extract atomic evidence from sources",          optional=False),
            Step(AgentRole.ANALYSIS,         "Analyze patterns, themes, gaps",               optional=True),
            Step(AgentRole.FACT_CHECKER,     "Verify claims and detect contradictions",       optional=True),
            Step(AgentRole.CITATION,         "Build citation graph and traceability matrix",  optional=True),
            Step(AgentRole.REPORT,           "Synthesize final publication-grade report",     optional=False),
        ])

    @classmethod
    def minimal_pipeline(cls) -> "OrchestratorPlan":
        """Minimal pipeline for simple / fast queries (2-4 tasks)."""
        Step = cls.Step
        return cls(steps=[
            Step(AgentRole.PLANNER,      "Decompose query",           optional=False),
            Step(AgentRole.WEB_RESEARCH, "Search web sources",        optional=False),
            Step(AgentRole.EVIDENCE,     "Extract evidence",          optional=True),
            Step(AgentRole.REPORT,       "Write summary report",      optional=False),
        ])


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class ResearchAgentOrchestrator:
    """
    Day 46 — Formalized Research Agent Orchestrator.

    Manages the full lifecycle of a research pipeline:
      1. Selects which agents run and in which order based on query complexity.
      2. Tracks invocation history per job.
      3. Handles agent failures with retry / fallback logic.
      4. Exposes telemetry (which agent, when, duration, success/fail).
    """

    def __init__(self) -> None:
        # job_id -> list of invocations
        self._history: Dict[str, List[AgentInvocation]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_plan(self, query: str, estimated_tasks: int) -> OrchestratorPlan:
        """
        Choose pipeline depth based on query complexity.
        Simple queries (≤4 tasks) → minimal pipeline.
        Complex queries (>4 tasks) → full pipeline.
        """
        if estimated_tasks <= 4:
            logger.info(
                f"[Orchestrator] Query classified as SIMPLE ({estimated_tasks} tasks) → minimal pipeline"
            )
            return OrchestratorPlan.minimal_pipeline()

        logger.info(
            f"[Orchestrator] Query classified as COMPLEX ({estimated_tasks} tasks) → full pipeline"
        )
        return OrchestratorPlan.default_pipeline()

    async def run_agent(
        self,
        job_id: str,
        role: AgentRole,
        coro: Callable[[], Any],
        input_summary: str = "",
        max_retries: int = 1,
    ) -> Any:
        """
        Execute a single agent coroutine with retry logic and telemetry recording.

        Args:
            job_id:        Research job identifier for history tracking.
            role:          The agent role being invoked.
            coro:          Zero-arg async callable returning the agent's result.
            input_summary: Human-readable description of inputs (for history).
            max_retries:   Number of retry attempts on transient failure.

        Returns:
            Agent result on success, or None if all retries are exhausted.
        """
        invocation = AgentInvocation(
            role=role,
            input_summary=input_summary,
        )
        start = time.perf_counter()

        for attempt in range(max_retries + 1):
            try:
                result = await coro()
                invocation.duration_ms = round((time.perf_counter() - start) * 1000, 2)
                invocation.success = True
                invocation.output_summary = self._summarize(result)
                self._record(job_id, invocation)
                logger.info(
                    f"[Orchestrator] ✓ {role.value} completed in {invocation.duration_ms:.0f}ms"
                )
                return result
            except Exception as exc:
                invocation.retries = attempt
                logger.warning(
                    f"[Orchestrator] ✗ {role.value} attempt {attempt + 1}/{max_retries + 1} failed: {exc}"
                )
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))  # exponential back-off
                else:
                    invocation.duration_ms = round((time.perf_counter() - start) * 1000, 2)
                    invocation.success = False
                    invocation.error = str(exc)
                    self._record(job_id, invocation)
                    return None

    def get_history(self, job_id: str) -> List[AgentInvocation]:
        """Return the ordered list of agent invocations for a job."""
        return list(self._history.get(job_id, []))

    def get_pipeline_summary(self, job_id: str) -> Dict[str, Any]:
        """Return a structured summary of all agent calls for a job."""
        invocations = self.get_history(job_id)
        total_ms = sum(i.duration_ms for i in invocations)
        failed = [i for i in invocations if not i.success]
        return {
            "job_id": job_id,
            "total_agents_run": len(invocations),
            "total_duration_ms": round(total_ms, 2),
            "failed_agents": [i.role.value for i in failed],
            "agents": [
                {
                    "role": i.role.value,
                    "success": i.success,
                    "duration_ms": i.duration_ms,
                    "retries": i.retries,
                    "error": i.error,
                }
                for i in invocations
            ],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record(self, job_id: str, invocation: AgentInvocation) -> None:
        self._history.setdefault(job_id, []).append(invocation)

    @staticmethod
    def _summarize(result: Any) -> str:
        if result is None:
            return "None"
        if isinstance(result, list):
            return f"list[{len(result)}]"
        if isinstance(result, dict):
            return f"dict[{len(result)} keys]"
        return type(result).__name__


# Singleton
research_agent_orchestrator = ResearchAgentOrchestrator()

__all__ = [
    "AgentRole",
    "AgentInvocation",
    "OrchestratorPlan",
    "ResearchAgentOrchestrator",
    "research_agent_orchestrator",
]
