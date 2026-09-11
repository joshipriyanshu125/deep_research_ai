"""
Day 24 — RAG Embeddings Adapter

Re-exports the core EmbeddingService and singletons from app.llm.embeddings.
Maintains backward compatibility across all rag consumers.
"""

from app.llm.embeddings import (
    EmbeddingService,
    embedding_service,
    batch_embed,
    EMBEDDING_DIM,
)

__all__ = [
    "EmbeddingService",
    "embedding_service",
    "batch_embed",
    "EMBEDDING_DIM",
]
