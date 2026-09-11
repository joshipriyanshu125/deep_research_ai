"""
Day 24 — Embeddings & Vector Store Test Suite

Tests:
  - EmbeddingService: dimension, unit normalization, reproducibility
  - Batch embedding: get_embeddings, batch_embed convenience helper
  - Caching: LRU cache hit, eviction, stats, clear_cache
  - Fallback logic: deterministic pseudo-embedding, dimension projection
  - VectorStore: add_documents, add_documents_batch, empty / whitespace docs
  - VectorStore Search: cosine similarity ranking, top_k, min_score
  - VectorStore Metadata Filtering: filter_by section, document_id, search_by_section, search_by_document
  - VectorStore Management: clear(), clear_document(doc_id), stats
  - Full Pipeline Integration: Document -> Chunker -> Embeddings -> VectorStore -> RAGRetriever
"""

import pytest
import numpy as np
from typing import List, Dict, Any

from app.llm.embeddings import (
    EmbeddingService,
    embedding_service,
    batch_embed,
    EMBEDDING_DIM,
    _deterministic_embedding,
    _normalize,
    _project_to_dim,
)
from app.rag.vector_store import VectorStore, vector_store
from app.rag.retriever import RAGRetriever, rag_retriever
from app.rag.chunker import SemanticChunker, Chunk


# ---------------------------------------------------------------------------
# 1. Deterministic Helper & Normalization Tests
# ---------------------------------------------------------------------------

class TestEmbeddingMathHelpers:
    def test_deterministic_embedding_dimension(self):
        vec = _deterministic_embedding("test text", dim=768)
        assert len(vec) == 768
        assert isinstance(vec[0], float)

    def test_deterministic_embedding_normalized(self):
        vec = _deterministic_embedding("test text", dim=768)
        norm = np.linalg.norm(np.array(vec, dtype=np.float32))
        assert pytest.approx(norm, rel=1e-4) == 1.0

    def test_deterministic_embedding_reproducible(self):
        vec1 = _deterministic_embedding("battery state of charge", dim=768)
        vec2 = _deterministic_embedding("battery state of charge", dim=768)
        assert vec1 == vec2

    def test_deterministic_embedding_different_for_different_text(self):
        vec1 = _deterministic_embedding("battery state of charge", dim=768)
        vec2 = _deterministic_embedding("neural network architectures", dim=768)
        assert vec1 != vec2

    def test_normalize_helper(self):
        raw = [3.0, 4.0]
        normed = _normalize(raw)
        assert pytest.approx(normed[0]) == 0.6
        assert pytest.approx(normed[1]) == 0.8

    def test_normalize_zero_vector(self):
        zero = [0.0, 0.0, 0.0]
        normed = _normalize(zero)
        assert normed == zero

    def test_project_to_dim_exact(self):
        vec = [0.6, 0.8]
        proj = _project_to_dim(vec, 2)
        assert len(proj) == 2
        assert pytest.approx(np.linalg.norm(proj)) == 1.0

    def test_project_to_dim_truncate(self):
        vec = [1.0, 2.0, 3.0, 4.0]
        proj = _project_to_dim(vec, 2)
        assert len(proj) == 2
        assert pytest.approx(np.linalg.norm(proj)) == 1.0

    def test_project_to_dim_pad(self):
        vec = [3.0, 4.0]
        proj = _project_to_dim(vec, 5)
        assert len(proj) == 5
        assert pytest.approx(np.linalg.norm(proj)) == 1.0


# ---------------------------------------------------------------------------
# 2. EmbeddingService Unit Tests
# ---------------------------------------------------------------------------

class TestEmbeddingService:
    @pytest.fixture(autouse=True)
    def clean_cache(self):
        embedding_service.clear_cache()
        yield
        embedding_service.clear_cache()

    @pytest.mark.asyncio
    async def test_get_embedding_returns_768_dim(self):
        service = EmbeddingService()
        vec = await service.get_embedding("Electric vehicles market trends in 2026")
        assert len(vec) == EMBEDDING_DIM
        assert all(isinstance(v, float) for v in vec)

    @pytest.mark.asyncio
    async def test_get_embedding_is_normalized(self):
        service = EmbeddingService()
        vec = await service.get_embedding("Lithium-ion solid state battery technology")
        norm = np.linalg.norm(np.array(vec, dtype=np.float32))
        assert pytest.approx(norm, rel=1e-4) == 1.0

    @pytest.mark.asyncio
    async def test_get_embedding_empty_text(self):
        service = EmbeddingService()
        vec = await service.get_embedding("")
        assert len(vec) == EMBEDDING_DIM
        norm = np.linalg.norm(np.array(vec, dtype=np.float32))
        assert pytest.approx(norm, rel=1e-4) == 1.0

    @pytest.mark.asyncio
    async def test_get_embedding_whitespace_only(self):
        service = EmbeddingService()
        vec = await service.get_embedding("   \n\t  ")
        assert len(vec) == EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_get_embeddings_batch(self):
        service = EmbeddingService()
        texts = [
            "Text one about energy storage",
            "Text two about artificial intelligence",
            "Text three about quantum computing",
        ]
        vectors = await service.get_embeddings(texts)
        assert len(vectors) == 3
        for vec in vectors:
            assert len(vec) == EMBEDDING_DIM
            assert pytest.approx(np.linalg.norm(vec), rel=1e-4) == 1.0

    @pytest.mark.asyncio
    async def test_get_embeddings_empty_list(self):
        service = EmbeddingService()
        vectors = await service.get_embeddings([])
        assert vectors == []

    @pytest.mark.asyncio
    async def test_batch_embed_helper(self):
        texts = ["Alpha", "Beta", "Gamma"]
        vectors = await batch_embed(texts)
        assert len(vectors) == 3
        assert len(vectors[0]) == EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_caching_behavior(self):
        service = EmbeddingService()
        assert service.cache_size == 0

        # First call caches
        vec1 = await service.get_embedding("Renewable solar energy generation")
        assert service.cache_size == 1

        # Second call returns from cache
        vec2 = await service.get_embedding("Renewable solar energy generation")
        assert service.cache_size == 1
        assert vec1 == vec2

    @pytest.mark.asyncio
    async def test_batch_embed_uses_partial_cache(self):
        service = EmbeddingService()
        # Pre-cache one
        await service.get_embedding("First sentence")
        assert service.cache_size == 1

        # Batch embed with 1 cached + 2 new
        vectors = await service.get_embeddings(["First sentence", "Second sentence", "Third sentence"])
        assert len(vectors) == 3
        assert service.cache_size == 3

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        service = EmbeddingService()
        await service.get_embedding("Item to cache")
        assert service.cache_size == 1
        service.clear_cache()
        assert service.cache_size == 0

    @pytest.mark.asyncio
    async def test_get_stats(self):
        service = EmbeddingService()
        await service.get_embedding("Stats test text")
        stats = service.get_stats()
        assert stats["embedding_dim"] == EMBEDDING_DIM
        assert stats["cache_size"] == 1
        assert "provider" in stats
        assert "model" in stats


# ---------------------------------------------------------------------------
# 3. VectorStore Tests
# ---------------------------------------------------------------------------

class TestVectorStore:
    @pytest.fixture
    def store(self):
        return VectorStore()

    @pytest.mark.asyncio
    async def test_add_single_documents(self, store: VectorStore):
        docs = [
            {"content": "Electric cars adoption rate in Europe", "section": "Introduction", "document_id": "doc_1"},
            {"content": "Battery charging infrastructure network expansion", "section": "Results", "document_id": "doc_1"},
        ]
        count = await store.add_documents(docs)
        assert count == 2
        assert store.size == 2
        assert not store.is_empty

    @pytest.mark.asyncio
    async def test_add_documents_skips_empty(self, store: VectorStore):
        docs = [
            {"content": "", "section": "None"},
            {"content": "   ", "section": "None"},
            {"content": "Valid content for embedding", "section": "Valid"},
        ]
        count = await store.add_documents(docs)
        assert count == 1
        assert store.size == 1

    @pytest.mark.asyncio
    async def test_add_documents_batch(self, store: VectorStore):
        docs = [
            {"content": f"Document chunk number {i} with distinct technical content", "chunk_id": f"c_{i}"}
            for i in range(10)
        ]
        count = await store.add_documents_batch(docs)
        assert count == 10
        assert store.size == 10

    @pytest.mark.asyncio
    async def test_add_documents_batch_empty(self, store: VectorStore):
        count = await store.add_documents_batch([])
        assert count == 0
        assert store.is_empty

    @pytest.mark.asyncio
    async def test_search_empty_store(self, store: VectorStore):
        results = await store.search("some query", top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_returns_top_k(self, store: VectorStore):
        docs = [
            {"content": f"Research note on renewable solar photovoltaic {i}", "chunk_id": f"c_{i}"}
            for i in range(8)
        ]
        await store.add_documents_batch(docs)
        results = await store.search("photovoltaic efficiency", top_k=3)
        assert len(results) == 3
        for doc, score in results:
            assert isinstance(doc, dict)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_search_order_descending_similarity(self, store: VectorStore):
        docs = [
            {"content": "Quantum computing qubit superposition and entanglement", "id": "1"},
            {"content": "Agricultural wheat yield optimization techniques", "id": "2"},
            {"content": "Quantum error correction algorithms and surface codes", "id": "3"},
        ]
        await store.add_documents_batch(docs)
        results = await store.search("quantum computer error correction", top_k=3)
        assert len(results) == 3
        # Scores must be sorted descending
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_search_metadata_filter_by_section(self, store: VectorStore):
        docs = [
            {"content": "Methodology for testing electrochemical cell impedance", "section": "Methods", "document_id": "p1"},
            {"content": "Observed 35% improvement in degradation rate over 1000 cycles", "section": "Results", "document_id": "p1"},
            {"content": "Discussion of thermal management implications in winter", "section": "Discussion", "document_id": "p1"},
        ]
        await store.add_documents_batch(docs)

        # Filter strictly for Results section
        results = await store.search("performance improvement", top_k=5, filter_by={"section": "Results"})
        assert len(results) == 1
        assert results[0][0]["section"] == "Results"
        assert "35% improvement" in results[0][0]["content"]

    @pytest.mark.asyncio
    async def test_search_metadata_filter_by_document_id(self, store: VectorStore):
        docs = [
            {"content": "Report A on autonomous vehicles sensor fusion", "document_id": "doc_A"},
            {"content": "Report B on autonomous vehicles lidar localization", "document_id": "doc_B"},
            {"content": "Report A on radar perception pipeline", "document_id": "doc_A"},
        ]
        await store.add_documents_batch(docs)

        results = await store.search("autonomous vehicles", top_k=5, filter_by={"document_id": "doc_B"})
        assert len(results) == 1
        assert results[0][0]["document_id"] == "doc_B"

    @pytest.mark.asyncio
    async def test_search_by_section_helper(self, store: VectorStore):
        docs = [
            {"content": "Abstract: Overview of deep reinforcement learning", "section": "Abstract"},
            {"content": "Results: Policy gradient achieved 98% reward", "section": "Results"},
        ]
        await store.add_documents_batch(docs)
        results = await store.search_by_section("reward", section="Results")
        assert len(results) == 1
        assert results[0][0]["section"] == "Results"

    @pytest.mark.asyncio
    async def test_search_by_document_helper(self, store: VectorStore):
        docs = [
            {"content": "Paper 1 text", "document_id": "arxiv:2401.001"},
            {"content": "Paper 2 text", "document_id": "arxiv:2401.002"},
        ]
        await store.add_documents_batch(docs)
        results = await store.search_by_document("text", document_id="arxiv:2401.001")
        assert len(results) == 1
        assert results[0][0]["document_id"] == "arxiv:2401.001"

    @pytest.mark.asyncio
    async def test_clear_all(self, store: VectorStore):
        docs = [{"content": "Some text", "chunk_id": "1"}, {"content": "Other text", "chunk_id": "2"}]
        await store.add_documents_batch(docs)
        assert store.size == 2
        store.clear()
        assert store.size == 0
        assert store.is_empty

    @pytest.mark.asyncio
    async def test_clear_document_selective(self, store: VectorStore):
        docs = [
            {"content": "Doc 1 Chunk 1", "document_id": "doc_1"},
            {"content": "Doc 1 Chunk 2", "document_id": "doc_1"},
            {"content": "Doc 2 Chunk 1", "document_id": "doc_2"},
        ]
        await store.add_documents_batch(docs)
        assert store.size == 3

        removed = store.clear_document("doc_1")
        assert removed == 2
        assert store.size == 1
        assert store._documents[0]["document_id"] == "doc_2"

    @pytest.mark.asyncio
    async def test_get_stats(self, store: VectorStore):
        docs = [
            {"content": "Chunk 1", "section": "Introduction", "document_id": "doc_A"},
            {"content": "Chunk 2", "section": "Results", "document_id": "doc_A"},
            {"content": "Chunk 3", "section": "Results", "document_id": "doc_B"},
        ]
        await store.add_documents_batch(docs)
        stats = store.get_stats()
        assert stats["total_chunks"] == 3
        assert stats["unique_documents"] == 2
        assert stats["sections"] == {"Introduction": 1, "Results": 2}
        assert stats["embedding_dim"] == EMBEDDING_DIM


# ---------------------------------------------------------------------------
# 4. Full End-to-End Pipeline Integration Tests
# ---------------------------------------------------------------------------

class TestFullRAGPipeline:
    @pytest.fixture(autouse=True)
    def reset_global_store(self):
        vector_store.clear()
        embedding_service.clear_cache()
        yield
        vector_store.clear()
        embedding_service.clear_cache()

    @pytest.mark.asyncio
    async def test_document_to_retrieval_full_pipeline(self):
        """
        Tests the entire Day 21-24 flow:
        Document -> Sections -> Chunks -> Embeddings -> VectorStore -> Retrieval with metadata
        """
        # 1. Realistic source with structured sections
        source = {
            "source_id": "paper_ev_battery_2026",
            "url": "https://arxiv.org/abs/2601.12345",
            "title": "State of Health Estimation for EV Lithium-ion Batteries",
            "source_type": "academic",
            "clean_text": (
                "## Abstract\n"
                "Electric vehicle lithium-ion battery management requires precise state-of-health tracking. "
                "We develop an attention-based neural network model for capacity estimation.\n\n"
                "## Results\n"
                "Our proposed model achieves a mean absolute percentage error of 0.84% across 500 test cells. "
                "Fast-charging degradation was successfully captured with 99.2% correlation to lab measurements.\n\n"
                "## Conclusion\n"
                "The proposed framework is suitable for real-time onboard battery management systems in EVs."
            )
        }

        # 2. Index via RAGRetriever
        retriever = RAGRetriever()
        num_chunks = await retriever.index_sources([source])
        assert num_chunks >= 3
        assert vector_store.size >= 3

        # 3. Retrieve general query
        results = await retriever.retrieve_relevant_context("battery capacity estimation error percentage", top_k=2)
        assert len(results) > 0
        top = results[0]
        assert "content" in top
        assert "score" in top
        assert "section" in top
        assert "document_id" in top
        assert top["document_id"] == "paper_ev_battery_2026"

        # 4. Retrieve with section filter (Results only)
        results_only = await retriever.retrieve_by_section("degradation", section="Results", top_k=2)
        assert len(results_only) > 0
        for r in results_only:
            assert r["section"] == "Results"
            assert "0.84%" in r["content"] or "degradation" in r["content"]

    @pytest.mark.asyncio
    async def test_academic_pdf_evidence_blocks_indexing(self):
        """
        Tests indexing a paper that came from PDFExtractor with evidence_blocks.
        """
        pdf_source = {
            "source_id": "pdf_paper_001",
            "url": "https://example.com/paper.pdf",
            "title": "Solid State Battery Electrolytes",
            "source_type": "academic",
            "metadata": {
                "evidence_blocks": [
                    {
                        "page": 1,
                        "section": "Abstract",
                        "text": "Sulfide-based solid electrolytes exhibit high ionic conductivity exceeding 10 mS/cm at room temperature.",
                    },
                    {
                        "page": 5,
                        "section": "Results",
                        "text": "The all-solid-state pouch cell demonstrated 80% capacity retention after 1500 cycles at 1C rate.",
                    }
                ]
            }
        }

        retriever = RAGRetriever()
        indexed = await retriever.index_sources([pdf_source])
        assert indexed >= 2

        results = await retriever.retrieve_relevant_context("capacity retention after 1500 cycles", top_k=1)
        assert len(results) == 1
        assert results[0]["page"] == 5
        assert results[0]["section"] == "Results"
        assert "1500 cycles" in results[0]["content"]
