"""
RAG Module — Day 23 Chunking, Day 24 Embeddings & Vector Store, Day 25 Hybrid Retrieval & RAG Pipeline
"""

from app.rag.chunker import Chunk, SemanticChunker, TextChunker, semantic_chunker, text_chunker
from app.rag.embeddings import EmbeddingService, embedding_service, batch_embed, EMBEDDING_DIM
from app.rag.vector_store import VectorStore, vector_store
from app.rag.reranker import HybridReranker, hybrid_reranker, LexicalScorer, SourceQualityScorer, RecencyScorer, ContextAlignmentScorer
from app.rag.retriever import RAGRetriever, rag_retriever
from app.rag.pipeline import RAGPipeline, rag_pipeline, RAGResponse, RAGCitation

__all__ = [
    # Chunking
    "Chunk",
    "SemanticChunker",
    "TextChunker",
    "semantic_chunker",
    "text_chunker",
    # Embeddings
    "EmbeddingService",
    "embedding_service",
    "batch_embed",
    "EMBEDDING_DIM",
    # Vector Store
    "VectorStore",
    "vector_store",
    # Reranker & Hybrid Search
    "HybridReranker",
    "hybrid_reranker",
    "LexicalScorer",
    "SourceQualityScorer",
    "RecencyScorer",
    "ContextAlignmentScorer",
    # Retriever & Pipeline
    "RAGRetriever",
    "rag_retriever",
    "RAGPipeline",
    "rag_pipeline",
    "RAGResponse",
    "RAGCitation",
]
