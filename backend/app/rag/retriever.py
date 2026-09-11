"""
RAG Retriever — updated for Day 24 Embeddings & Day 23 Semantic Chunking.

index_sources now uses SemanticChunker + VectorStore batch insert:
  Document
    ↓
  Sections (SemanticChunker)
    ↓
  Chunks (carrying page, section, doc_id, metadata)
    ↓
  Batch Embeddings (1 API call)
    ↓
  Vector Store (768-dim normalized vectors)

Backward-compatible: existing callers pass the same source dicts.
"""

from typing import List, Dict, Any, Optional
from app.rag.vector_store import vector_store
from app.rag.chunker import semantic_chunker, text_chunker


class RAGRetriever:
    async def index_sources(self, sources: List[Dict[str, Any]]) -> int:
        """
        Index a list of source dicts using the semantic chunker and batch embedding.

        Supports:
          - Plain-text sources (web / news / company)
          - PDF-sourced sources with evidence_blocks (academic papers — Day 22)

        Returns total number of chunks indexed.
        """
        all_rag_docs: List[Dict[str, Any]] = []

        for s in sources:
            # Use SemanticChunker.chunk_source which auto-detects PDF blocks vs plain text
            chunks = semantic_chunker.chunk_source(s)

            if not chunks:
                # Last-resort fallback: use old text_chunker on raw text
                text = s.get("clean_text") or s.get("content") or s.get("snippet") or ""
                if text:
                    flat_chunks = text_chunker.chunk_text(text, metadata={
                        "source_id": s.get("id") or s.get("source_id", ""),
                        "url": s.get("url", ""),
                        "title": s.get("title", ""),
                        "source_type": s.get("source_type", "web"),
                    })
                    all_rag_docs.extend(flat_chunks)
                continue

            for chunk in chunks:
                all_rag_docs.append(chunk.to_rag_document())

        if all_rag_docs:
            await vector_store.add_documents_batch(all_rag_docs)

        return len(all_rag_docs)

    async def retrieve_relevant_context(
        self,
        sub_query: str,
        top_k: int = 4,
        filter_by: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the most relevant chunks for a sub-query.
        Returns list of dicts: {content, metadata, score, page, section, chunk_id, document_id}.
        """
        results = await vector_store.search(
            sub_query,
            top_k=top_k,
            filter_by=filter_by,
            min_score=min_score,
        )
        return [
            {
                "content": item[0].get("content", ""),
                "metadata": item[0].get("metadata", {}),
                "score": item[1],
                # Promoted fields for caller convenience
                "page": item[0].get("page"),
                "section": item[0].get("section", ""),
                "chunk_id": item[0].get("chunk_id", ""),
                "document_id": item[0].get("document_id", ""),
            }
            for item in results
        ]

    async def retrieve_by_section(
        self,
        sub_query: str,
        section: str,
        top_k: int = 4,
    ) -> List[Dict[str, Any]]:
        """Retrieve chunks only from a specific section (e.g. 'Results' or 'Abstract')."""
        return await self.retrieve_relevant_context(
            sub_query,
            top_k=top_k,
            filter_by={"section": section},
        )


rag_retriever = RAGRetriever()
