"""
Day 91–95 — Advanced Research Modes

Four configurable research modes that control depth, source limits, parallelism,
and feature flags for the research pipeline:

  quick    — 5–10  sources, fast, low cost, no fact-checking
  standard — 15–30 sources, web + papers, standard fact-checking
  deep     — 30–100 sources, multi-agent, cross-validation
  expert   — 100+ sources, primary + academic + financial, multi-pass,
             contradiction analysis, full verification

Each mode maps to a ResearchModeConfig that is resolved at job-creation time and
stored on ResearchJob.research_mode.  All pipeline logic gates off the config
flags rather than the raw mode string so new modes can be added without touching
the orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Mode constants — use these instead of bare strings
# ---------------------------------------------------------------------------

class ResearchMode:
    QUICK    = "quick"
    STANDARD = "standard"
    DEEP     = "deep"
    EXPERT   = "expert"

    ALL: List[str] = ["quick", "standard", "deep", "expert"]


# ---------------------------------------------------------------------------
# Per-mode configuration dataclass
# ---------------------------------------------------------------------------

@dataclass
class ResearchModeConfig:
    """
    All behavioural knobs for a single research mode.
    Pipeline code reads these flags instead of branching on the mode name.
    """

    # Human-readable identifiers
    mode: str
    display_name: str
    description: str

    # Source collection limits
    min_sources: int
    max_sources: int

    # Planner parameters (passed straight through to create_plan)
    depth: int
    breadth: int

    # Execution concurrency
    max_concurrency: int

    # --- Feature flags ---
    # Fact-checking agent pass
    enable_fact_checking: bool = True
    # Second synthesis pass that compares conclusions across evidence clusters
    enable_cross_validation: bool = False
    # Spawn multiple specialised agents (analyst, synthesiser, fact-checker) in parallel
    enable_multi_agent: bool = False
    # Pull from academic / paper search channels
    enable_academic: bool = True
    # Pull from financial data channels
    enable_financial: bool = False
    # Run a dedicated contradiction-detection sweep before final synthesis
    enable_contradiction_analysis: bool = False
    # Extra end-to-end verification loops after the first synthesis
    enable_multi_pass: bool = False

    # Number of full verification passes (1 = single pass, default pipeline)
    verification_passes: int = 1

    # Search categories forwarded to the planner / executor
    categories: List[str] = field(default_factory=lambda: ["web", "academic", "market"])

    # Informational cost estimate shown in UI
    estimated_cost_label: str = "low"

    # Estimated wall-time label shown in UI
    estimated_time_label: str = "fast"

    # ---------------------------------------------------------------------------
    def to_dict(self) -> Dict:
        """Serialise to a plain dict (JSON-safe)."""
        return {
            "mode":                      self.mode,
            "display_name":              self.display_name,
            "description":               self.description,
            "source_range":              {"min": self.min_sources, "max": self.max_sources},
            "depth":                     self.depth,
            "breadth":                   self.breadth,
            "max_concurrency":           self.max_concurrency,
            "features": {
                "fact_checking":         self.enable_fact_checking,
                "cross_validation":      self.enable_cross_validation,
                "multi_agent":           self.enable_multi_agent,
                "academic_sources":      self.enable_academic,
                "financial_sources":     self.enable_financial,
                "contradiction_analysis": self.enable_contradiction_analysis,
                "multi_pass_verification": self.enable_multi_pass,
            },
            "verification_passes":       self.verification_passes,
            "categories":                self.categories,
            "estimated_cost":            self.estimated_cost_label,
            "estimated_time":            self.estimated_time_label,
        }


# ---------------------------------------------------------------------------
# Mode registry — single source of truth for all four modes
# ---------------------------------------------------------------------------

RESEARCH_MODE_CONFIGS: Dict[str, ResearchModeConfig] = {

    ResearchMode.QUICK: ResearchModeConfig(
        mode                      = ResearchMode.QUICK,
        display_name              = "Quick Research",
        description               = (
            "Fast, lightweight research sweep across 5–10 web sources. "
            "Ideal for quick fact lookups and trend scanning. No fact-checking or "
            "academic papers."
        ),
        min_sources               = 5,
        max_sources               = 10,
        depth                     = 1,
        breadth                   = 2,
        max_concurrency           = 4,
        enable_fact_checking      = False,
        enable_cross_validation   = False,
        enable_multi_agent        = False,
        enable_academic           = False,
        enable_financial          = False,
        enable_contradiction_analysis = False,
        enable_multi_pass         = False,
        verification_passes       = 1,
        categories                = ["web"],
        estimated_cost_label      = "very low",
        estimated_time_label      = "< 30 seconds",
    ),

    ResearchMode.STANDARD: ResearchModeConfig(
        mode                      = ResearchMode.STANDARD,
        display_name              = "Standard Research",
        description               = (
            "Balanced research across 15–30 web and academic sources. "
            "Includes standard fact-checking. Suitable for most research tasks."
        ),
        min_sources               = 15,
        max_sources               = 30,
        depth                     = 2,
        breadth                   = 3,
        max_concurrency           = 6,
        enable_fact_checking      = True,
        enable_cross_validation   = False,
        enable_multi_agent        = False,
        enable_academic           = True,
        enable_financial          = False,
        enable_contradiction_analysis = False,
        enable_multi_pass         = False,
        verification_passes       = 1,
        categories                = ["web", "academic", "market"],
        estimated_cost_label      = "low",
        estimated_time_label      = "1–3 minutes",
    ),

    ResearchMode.DEEP: ResearchModeConfig(
        mode                      = ResearchMode.DEEP,
        display_name              = "Deep Research",
        description               = (
            "Comprehensive research across 30–100+ sources using multiple specialised "
            "agents operating in parallel. Includes fact-checking, cross-validation of "
            "conclusions across evidence clusters, and two verification passes."
        ),
        min_sources               = 30,
        max_sources               = 100,
        depth                     = 3,
        breadth                   = 5,
        max_concurrency           = 10,
        enable_fact_checking      = True,
        enable_cross_validation   = True,
        enable_multi_agent        = True,
        enable_academic           = True,
        enable_financial          = False,
        enable_contradiction_analysis = False,
        enable_multi_pass         = True,
        verification_passes       = 2,
        categories                = ["web", "academic", "market"],
        estimated_cost_label      = "medium",
        estimated_time_label      = "5–15 minutes",
    ),

    ResearchMode.EXPERT: ResearchModeConfig(
        mode                      = ResearchMode.EXPERT,
        display_name              = "Expert Research",
        description               = (
            "Exhaustive research across 100+ sources spanning web, primary academic "
            "literature, and financial data. Employs multi-agent orchestration, "
            "contradiction analysis, three verification passes, and cross-validation. "
            "Designed for high-stakes, publication-quality research."
        ),
        min_sources               = 100,
        max_sources               = 500,
        depth                     = 4,
        breadth                   = 7,
        max_concurrency           = 16,
        enable_fact_checking      = True,
        enable_cross_validation   = True,
        enable_multi_agent        = True,
        enable_academic           = True,
        enable_financial          = True,
        enable_contradiction_analysis = True,
        enable_multi_pass         = True,
        verification_passes       = 3,
        categories                = ["web", "academic", "market", "financial"],
        estimated_cost_label      = "high",
        estimated_time_label      = "15–60 minutes",
    ),
}

# Default when no mode is specified
DEFAULT_MODE = ResearchMode.STANDARD


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_mode_config(mode: Optional[str]) -> ResearchModeConfig:
    """
    Resolve a mode string to its ResearchModeConfig.

    Falls back to STANDARD for None or unrecognised mode strings so callers
    never have to guard against a missing config.

    Args:
        mode: One of "quick", "standard", "deep", "expert" (case-insensitive).

    Returns:
        The corresponding ResearchModeConfig.
    """
    if mode is None:
        return RESEARCH_MODE_CONFIGS[DEFAULT_MODE]
    normalised = mode.strip().lower()
    return RESEARCH_MODE_CONFIGS.get(normalised, RESEARCH_MODE_CONFIGS[DEFAULT_MODE])


def list_modes() -> List[Dict]:
    """Return all mode configs as JSON-serialisable dicts, ordered by complexity."""
    return [
        RESEARCH_MODE_CONFIGS[m].to_dict()
        for m in [ResearchMode.QUICK, ResearchMode.STANDARD, ResearchMode.DEEP, ResearchMode.EXPERT]
    ]


def validate_mode(mode: str) -> bool:
    """Return True if *mode* is a known research mode string."""
    return mode.strip().lower() in RESEARCH_MODE_CONFIGS
