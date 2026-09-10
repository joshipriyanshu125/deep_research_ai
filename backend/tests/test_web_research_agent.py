import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.search.query_generator import QueryGenerator, _extract_topic, _deduplicate
from app.search.result_ranker import ResultRanker, _tokenise, _keyword_overlap_score
from app.agents.web_agent import DeepWebResearchAgent, WebAgent, deep_web_research_agent
from app.database.models.source import Source, SourceType


class TestQueryGenerator:
    def test_extract_topic_question_cleaning(self):
        assert _extract_topic("What is the Indian EV market size?") == "Indian EV market size"
        assert _extract_topic("How does quantum computing work?") == "quantum computing work"
        assert _extract_topic("Explain the future of AI in healthcare") == "future of AI in healthcare"

    def test_deduplicate(self):
        queries = ["India EV market", "india ev market", "India EV sales", "India EV market "]
        deduped = _deduplicate(queries)
        assert len(deduped) == 2
        assert deduped == ["India EV market", "India EV sales"]

    @pytest.mark.asyncio
    async def test_template_fallback_web(self):
        gen = QueryGenerator()
        # Without LLM configured or on failure, falls back to templates
        queries = await gen.generate_queries("What is the Indian EV market?", n=6, category="web")
        assert len(queries) == 6
        assert any("market size" in q.lower() or "growth" in q.lower() for q in queries)
        assert all("indian ev market" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_template_fallback_market(self):
        gen = QueryGenerator()
        queries = await gen.generate_queries("Indian EV market", n=4, category="market")
        assert len(queries) == 4
        assert any("industry analysis" in q.lower() or "market share" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_template_fallback_academic(self):
        gen = QueryGenerator()
        queries = await gen.generate_queries("Deep Reinforcement Learning", n=3, category="academic")
        assert len(queries) == 3
        assert any("research" in q.lower() or "empirical" in q.lower() or "systematic" in q.lower() for q in queries)

    @pytest.mark.asyncio
    async def test_llm_query_generation(self):
        gen = QueryGenerator()
        mock_llm = MagicMock()
        mock_llm.execute_prompt = AsyncMock(return_value='["India EV market size 2026", "India EV policy", "Tata EV market share"]')

        with patch("app.llm.service.get_llm_service", return_value=mock_llm):
            queries = await gen.generate_queries("Indian EV market", n=3)
            assert len(queries) == 3
            assert "India EV market size 2026" in queries
            assert "Tata EV market share" in queries


class TestResultRanker:
    def test_tokenisation(self):
        tokens = _tokenise("What is the Indian EV market size in 2026?")
        assert "indian" in tokens
        assert "ev" in tokens
        assert "market" in tokens
        assert "size" in tokens
        assert "2026" in tokens
        assert "what" not in tokens
        assert "is" not in tokens

    def test_keyword_overlap_score(self):
        query_tokens = ["indian", "ev", "market"]
        score1 = _keyword_overlap_score(query_tokens, "The Indian EV market is growing fast")
        assert score1 == 1.0

        score2 = _keyword_overlap_score(query_tokens, "US electric vehicle trends")
        assert score2 == 0.0

    def test_domain_authority_bonus(self):
        ranker = ResultRanker()
        gov_score = ranker._domain_score("https://niti.gov.in/report/ev")
        edu_score = ranker._domain_score("https://mit.edu/paper")
        wiki_score = ranker._domain_score("https://en.wikipedia.org/wiki/Electric_vehicle")
        spam_score = ranker._domain_score("https://quora.com/what-is-ev")

        assert gov_score > wiki_score
        assert edu_score > wiki_score
        assert wiki_score > spam_score
        assert spam_score == 0.0

    def test_spam_detection(self):
        ranker = ResultRanker()
        results = [
            {
                "title": "Buy now free download casino forex",
                "url": "https://example.com/spam",
                "snippet": "click here for crypto trading",
            }
        ]
        ranked = ranker.rank("Indian EV market", results)
        assert len(ranked) == 1
        assert ranked[0]["relevance_score"] == 0.0

    def test_ranking_sort_order(self):
        ranker = ResultRanker()
        results = [
            {
                "title": "Random generic article",
                "url": "https://example.com/article",
                "snippet": "Something totally unrelated.",
            },
            {
                "title": "Comprehensive Guide to Indian EV Market Size and Growth",
                "url": "https://pib.gov.in/pressrelease/ev-market",
                "snippet": "Government policy report on the Indian EV market and sales expansion.",
            },
        ]
        ranked = ranker.rank("Indian EV market size", results)
        assert len(ranked) == 2
        assert ranked[0]["url"] == "https://pib.gov.in/pressrelease/ev-market"
        assert ranked[0]["relevance_score"] > ranked[1]["relevance_score"]

    def test_empty_results(self):
        ranker = ResultRanker()
        assert ranker.rank("test", []) == []


class TestDeepWebResearchAgent:
    @pytest.mark.asyncio
    async def test_full_pipeline_execution(self):
        agent = DeepWebResearchAgent()

        # Mock search engine
        mock_search_results = [
            {"title": "India EV Report 1", "url": "https://pib.gov.in/ev1", "snippet": "Detailed EV analysis in India"},
            {"title": "India EV Report 2", "url": "https://reuters.com/ev2", "snippet": "Market growth metrics for EV"},
        ]

        # Mock content extractor
        mock_extraction = {
            "title": "Detailed India EV Report",
            "text": "Full extracted article content discussing the booming Indian EV market in 2026.",
            "author": "Research Bureau",
            "date": "2026-02-15",
        }

        with patch("app.search.query_generator.query_generator.generate_queries", new_callable=AsyncMock) as mock_gen_q, \
             patch("app.search.web_search.web_search_engine.search", new_callable=AsyncMock) as mock_search, \
             patch("app.scraping.extractor.content_extractor.extract_from_url", new_callable=AsyncMock) as mock_ext:

            mock_gen_q.return_value = ["India EV market size 2026", "India EV policy"]
            mock_search.return_value = mock_search_results
            mock_ext.return_value = mock_extraction

            sources = await agent.execute(
                query="Indian EV market",
                research_id="res-test-123",
                is_market=False,
                max_queries=2,
                top_k=5,
            )

            assert len(sources) == 2
            assert all(isinstance(s, Source) for s in sources)
            assert sources[0].research_id == "res-test-123"
            assert sources[0].source_type == SourceType.WEB
            assert sources[0].author == "Research Bureau"
            assert "booming Indian EV market" in sources[0].clean_text
            assert "query_used" in sources[0].metadata
            assert sources[0].metadata["rank"] == 1

    @pytest.mark.asyncio
    async def test_deduplication_across_queries(self):
        agent = DeepWebResearchAgent()

        # Return identical URL for both queries
        shared_item = {"title": "Shared URL Item", "url": "https://example.com/same-url", "snippet": "Same snippet"}

        with patch("app.search.query_generator.query_generator.generate_queries", new_callable=AsyncMock) as mock_gen_q, \
             patch("app.search.web_search.web_search_engine.search", new_callable=AsyncMock) as mock_search, \
             patch("app.scraping.extractor.content_extractor.extract_from_url", new_callable=AsyncMock) as mock_ext:

            mock_gen_q.return_value = ["Query 1", "Query 2"]
            mock_search.return_value = [shared_item]
            mock_ext.return_value = {"title": "Extracted Title", "text": "Extracted Content"}

            sources = await agent.execute("Indian EV market", "res-123")
            # Should deduplicate to 1 source despite being returned by both queries
            assert len(sources) == 1
            assert sources[0].url == "https://example.com/same-url"

    @pytest.mark.asyncio
    async def test_is_market_routes_to_news_and_company_type(self):
        agent = DeepWebResearchAgent()

        with patch("app.search.query_generator.query_generator.generate_queries", new_callable=AsyncMock) as mock_gen_q, \
             patch("app.search.news_search.news_search_engine.search", new_callable=AsyncMock) as mock_news_search, \
             patch("app.scraping.extractor.content_extractor.extract_from_url", new_callable=AsyncMock) as mock_ext:

            mock_gen_q.return_value = ["Tata Motors EV revenue"]
            mock_news_search.return_value = [
                {"title": "Tata EV news", "url": "https://bloomberg.com/tata", "snippet": "Tata EV quarterly results"}
            ]
            mock_ext.return_value = {"title": "Tata News", "text": "Quarterly financials..."}

            sources = await agent.execute("Tata Motors EV", "res-market-1", is_market=True)
            assert len(sources) == 1
            assert sources[0].source_type == SourceType.COMPANY
            assert mock_news_search.called

    @pytest.mark.asyncio
    async def test_backward_compatibility_web_agent(self):
        # Verify WebAgent alias and singleton work seamlessly
        assert isinstance(deep_web_research_agent, DeepWebResearchAgent)
        agent = WebAgent()
        assert isinstance(agent, DeepWebResearchAgent)
