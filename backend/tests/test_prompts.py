import pytest
from app.llm.prompts import (
    PromptConfig,
    PROMPT_REGISTRY,
    get_prompt,
    register_prompt,
    list_prompts,
    planner_prompt,
    research_prompt,
    source_evaluation_prompt,
    summarization_prompt,
    fact_check_prompt,
    citation_prompt,
    report_prompt,
    analyst_prompt,
    PLANNER_SYSTEM_PROMPT,
    FACT_CHECKER_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
    ANALYST_PROMPT,
)
from app.llm.service import LLMService
from app.llm.provider import MockLLMProvider


def test_required_prompts_exist_in_registry():
    expected_prompts = [
        "planner_prompt",
        "research_prompt",
        "source_evaluation_prompt",
        "summarization_prompt",
        "fact_check_prompt",
        "citation_prompt",
        "report_prompt",
        "analyst_prompt",
    ]
    for name in expected_prompts:
        prompt = get_prompt(name)
        assert isinstance(prompt, PromptConfig)
        assert prompt.name == name
        assert prompt.version is not None
        assert len(prompt.version) > 0
        assert isinstance(prompt.temperature, float)
        assert isinstance(prompt.max_tokens, int)
        assert prompt.max_tokens > 0
        assert len(prompt.system_prompt) > 0
        assert len(prompt.user_template) > 0


def test_prompt_attributes_and_defaults():
    # Planner
    assert planner_prompt.name == "planner_prompt"
    assert planner_prompt.version.startswith("1.")
    assert planner_prompt.temperature == 0.2
    assert planner_prompt.max_tokens == 2000

    # Research
    assert research_prompt.name == "research_prompt"
    assert research_prompt.version == "1.0.0"
    assert research_prompt.temperature == 0.5
    assert research_prompt.max_tokens == 3000

    # Source evaluation
    assert source_evaluation_prompt.name == "source_evaluation_prompt"
    assert source_evaluation_prompt.temperature == 0.2
    assert source_evaluation_prompt.max_tokens == 1500

    # Summarization
    assert summarization_prompt.name == "summarization_prompt"
    assert summarization_prompt.temperature == 0.3
    assert summarization_prompt.max_tokens == 2000

    # Fact check
    assert fact_check_prompt.name == "fact_check_prompt"
    assert fact_check_prompt.temperature == 0.1
    assert fact_check_prompt.max_tokens == 1500

    # Citation
    assert citation_prompt.name == "citation_prompt"
    assert citation_prompt.temperature == 0.2
    assert citation_prompt.max_tokens == 2000

    # Report
    assert report_prompt.name == "report_prompt"
    assert report_prompt.temperature == 0.7
    assert report_prompt.max_tokens == 4000


def test_prompt_formatting():
    formatted = planner_prompt.format_user_prompt(
        query="Quantum Computing",
        depth=2,
        breadth=3,
    )
    assert "Quantum Computing" in formatted
    assert "Depth level: 2" in formatted
    assert "Number of sub-tasks: 3" in formatted


def test_prompt_to_dict_and_list_prompts():
    all_prompts = list_prompts()
    assert "planner_prompt" in all_prompts
    assert "report_prompt" in all_prompts
    assert all_prompts["report_prompt"]["temperature"] == 0.7
    assert all_prompts["report_prompt"]["max_tokens"] == 4000


def test_custom_prompt_registration():
    custom = PromptConfig(
        name="custom_eval_prompt",
        version="2.0.0",
        system_prompt="System instructions",
        user_template="Template {item}",
        temperature=0.4,
        max_tokens=1200,
    )
    register_prompt(custom)
    retrieved = get_prompt("custom_eval_prompt")
    assert retrieved.name == "custom_eval_prompt"
    assert retrieved.version == "2.0.0"


def test_backward_compatibility_constants():
    assert PLANNER_SYSTEM_PROMPT == planner_prompt.system_prompt
    assert FACT_CHECKER_SYSTEM_PROMPT == fact_check_prompt.system_prompt
    assert SYNTHESIZER_SYSTEM_PROMPT == report_prompt.system_prompt
    assert ANALYST_PROMPT == analyst_prompt.system_prompt


@pytest.mark.asyncio
async def test_llm_service_execute_prompt_with_config():
    service = LLMService(provider=MockLLMProvider())
    result = await service.execute_prompt(
        planner_prompt,
        variables={"query": "AI Agents", "depth": 1, "breadth": 2},
        is_json=True,
    )
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_llm_service_execute_prompt_with_name():
    service = LLMService(provider=MockLLMProvider())
    result = await service.execute_prompt(
        "report_prompt",
        variables={"query": "Fusion Energy", "evidence_summary": "[1] High Q plasma output"},
    )
    assert isinstance(result, str)
    assert len(result) > 0
