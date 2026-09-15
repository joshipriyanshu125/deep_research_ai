"""
Tests for DAY 82–84 — Multi-Model Architecture
Tests the Model Router:
- Simple extraction -> Cheap model
- Complex planning -> Reasoning model
- Large synthesis -> Powerful model
- Selection based on: task complexity, cost, latency, availability/fallbacks.
"""

import pytest
from app.llm.router import (
    ModelRouter,
    ModelProfile,
    ModelTier,
    TaskComplexity,
    RoutingStrategy,
    model_router
)
from app.llm.service import LLMService, llm_service
from app.llm.provider import MockLLMProvider


@pytest.fixture(autouse=True)
def reset_router_health():
    model_router.reset_health()
    yield
    model_router.reset_health()


def test_task_complexity_classification():
    router = ModelRouter()

    # 1. Simple Extraction
    extraction_prompt = "Extract entities and key metrics into a json object from the text."
    c1 = router.analyze_complexity(extraction_prompt)
    assert c1 == TaskComplexity.SIMPLE_EXTRACTION

    # 2. Complex Planning
    planning_prompt = "Decompose the research goal into sub-questions and structured search strategy subtasks."
    c2 = router.analyze_complexity(planning_prompt)
    assert c2 == TaskComplexity.COMPLEX_PLANNING

    # 3. Large Synthesis
    synthesis_prompt = "Synthesize a comprehensive research report with executive summary, citations, and analysis."
    c3 = router.analyze_complexity(synthesis_prompt)
    assert c3 == TaskComplexity.LARGE_SYNTHESIS

    # 4. Fact Checking
    fact_prompt = "Verify claim against evidence and detect any contradiction."
    c4 = router.analyze_complexity(fact_prompt)
    assert c4 == TaskComplexity.FACT_CHECKING


def test_model_selection_by_complexity_tier():
    router = ModelRouter()

    # Simple Extraction -> Cheap tier model (gpt-4o-mini, gemini-1.5-flash, claude-3-haiku)
    d_extract = router.route("Extract key metrics and parse json")
    assert d_extract.complexity == TaskComplexity.SIMPLE_EXTRACTION
    assert d_extract.tier == ModelTier.CHEAP
    assert d_extract.selected_model in ["gpt-4o-mini", "gemini-1.5-flash", "claude-3-haiku", "mock-llm"]

    # Complex Planning -> Reasoning tier model (o3-mini, deepseek-r1, o1)
    d_plan = router.route("Decompose the research goal into sub-questions and dependencies")
    assert d_plan.complexity == TaskComplexity.COMPLEX_PLANNING
    assert d_plan.tier == ModelTier.REASONING
    assert d_plan.selected_model in ["o3-mini", "deepseek-r1", "o1"]

    # Large Synthesis -> Powerful tier model (gpt-4o, claude-3-5-sonnet, gemini-1.5-pro)
    d_synth = router.route("Synthesize a comprehensive research report with deep analysis and executive summary")
    assert d_synth.complexity == TaskComplexity.LARGE_SYNTHESIS
    assert d_synth.tier == ModelTier.POWERFUL
    assert d_synth.selected_model in ["gpt-4o", "claude-3-5-sonnet", "gemini-1.5-pro"]


def test_routing_by_strategy_cost_and_latency():
    router = ModelRouter()
    prompt = "Analyze the fundamental principles of artificial intelligence."

    # Cost-minimized strategy should select cheap tier
    d_cost = router.route(prompt, strategy=RoutingStrategy.COST_MINIMIZED)
    assert d_cost.tier == ModelTier.CHEAP
    assert d_cost.estimated_cost_usd < 0.005

    # Lowest-latency strategy should prioritize fast response models
    d_lat = router.route(prompt, strategy=RoutingStrategy.LOWEST_LATENCY)
    assert d_lat.expected_latency_ms <= 500.0

    # Max-quality strategy should select powerful or reasoning models
    d_qual = router.route(prompt, strategy=RoutingStrategy.MAX_QUALITY)
    assert d_qual.tier in [ModelTier.POWERFUL, ModelTier.REASONING]


def test_router_fallback_and_circuit_breaker():
    router = ModelRouter()
    prompt = "Decompose research plan into subtasks"

    # Primary reasoning model
    d1 = router.route(prompt)
    primary_model = d1.selected_model

    # Simulate 3 failures to trip circuit breaker
    router.record_failure(primary_model, error="503 Service Unavailable")
    router.record_failure(primary_model, error="503 Service Unavailable")
    router.record_failure(primary_model, error="503 Service Unavailable")

    profile = router.get_model_profile(primary_model)
    assert profile.is_available() is False
    assert profile.consecutive_failures == 3
    assert profile.circuit_open_until is not None

    # Routing again should now avoid the failed model and select the fallback
    d2 = router.route(prompt)
    assert d2.selected_model != primary_model


@pytest.mark.asyncio
async def test_llm_service_routed_execution():
    custom_service = LLMService(provider=MockLLMProvider())

    # 1. Text generation with router
    result, decision = await custom_service.generate_routed(
        prompt="Synthesize a comprehensive research report on autonomous robotics.",
        task_hint="synthesis"
    )

    assert result is not None
    assert len(result) > 20
    assert decision.complexity == TaskComplexity.LARGE_SYNTHESIS
    assert decision.tier == ModelTier.POWERFUL
    assert len(decision.fallback_chain) > 0

    # 2. JSON generation with router
    json_res, json_decision = await custom_service.generate_json_routed(
        prompt="Extract entities: Apple, Microsoft, Google into json",
        task_hint="extraction"
    )

    assert json_res is not None
    assert json_decision.complexity == TaskComplexity.SIMPLE_EXTRACTION
    assert json_decision.tier == ModelTier.CHEAP
