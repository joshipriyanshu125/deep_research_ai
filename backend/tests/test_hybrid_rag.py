"""
Day 25 — Hybrid RAG & Reranking Test Suite

Tests:
  - LexicalScorer: BM25 term frequency, stopword filtering, length normalization
  - SourceQualityScorer: academic boost, domain authority, spam penalties
  - RecencyScorer: exponential decay, multiple date formats, default fallback
  - ContextAlignmentScorer: alignment with overarching research topic
  - HybridReranker: weighted blending, score breakdowns, reranking logic
  - RAGRetriever.retrieve_hybrid: top-k candidate reranking, section filters
  - RAGPipeline: full question-answering, citation extraction, empty input handling
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.rag.reranker import (
    LexicalScorer,
    SourceQualityScorer,
    RecencyScorer,
    ContextAlignmentScorer,
    HybridReranker,
    hybrid_reranker,
    tokenize,
)
from app.rag.retriever import RAGRetriever, rag_retriever
from app.rag.pipeline import RAGPipeline, rag_pipeline, RAGResponse, RAGCitation
from app.rag.vector_store import vector_store
from app.llm.embeddings import embedding_service


# ---------------------------------------------------------------------------
# 1. Lexical Scorer Tests
# ---------------------------------------------------------------------------

class TestLexicalScorer:
    def test_tokenize_removes_stopwords(self):
        tokens = tokenize("The battery is charging into the station")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "battery" in tokens
        assert "charg" in tokens
        assert "station" in tokens

    def test_lexical_exact_match(self):
        scorer = LexicalScorer()
        score = scorer.score("solid state battery", "Our research focuses on solid state battery design.")
        assert score > 0.4

    def test_lexical_no_match(self):
        scorer = LexicalScorer()
        score = scorer.score("quantum computing cryptography", "Organic agriculture crop rotation methods.")
        assert score == 0.0

    def test_lexical_empty_query_or_doc(self):
        scorer = LexicalScorer()
        assert scorer.score("", "Some text") == 0.0
        assert scorer.score("query", "") == 0.0


# ---------------------------------------------------------------------------
# 2. Source Quality Scorer Tests
# ---------------------------------------------------------------------------

class TestSourceQualityScorer:
    def test_academic_source_highest_quality(self):
        scorer = SourceQualityScorer()
        doc = {"metadata": {"source_type": "academic", "url": "https://arxiv.org/abs/2401.123"}}
        assert scorer.score(doc) == 1.0

    def test_high_authority_domain(self):
        scorer = SourceQualityScorer()
        doc = {"metadata": {"url": "https://www.nature.com/articles/s41586-024-001"}}
        assert scorer.score(doc) == 0.95

    def test_government_domain(self):
        scorer = SourceQualityScorer()
        doc = {"metadata": {"url": "https://niti.gov.in/report-ev.pdf"}}
        assert scorer.score(doc) == 0.95

    def test_low_quality_domain_penalty(self):
        scorer = SourceQualityScorer()
        doc = {"metadata": {"url": "https://www.quora.com/What-is-EV-charging"}}
        assert scorer.score(doc) == 0.1

    def test_explicit_credibility_score(self):
        scorer = SourceQualityScorer()
        doc = {"metadata": {"credibility_score": 0.88}}
        assert scorer.score(doc) == 0.88


# ---------------------------------------------------------------------------
# 3. Recency Scorer Tests
# ---------------------------------------------------------------------------

class TestRecencyScorer:
    def test_recent_date_high_score(self):
        scorer = RecencyScorer(half_life_days=730.0)
        now = datetime(2026, 9, 11)
        doc = {"metadata": {"published_at": "2026-09-01"}}
        score = scorer.score(doc, current_date=now)
        assert score > 0.95

    def test_two_year_old_date_half_life(self):
        scorer = RecencyScorer(half_life_days=730.0)
        now = datetime(2026, 9, 11)
        two_years_ago = now - timedelta(days=730)
        doc = {"metadata": {"published_at": two_years_ago.strftime("%Y-%m-%d")}}
        score = scorer.score(doc, current_date=now)
        assert pytest.approx(score, rel=0.05) == 0.50

    def test_missing_date_fallback(self):
        scorer = RecencyScorer(default_score=0.5)
        doc = {"metadata": {}}
        assert scorer.score(doc) == 0.5

    def test_integer_year_parsing(self):
        scorer = RecencyScorer(half_life_days=730.0)
        now = datetime(2026, 9, 11)
        doc = {"metadata": {"year": 2026}}
        score = scorer.score(doc, current_date=now)
        assert score > 0.70


# ---------------------------------------------------------------------------
# 4. Context Alignment Scorer Tests
# ---------------------------------------------------------------------------

class TestContextAlignmentScorer:
    def test_matching_research_context(self):
        scorer = ContextAlignmentScorer()
        score = scorer.score(
            context="Electric vehicle battery cathode degradation analysis",
            chunk_text="Experimental degradation study on nickel-rich NMC cathode in EV battery pouch cells.",
        )
        assert score > 0.2

    def test_empty_research_context_returns_neutral(self):
        scorer = ContextAlignmentScorer()
        assert scorer.score(None, "Any chunk text") == 0.5
        assert scorer.score("", "Any chunk text") == 0.5


# ---------------------------------------------------------------------------
# 5. Hybrid Reranker Tests
# ---------------------------------------------------------------------------

class TestHybridReranker:
    def test_reranker_weights_normalization(self):
        reranker = HybridReranker(
            weight_semantic=4.0,
            weight_lexical=2.5,
            weight_quality=1.5,
            weight_recency=1.0,
            weight_context=1.0,
        )
        total = (
            reranker.w_sem
            + reranker.w_lex
            + reranker.w_qual
            + reranker.w_rec
            + reranker.w_ctx
        )
        assert pytest.approx(total) == 1.0

    def test_reranker_composite_score_breakdown(self):
        reranker = HybridReranker()
        candidates = [
            (
                {
                    "content": "Sodium-ion batteries offer an alternative to lithium-ion for grid energy storage.",
                    "document_id": "doc_na_ion",
                    "metadata": {"source_type": "academic", "published_at": "2026-01-01"},
                },
                0.85,
            )
        ]

        reranked = reranker.rerank(
            query="sodium-ion grid storage",
            candidates=candidates,
            research_context="Grid scale electrochemical energy storage",
            top_k=1,
        )

        assert len(reranked) == 1
        item = reranked[0]
        assert "hybrid_score" in item
        assert "score_breakdown" in item
        breakdown = item["score_breakdown"]
        assert "semantic" in breakdown
        assert "lexical" in breakdown
        assert "quality" in breakdown
        assert "recency" in breakdown
        assert "context" in breakdown
        assert item["hybrid_score"] > 0.5

    def test_high_quality_recent_outranks_noisy_semantic(self):
        reranker = HybridReranker(
            weight_semantic=0.30,
            weight_lexical=0.30,
            weight_quality=0.20,
            weight_recency=0.10,
            weight_context=0.10,
        )

        candidates = [
            # Candidate A: High semantic score, but spam domain, old, no keyword match
            (
                {
                    "content": "General electronics news and miscellaneous gadgets gadgetry.",
                    "document_id": "doc_spam",
                    "metadata": {"url": "https://quora.com/spam", "published_at": "2015-01-01"},
                },
                0.80,
            ),
            # Candidate B: Moderate semantic score, but high authority academic paper, recent, exact keyword match
            (
                {
                    "content": "Direct measurement of lithium dendrite growth rates in solid-state electrolytes.",
                    "document_id": "doc_academic",
                    "metadata": {"source_type": "academic", "url": "https://nature.com/article", "published_at": "2026-05-01"},
                },
                0.70,
            ),
        ]

        reranked = reranker.rerank(
            query="lithium dendrite growth solid-state electrolyte",
            candidates=candidates,
            research_context="Solid state battery safety and dendrite prevention",
            top_k=2,
        )

        # Candidate B should outrank Candidate A due to quality + lexical + recency + context
        assert reranked[0]["document_id"] == "doc_academic"


# ---------------------------------------------------------------------------
# 6. RAGRetriever Hybrid Integration Tests
# ---------------------------------------------------------------------------

class TestRAGRetrieverHybrid:
    @pytest.fixture(autouse=True)
    def clean_env(self):
        vector_store.clear()
        embedding_service.clear_cache()
        yield
        vector_store.clear()
        embedding_service.clear_cache()

    @pytest.mark.asyncio
    async def test_retrieve_hybrid_end_to_end(self):
        source = {
            "source_id": "paper_2026_dendrites",
            "url": "https://nature.com/energy/2026",
            "title": "Lithium Dendrite Prevention",
            "source_type": "academic",
            "metadata": {
                "published_at": "2026-02-15",
                "evidence_blocks": [
                    {
                        "page": 2,
                        "section": "Results",
                        "text": "Applying a 5 MPa stack pressure completely suppressed lithium dendrite penetration across 2000 hours.",
                    }
                ]
            }
        }

        retriever = RAGRetriever()
        await retriever.index_sources([source])

        results = await retriever.retrieve_hybrid(
            query="stack pressure suppress dendrite penetration",
            research_context="Solid-state battery safety engineering",
            top_k=1,
        )

        assert len(results) == 1
        top = results[0]
        assert top["page"] == 2
        assert top["section"] == "Results"
        assert top["hybrid_score"] > 0.5
        assert "score_breakdown" in top


# ---------------------------------------------------------------------------
# 7. Full RAG Pipeline Question Answering Tests
# ---------------------------------------------------------------------------

class TestRAGPipeline:
    @pytest.fixture(autouse=True)
    def clean_env(self):
        vector_store.clear()
        embedding_service.clear_cache()
        yield
        vector_store.clear()
        embedding_service.clear_cache()

    @pytest.mark.asyncio
    async def test_rag_pipeline_empty_question(self):
        pipeline = RAGPipeline()
        resp = await pipeline.answer("")
        assert resp.answer == "No question provided."
        assert resp.citations == []

    @pytest.mark.asyncio
    async def test_rag_pipeline_no_indexed_sources(self):
        pipeline = RAGPipeline()
        resp = await pipeline.answer("What is the efficiency of perovskite solar cells?")
        assert "No relevant evidence found" in resp.answer
        assert resp.citations == []

    @pytest.mark.asyncio
    async def test_rag_pipeline_answer_generation(self):
        source = {
            "source_id": "paper_perovskite_2026",
            "url": "https://science.org/perovskite-tandem",
            "title": "Perovskite-Silicon Tandem Solar Cells",
            "source_type": "academic",
            "metadata": {
                "published_at": "2026-04-10",
                "evidence_blocks": [
                    {
                        "page": 4,
                        "section": "Results",
                        "text": "The monolithic perovskite-silicon tandem cell achieved a certified power conversion efficiency of 33.9% under 1-sun illumination.",
                    }
                ]
            }
        }

        retriever = RAGRetriever()
        await retriever.index_sources([source])

        # Mock LLM to return grounded synthesis with citation [1]
        mock_llm = MagicMock()
        mock_llm.execute_prompt = AsyncMock(
            return_value="Monolithic perovskite-silicon tandem solar cells have achieved a certified power conversion efficiency of 33.9% [1]."
        )

        pipeline = RAGPipeline(retriever=retriever, llm=mock_llm)
        response: RAGResponse = await pipeline.answer(
            question="What is the power conversion efficiency of tandem perovskite cells?",
            research_context="Next generation photovoltaic efficiency milestones",
            top_k=1,
        )

        assert response.total_chunks_found == 1
        assert "33.9%" in response.answer
        assert len(response.citations) == 1
        citation = response.citations[0]
        assert citation.index == 1
        assert citation.page == 4
        assert citation.section == "Results"
        assert citation.title == "Perovskite-Silicon Tandem Solar Cells"
        assert citation.url == "https://science.org/perovskite-tandem"
