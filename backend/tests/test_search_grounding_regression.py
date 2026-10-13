"""Offline regressions for live-search, planner, provider and grounding contracts."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.paper_agent import AcademicPaperAgent
from app.agents.planner import PlannerAgent
from app.agents.web_agent import DeepWebResearchAgent
from app.config.settings import settings
from app.database.models.source import Source
from app.llm.gemini import GeminiLLMProvider
from app.llm.openai import OpenAILLMProvider, get_llm_provider
from app.llm.provider import LLMUnavailableError, UnavailableLLMProvider
from app.llm.service import LLMService
from app.research.evidence import evidence_extractor
from app.search import web_search as web_search_module
from app.search.academic_search import AcademicSearchEngine
from app.search.news_search import NewsSearchEngine
from app.search.web_search import WebSearchEngine


@pytest.mark.asyncio
async def test_live_search_failure_returns_empty_without_manufactured_sources(monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(settings, "SERPER_API_KEY", "")

    web = WebSearchEngine()
    monkeypatch.setattr(web, "_wikipedia_search", AsyncMock(return_value=[]))

    class BrokenDDGS:
        def __enter__(self):
            raise RuntimeError("offline")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(web_search_module, "DDGS", BrokenDDGS)
    assert await web.search("Mars sample return mission", max_results=3) == []

    news = NewsSearchEngine()
    monkeypatch.setattr(news, "_google_news_rss", AsyncMock(return_value=[]))
    monkeypatch.setattr(web_search_module, "DDGS", BrokenDDGS)
    # Patch the news module's imported class as well; no network is used.
    import app.search.news_search as news_module
    monkeypatch.setattr(news_module, "DDGS", BrokenDDGS)
    assert await news.search("Mars sample return mission", max_results=3) == []


@pytest.mark.asyncio
async def test_blocking_ddgs_is_time_bounded(monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(settings, "SERPER_API_KEY", "")
    monkeypatch.setattr(web_search_module, "DDG_TIMEOUT_SECONDS", 0.01)

    class SlowDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def text(self, *args, **kwargs):
            time.sleep(0.15)
            return []

    monkeypatch.setattr(web_search_module, "DDGS", SlowDDGS)
    web = WebSearchEngine()
    monkeypatch.setattr(web, "_wikipedia_search", AsyncMock(return_value=[]))

    started = time.perf_counter()
    assert await web.search("bounded query", max_results=1) == []
    assert time.perf_counter() - started < 0.10


@pytest.mark.asyncio
async def test_planner_respects_requested_categories_and_query_on_fallback():
    # Explicit provider selection with no key gives a deterministic planner
    # fallback; no network or canned mock plan is involved.
    agent = PlannerAgent(provider_type="openrouter")
    plan = await agent.create_plan(
        "What are the launch constraints of the Mars sample return mission?",
        depth=1,
        breadth=4,
        categories=["academic", "web"],
    )

    assert plan.tasks
    assert {task.category for task in plan.tasks} <= {"academic", "web"}
    assert {task.category for task in plan.tasks} == {"academic", "web"}
    assert all("mars" in f"{task.question} {task.query}".lower() for task in plan.tasks)
    assert all("indian ev" not in task.query.lower() for task in plan.tasks)
    assert "categories" in plan.metadata


@pytest.mark.asyncio
async def test_provider_failure_does_not_return_canned_factual_output():
    unavailable = UnavailableLLMProvider("provider unavailable")
    with pytest.raises(LLMUnavailableError):
        await unavailable.generate_text("What is unrelated topic X?")

    with patch.object(settings, "OPENAI_API_KEY", ""):
        with pytest.raises(LLMUnavailableError):
            await OpenAILLMProvider(api_key=None).generate_text("Any query")

    assert isinstance(get_llm_provider(provider_type="openrouter"), UnavailableLLMProvider) or settings.OPENROUTER_API_KEY


def test_gemini_provider_selection_preserves_configured_model(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "configured-for-test")
    provider = get_llm_provider(provider_type="gemini")
    assert isinstance(provider, GeminiLLMProvider)
    assert provider.model == settings.GEMINI_MODEL


@pytest.mark.asyncio
async def test_academic_metadata_only_record_never_becomes_evidence():
    agent = AcademicPaperAgent(download_pdfs=False)
    source = await agent._enrich_paper(
        {
            "url": "https://arxiv.org/abs/1234.5678",
            "title": "A metadata-only paper",
            "authors": ["A. Researcher"],
            "source": "arxiv",
        },
        "run-metadata-only",
    )

    assert source is not None
    assert source.metadata["content_provenance"] == "metadata-only"
    assert source.metadata["evidence_eligible"] is False
    assert "Academic paper:" not in source.content
    assert evidence_extractor.extract_evidence(source) == []


@pytest.mark.asyncio
async def test_llm_invented_quote_is_rejected_and_heuristic_quote_is_traceable():
    source = Source(
        source_id="src-grounded",
        research_id="run-grounded",
        url="https://nasa.gov/mars/sample-return",
        title="Mars sample return update",
        content="The mission schedule changed in 2025 after testing identified a 12% mass increase.",
    )
    fake_llm = MagicMock()
    fake_llm.execute_prompt = AsyncMock(
        return_value=json.dumps(
            {
                "claims": [
                    {
                        "claim": "The mission has a fabricated 99% success rate.",
                        "evidence": "This sentence does not occur in the source.",
                        "confidence": 0.99,
                    }
                ]
            }
        )
    )
    fake_llm.provider = UnavailableLLMProvider("test double")

    with patch("app.research.evidence.get_llm_service", return_value=fake_llm):
        evidence = await evidence_extractor.extract_evidence_async(
            source,
            research_id="run-grounded",
            use_llm=True,
        )

    assert evidence
    assert all("fabricated" not in item.claim for item in evidence)
    assert all(item.quote.lower() in source.content.lower() for item in evidence)
    assert all(item.metadata["quote_validated"] is True for item in evidence)
    assert all(item.metadata["llm_success"] is False for item in evidence)


@pytest.mark.asyncio
async def test_fact_checker_cannot_upgrade_claim_without_supporting_evidence():
    from app.agents.fact_checker import FactCheckerAgent

    agent = FactCheckerAgent()
    with patch.object(
        agent.llm,
        "execute_prompt",
        new=AsyncMock(
            return_value=json.dumps(
                {
                    "supported": True,
                    "confidence": 0.99,
                    "sources": ["https://invented.example/source"],
                    "reasoning": "It is verified.",
                }
            )
        ),
    ):
        result = await agent.fact_check_claim(
            "A claim with no evidence",
            evidence_pool=[],
            use_llm=True,
        )

    assert result.supported is False
    assert result.sources == []
    assert result.metadata["llm_attempted"] is True
    assert result.metadata["llm_provider"] != "gemini"


@pytest.mark.asyncio
async def test_academic_provider_calls_are_bounded(monkeypatch):
    engine = AcademicSearchEngine()
    monkeypatch.setattr("app.search.academic_search.ACADEMIC_PROVIDER_TIMEOUT_SECONDS", 0.01)

    async def slow_search(*args, **kwargs):
        await asyncio.sleep(0.1)
        return []

    engine.arxiv.search = slow_search
    engine.semantic_scholar.search = slow_search
    engine.crossref.search = slow_search
    engine.pubmed.search = slow_search

    started = time.perf_counter()
    assert await engine.search("bounded academic query", max_results=4) == []
    assert time.perf_counter() - started < 0.10


@pytest.mark.asyncio
async def test_web_source_keeps_provider_and_content_provenance():
    agent = DeepWebResearchAgent(max_concurrency=1)
    with patch(
        "app.search.query_generator.query_generator.generate_queries",
        new=AsyncMock(return_value=["climate policy evidence"]),
    ), patch(
        "app.search.web_search.web_search_engine.search",
        new=AsyncMock(
            return_value=[
                {
                    "title": "Climate policy evidence",
                    "url": "https://nasa.gov/climate/policy",
                    "snippet": "A source-backed climate policy finding.",
                    "engine": "serper",
                }
            ]
        ),
    ), patch(
        "app.scraping.extractor.content_extractor.extract_from_url",
        new=AsyncMock(
            return_value={
                "title": "Climate policy evidence",
                "text": "The source-backed climate policy finding was published in 2025.",
            }
        ),
    ):
        sources = await agent.execute(
            "climate policy evidence",
            "run-provenance",
            max_queries=1,
            top_k=1,
        )

    assert len(sources) == 1
    assert sources[0].metadata["search_provider"] == "serper"
    assert sources[0].metadata["content_provenance"] == "fetched"
    assert sources[0].metadata["evidence_eligible"] is True
