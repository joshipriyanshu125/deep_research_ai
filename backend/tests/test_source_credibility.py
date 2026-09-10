import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.database.models.source import Source, SourceType
from app.research.credibility import (
    SourceCredibilityScorer,
    source_credibility_scorer,
    CredibilityEvaluation,
)
from app.agents.web_agent import DeepWebResearchAgent


class TestAuthorityScoring:
    def test_government_authority(self):
        scorer = SourceCredibilityScorer()
        src = Source(
            research_id="res-1",
            url="https://niti.gov.in/report/ev-2026",
            title="NITI Aayog EV Framework",
            content="Official government policy report on national battery manufacturing.",
            source_type=SourceType.GOVERNMENT,
            publication_date="2026-01-15",
        )
        eval_res = scorer.evaluate_source(src, question="India EV policy")
        assert eval_res.authority_score >= 0.95
        assert eval_res.tier == "very_high"

    def test_academic_authority(self):
        scorer = SourceCredibilityScorer()
        src = Source(
            research_id="res-2",
            url="https://arxiv.org/abs/2601.12345",
            title="Empirical Benchmarks for Solid-State Lithium Batteries",
            content="Peer-reviewed experimental methodology investigating electrode degradation.",
            source_type=SourceType.ACADEMIC,
            publication_date="2026-02-01",
        )
        eval_res = scorer.evaluate_source(src, question="Solid-state battery research")
        assert eval_res.authority_score >= 0.95
        assert eval_res.tier == "very_high"

    def test_major_news_authority(self):
        scorer = SourceCredibilityScorer()
        src = Source(
            research_id="res-3",
            url="https://reuters.com/business/markets/ev-sales-surge",
            title="Reuters Market Report",
            content="EV sales surge across Asian markets reaching record quarterly volume.",
            source_type=SourceType.NEWS,
            publication_date="2026-03-01",
        )
        eval_res = scorer.evaluate_source(src, question="EV sales growth")
        assert eval_res.authority_score >= 0.85
        assert eval_res.tier in ("high", "very_high")

    def test_blog_authority(self):
        scorer = SourceCredibilityScorer()
        src = Source(
            research_id="res-4",
            url="https://medium.com/@enthusiast/my-thoughts-on-evs",
            title="Why I Think Electric Cars Are Cool",
            content="Personal opinion blog about owning an electric scooter in Mumbai.",
            source_type=SourceType.BLOG,
            publication_date="2026-01-01",
        )
        eval_res = scorer.evaluate_source(src, question="Electric scooters in Mumbai")
        assert eval_res.authority_score <= 0.65
        assert eval_res.tier in ("medium", "medium_high")

    def test_forum_social_authority(self):
        scorer = SourceCredibilityScorer()
        src = Source(
            research_id="res-5",
            url="https://reddit.com/r/electricvehicles/comments/xyz",
            title="Anyone having battery issues?",
            content="Anonymous user asking about vehicle range during winter.",
            source_type=SourceType.FORUM,
            publication_date="2026-02-10",
        )
        eval_res = scorer.evaluate_source(src, question="Battery issues")
        assert eval_res.authority_score <= 0.35
        assert eval_res.tier == "low"


class TestRecencyScoring:
    def test_recent_publication_scores_high(self):
        scorer = SourceCredibilityScorer()
        src_recent = Source(
            research_id="res-rec",
            url="https://site.org/doc",
            title="Recent Doc",
            publication_date="2026-02-15",
        )
        eval_recent = scorer.evaluate_source(src_recent)
        assert eval_recent.recency_score == 1.0

    def test_older_publication_decays(self):
        scorer = SourceCredibilityScorer()
        src_old = Source(
            research_id="res-rec",
            url="https://site.org/doc",
            title="Old Doc",
            publication_date="2018-05-10",
        )
        eval_old = scorer.evaluate_source(src_old)
        assert eval_old.recency_score <= 0.50


class TestSpecificityAndPrimarySource:
    def test_high_quantitative_density(self):
        scorer = SourceCredibilityScorer()
        dense_content = (
            "The market reached $15.4B in revenue in 2026 with a CAGR of 28.5%. "
            "Subsidies of ₹10,000 crore funded 1,200,000 electric two-wheelers and 50,000 commercial buses. "
            "Battery pack prices fell to $85/kWh while energy density reached 450 Wh/kg."
        )
        src = Source(
            research_id="res-spec",
            url="https://statista.com/reports/ev-stats",
            title="Quantitative EV Market Metrics",
            content=dense_content,
            source_type=SourceType.COMPANY,
            publication_date="2026-02-01",
        )
        eval_res = scorer.evaluate_source(src, question="EV market revenue and battery pack prices")
        assert eval_res.specificity_score >= 0.85
        assert any("quantitative" in s.lower() for s in eval_res.signals)

    def test_primary_source_indicators(self):
        scorer = SourceCredibilityScorer()
        src = Source(
            research_id="res-prim",
            url="https://pib.gov.in/gazette/ev-2026",
            title="Gazette Notification: EV Subsidies",
            content="Official gazette notification published by the Ministry of Heavy Industries.",
            source_type=SourceType.GOVERNMENT,
            publication_date="2026-01-20",
        )
        eval_res = scorer.evaluate_source(src)
        assert eval_res.primary_source_score >= 0.90


class TestCrossSourceAgreementAndBatch:
    def test_evaluate_batch_corroboration(self):
        scorer = SourceCredibilityScorer()
        q = "Indian electric vehicle sales and manufacturing"

        sources = [
            Source(
                research_id="batch-1",
                url="https://pib.gov.in/report1",
                title="Government EV Initiative",
                content="Indian electric vehicle sales exceeded 2 million units in 2026 under national manufacturing subsidies.",
                source_type=SourceType.GOVERNMENT,
                publication_date="2026-01-10",
            ),
            Source(
                research_id="batch-1",
                url="https://reuters.com/news/ev-india",
                title="Reuters: Indian Electric Vehicle Sales Record",
                content="Indian electric vehicle sales topped 2 million units in 2026 as manufacturing expanded rapidly.",
                source_type=SourceType.NEWS,
                publication_date="2026-01-15",
            ),
            Source(
                research_id="batch-1",
                url="https://forum.com/thread/1",
                title="Random thread",
                content="Nothing relevant here.",
                source_type=SourceType.FORUM,
                publication_date="2026-01-01",
            ),
        ]

        evaluated_sources = scorer.evaluate_batch(sources, question=q)
        assert len(evaluated_sources) == 3

        # First two corroborated sources should have higher credibility scores than the forum post
        assert evaluated_sources[0].credibility_score > evaluated_sources[2].credibility_score
        assert evaluated_sources[1].credibility_score > evaluated_sources[2].credibility_score
        assert "credibility_breakdown" in evaluated_sources[0].metadata
        assert "credibility_tier" in evaluated_sources[0].metadata
        assert evaluated_sources[0].metadata["credibility_tier"] in ("very_high", "high")


class TestWebAgentCredibilityIntegration:
    @pytest.mark.asyncio
    async def test_agent_attaches_credibility_breakdown(self):
        agent = DeepWebResearchAgent()

        mock_search_results = [
            {
                "title": "Government Release: India EV Infrastructure",
                "url": "https://niti.gov.in/ev-strategy",
                "snippet": "EV strategy reaching 30% penetration by 2030 with $5B investment.",
                "date": "2026-02-01",
            }
        ]

        mock_extraction = {
            "title": "NITI Aayog EV Strategy 2026",
            "text": "Official report: Electric vehicle adoption will reach 30% by 2030 backed by $5B capital expenditure and ₹10,000 crore incentives.",
            "author": "NITI Aayog",
            "date": "2026-02-01",
        }

        with patch("app.search.query_generator.query_generator.generate_queries", new_callable=AsyncMock) as mock_q, \
             patch("app.search.web_search.web_search_engine.search", new_callable=AsyncMock) as mock_s, \
             patch("app.scraping.extractor.content_extractor.extract_from_url", new_callable=AsyncMock) as mock_e:

            mock_q.return_value = ["India EV infrastructure 2026"]
            mock_s.return_value = mock_search_results
            mock_e.return_value = mock_extraction

            sources = await agent.execute("India EV infrastructure", "res-cred-test")
            assert len(sources) == 1
            s = sources[0]
            assert s.credibility_score >= 0.85
            assert "credibility_breakdown" in s.metadata
            assert s.metadata["credibility_tier"] in ("very_high", "high")
