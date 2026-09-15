"""
Day 91–95 — Advanced Research Modes — Unit Tests

Pure unit tests: no DB, no LLM, no HTTP calls.
All assertions target the new research_modes module and the updated
ResearchRequest / ResearchJob models.
"""

import pytest
from app.research.research_modes import (
    ResearchMode,
    ResearchModeConfig,
    RESEARCH_MODE_CONFIGS,
    DEFAULT_MODE,
    get_mode_config,
    list_modes,
    validate_mode,
)
from app.database.models.research import ResearchRequest, ResearchJob


# ---------------------------------------------------------------------------
# 1. Mode registry — all four modes must exist
# ---------------------------------------------------------------------------

class TestResearchModeRegistry:
    def test_all_four_modes_defined(self):
        for mode in [ResearchMode.QUICK, ResearchMode.STANDARD, ResearchMode.DEEP, ResearchMode.EXPERT]:
            assert mode in RESEARCH_MODE_CONFIGS, f"Mode '{mode}' missing from RESEARCH_MODE_CONFIGS"

    def test_mode_constants_correct(self):
        assert ResearchMode.QUICK    == "quick"
        assert ResearchMode.STANDARD == "standard"
        assert ResearchMode.DEEP     == "deep"
        assert ResearchMode.EXPERT   == "expert"

    def test_all_list_contains_exactly_four(self):
        assert len(ResearchMode.ALL) == 4

    def test_default_mode_is_standard(self):
        assert DEFAULT_MODE == ResearchMode.STANDARD


# ---------------------------------------------------------------------------
# 2. get_mode_config — resolution & fallback
# ---------------------------------------------------------------------------

class TestGetModeConfig:
    def test_resolves_quick(self):
        cfg = get_mode_config("quick")
        assert cfg.mode == ResearchMode.QUICK

    def test_resolves_standard(self):
        cfg = get_mode_config("standard")
        assert cfg.mode == ResearchMode.STANDARD

    def test_resolves_deep(self):
        cfg = get_mode_config("deep")
        assert cfg.mode == ResearchMode.DEEP

    def test_resolves_expert(self):
        cfg = get_mode_config("expert")
        assert cfg.mode == ResearchMode.EXPERT

    def test_case_insensitive(self):
        assert get_mode_config("QUICK").mode  == "quick"
        assert get_mode_config("Expert").mode == "expert"
        assert get_mode_config("DEEP").mode   == "deep"

    def test_none_falls_back_to_standard(self):
        cfg = get_mode_config(None)
        assert cfg.mode == ResearchMode.STANDARD

    def test_unknown_mode_falls_back_to_standard(self):
        cfg = get_mode_config("turbo_max_ultra")
        assert cfg.mode == ResearchMode.STANDARD

    def test_empty_string_falls_back_to_standard(self):
        cfg = get_mode_config("   ")
        assert cfg.mode == ResearchMode.STANDARD


# ---------------------------------------------------------------------------
# 3. Source range validation
# ---------------------------------------------------------------------------

class TestSourceRanges:
    def test_quick_source_range(self):
        cfg = get_mode_config("quick")
        assert cfg.min_sources == 5
        assert cfg.max_sources == 10

    def test_standard_source_range(self):
        cfg = get_mode_config("standard")
        assert cfg.min_sources == 15
        assert cfg.max_sources == 30

    def test_deep_source_range(self):
        cfg = get_mode_config("deep")
        assert cfg.min_sources == 30
        assert cfg.max_sources == 100

    def test_expert_source_range(self):
        cfg = get_mode_config("expert")
        assert cfg.min_sources >= 100

    def test_increasing_min_sources(self):
        modes = [ResearchMode.QUICK, ResearchMode.STANDARD, ResearchMode.DEEP, ResearchMode.EXPERT]
        mins = [RESEARCH_MODE_CONFIGS[m].min_sources for m in modes]
        assert mins == sorted(mins), "min_sources should increase from quick → expert"


# ---------------------------------------------------------------------------
# 4. Depth / breadth constraints
# ---------------------------------------------------------------------------

class TestDepthBreadth:
    def test_quick_lowest_depth(self):
        assert get_mode_config("quick").depth == 1

    def test_quick_lowest_breadth(self):
        assert get_mode_config("quick").breadth == 2

    def test_expert_highest_depth(self):
        assert get_mode_config("expert").depth == 4

    def test_expert_highest_breadth(self):
        assert get_mode_config("expert").breadth == 7

    def test_depth_increases_monotonically(self):
        modes = [ResearchMode.QUICK, ResearchMode.STANDARD, ResearchMode.DEEP, ResearchMode.EXPERT]
        depths = [RESEARCH_MODE_CONFIGS[m].depth for m in modes]
        assert depths == sorted(depths)

    def test_breadth_increases_monotonically(self):
        modes = [ResearchMode.QUICK, ResearchMode.STANDARD, ResearchMode.DEEP, ResearchMode.EXPERT]
        breadths = [RESEARCH_MODE_CONFIGS[m].breadth for m in modes]
        assert breadths == sorted(breadths)


# ---------------------------------------------------------------------------
# 5. Feature flags — per spec
# ---------------------------------------------------------------------------

class TestFeatureFlags:
    # Quick — everything off
    def test_quick_no_fact_checking(self):
        assert get_mode_config("quick").enable_fact_checking is False

    def test_quick_no_cross_validation(self):
        assert get_mode_config("quick").enable_cross_validation is False

    def test_quick_no_multi_agent(self):
        assert get_mode_config("quick").enable_multi_agent is False

    def test_quick_no_contradiction_analysis(self):
        assert get_mode_config("quick").enable_contradiction_analysis is False

    def test_quick_no_multi_pass(self):
        assert get_mode_config("quick").enable_multi_pass is False

    def test_quick_single_pass(self):
        assert get_mode_config("quick").verification_passes == 1

    # Standard — fact-check only
    def test_standard_fact_checking_enabled(self):
        assert get_mode_config("standard").enable_fact_checking is True

    def test_standard_no_multi_agent(self):
        assert get_mode_config("standard").enable_multi_agent is False

    def test_standard_no_cross_validation(self):
        assert get_mode_config("standard").enable_cross_validation is False

    def test_standard_single_pass(self):
        assert get_mode_config("standard").verification_passes == 1

    # Deep — fact-check + multi-agent + cross-validation, 2 passes
    def test_deep_fact_checking(self):
        assert get_mode_config("deep").enable_fact_checking is True

    def test_deep_multi_agent(self):
        assert get_mode_config("deep").enable_multi_agent is True

    def test_deep_cross_validation(self):
        assert get_mode_config("deep").enable_cross_validation is True

    def test_deep_no_contradiction_analysis(self):
        assert get_mode_config("deep").enable_contradiction_analysis is False

    def test_deep_two_passes(self):
        assert get_mode_config("deep").verification_passes == 2

    # Expert — all on, 3 passes
    def test_expert_fact_checking(self):
        assert get_mode_config("expert").enable_fact_checking is True

    def test_expert_multi_agent(self):
        assert get_mode_config("expert").enable_multi_agent is True

    def test_expert_cross_validation(self):
        assert get_mode_config("expert").enable_cross_validation is True

    def test_expert_contradiction_analysis(self):
        assert get_mode_config("expert").enable_contradiction_analysis is True

    def test_expert_multi_pass(self):
        assert get_mode_config("expert").enable_multi_pass is True

    def test_expert_three_passes(self):
        assert get_mode_config("expert").verification_passes == 3

    def test_expert_financial_sources(self):
        assert get_mode_config("expert").enable_financial is True


# ---------------------------------------------------------------------------
# 6. Serialisation — to_dict
# ---------------------------------------------------------------------------

class TestModeConfigSerialization:
    def test_to_dict_has_required_keys(self):
        cfg = get_mode_config("deep")
        d = cfg.to_dict()
        for key in ("mode", "display_name", "description", "source_range",
                    "depth", "breadth", "features", "verification_passes",
                    "categories", "estimated_cost", "estimated_time"):
            assert key in d, f"Key '{key}' missing from to_dict() output"

    def test_to_dict_source_range_struct(self):
        d = get_mode_config("standard").to_dict()
        assert "min" in d["source_range"]
        assert "max" in d["source_range"]

    def test_to_dict_features_struct(self):
        d = get_mode_config("expert").to_dict()
        feats = d["features"]
        for flag in ("fact_checking", "cross_validation", "multi_agent",
                     "academic_sources", "financial_sources",
                     "contradiction_analysis", "multi_pass_verification"):
            assert flag in feats

    def test_quick_to_dict_fact_checking_false(self):
        d = get_mode_config("quick").to_dict()
        assert d["features"]["fact_checking"] is False

    def test_expert_to_dict_all_features_true(self):
        d = get_mode_config("expert").to_dict()
        for v in d["features"].values():
            assert v is True, "All expert features should be True"


# ---------------------------------------------------------------------------
# 7. list_modes helper
# ---------------------------------------------------------------------------

class TestListModes:
    def test_returns_four_items(self):
        modes = list_modes()
        assert len(modes) == 4

    def test_order_is_quick_standard_deep_expert(self):
        modes = list_modes()
        assert [m["mode"] for m in modes] == ["quick", "standard", "deep", "expert"]

    def test_all_items_are_dicts(self):
        for m in list_modes():
            assert isinstance(m, dict)


# ---------------------------------------------------------------------------
# 8. validate_mode helper
# ---------------------------------------------------------------------------

class TestValidateMode:
    def test_valid_modes(self):
        for mode in ["quick", "standard", "deep", "expert"]:
            assert validate_mode(mode) is True

    def test_invalid_mode(self):
        assert validate_mode("ultrafast") is False

    def test_case_insensitive_validation(self):
        assert validate_mode("EXPERT") is True


# ---------------------------------------------------------------------------
# 9. ResearchRequest model accepts research_mode field
# ---------------------------------------------------------------------------

class TestResearchRequestModel:
    def test_default_mode_is_standard(self):
        req = ResearchRequest(query="test query")
        assert req.research_mode == "standard"

    def test_set_quick_mode(self):
        req = ResearchRequest(query="test query", research_mode="quick")
        assert req.research_mode == "quick"

    def test_set_expert_mode(self):
        req = ResearchRequest(query="test query", research_mode="expert")
        assert req.research_mode == "expert"

    def test_depth_breadth_optional_none_by_default(self):
        req = ResearchRequest(query="test query")
        assert req.depth is None
        assert req.breadth is None

    def test_explicit_depth_overrides_mode(self):
        req = ResearchRequest(query="test query", research_mode="quick", depth=3)
        assert req.depth == 3

    def test_mode_none_accepted(self):
        req = ResearchRequest(query="test query", research_mode=None)
        assert req.research_mode is None


# ---------------------------------------------------------------------------
# 10. ResearchJob model carries research_mode field
# ---------------------------------------------------------------------------

class TestResearchJobModel:
    def test_default_mode_on_job(self):
        job = ResearchJob(query="test query")
        assert job.research_mode == "standard"

    def test_set_deep_mode_on_job(self):
        job = ResearchJob(query="test query", research_mode="deep")
        assert job.research_mode == "deep"

    def test_job_serialises_research_mode(self):
        job = ResearchJob(query="test query", research_mode="expert")
        d = job.model_dump(mode="json")
        assert d["research_mode"] == "expert"


# ---------------------------------------------------------------------------
# 11. Concurrency limits increase with mode complexity
# ---------------------------------------------------------------------------

class TestConcurrencyLimits:
    def test_quick_lowest_concurrency(self):
        assert get_mode_config("quick").max_concurrency == 4

    def test_expert_highest_concurrency(self):
        assert get_mode_config("expert").max_concurrency >= 12

    def test_concurrency_increases_monotonically(self):
        modes = [ResearchMode.QUICK, ResearchMode.STANDARD, ResearchMode.DEEP, ResearchMode.EXPERT]
        concurrencies = [RESEARCH_MODE_CONFIGS[m].max_concurrency for m in modes]
        assert concurrencies == sorted(concurrencies)


# ---------------------------------------------------------------------------
# 12. Categories
# ---------------------------------------------------------------------------

class TestCategories:
    def test_quick_web_only(self):
        cfg = get_mode_config("quick")
        assert cfg.categories == ["web"]

    def test_standard_includes_academic_and_market(self):
        cfg = get_mode_config("standard")
        assert "academic" in cfg.categories
        assert "market" in cfg.categories

    def test_expert_includes_financial(self):
        cfg = get_mode_config("expert")
        assert "financial" in cfg.categories
