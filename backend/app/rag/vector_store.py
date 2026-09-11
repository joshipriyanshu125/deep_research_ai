"""
Day 24 — Production Vector Store

Features:
  - Batch insert:   add_documents_batch() — one embedding call for N docs
  - Single insert:  add_documents() — backward compatible
  - Search:         cosine similarity with optional metadata filtering
  - Filter search:  retrieve only chunks from a specific section/document
  - Stats:          size, document count, section distribution
  - Selective clear: clear_document(document_id) — remove all chunks for a source
  - Full clear:     clear()

All vectors are stored as 768-dim unit-normalized float32 arrays.
"""

import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from app.rag.embeddings import embedding_service
from app.utils.logger import logger


class VectorStore:
    """
    Day 24 — In-memory vector store with cosine similarity search,
    metadata filtering, batch insertion, and per-document management.
    """

    def __init__(self):
        self._documents: List[Dict[str, Any]] = []
        self._vectors: List[List[float]] = []

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    async def add_documents(self, docs: List[Dict[str, Any]]) -> int:
        """
        Add documents one-by-one (backward compatible with Day 14–23).
        Returns number of documents successfully added.
        For better performance with large batches, use add_documents_batch().
        """
        added = 0
        for doc in docs:
            text = doc.get("content", "")
            if not text or not text.strip():
                continue
            try:
                vector = await embedding_service.get_embedding(text)
                self._documents.append(doc)
                self._vectors.append(vector)
                added += 1
            except Exception as e:
                logger.warning(f"Failed to embed document: {e}")
        return added

    async def add_documents_batch(self, docs: List[Dict[str, Any]]) -> int:
        """
        Add documents using a single batch embedding call.
        Significantly faster than add_documents() for N > 5 documents.
        Returns number of documents successfully added.
        """
        if not docs:
            return 0

        # Filter valid docs
        valid: List[Tuple[int, Dict[str, Any], str]] = []
        for i, doc in enumerate(docs):
            text = (doc.get("content") or "").strip()
            if text:
                valid.append((i, doc, text))

        if not valid:
            return 0

        texts = [t for _, _, t in valid]
        try:
            vectors = await embedding_service.get_embeddings(texts)
        except Exception as e:
            logger.warning(f"Batch embedding failed: {e}. Falling back to individual embeds.")
            return await self.add_documents(docs)

        for (_orig_idx, doc, _text), vec in zip(valid, vectors):
            self._documents.append(doc)
            self._vectors.append(vec)

        added = len(valid)
        logger.debug(f"VectorStore: batch added {added} documents via {embedding_service.provider}")
        return added

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_by: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Cosine similarity search with optional metadata filtering.

        Args:
            query:      The search query string
            top_k:      Max results to return
            filter_by:  Dict of metadata key→value to pre-filter candidates.
                        e.g. {"section": "Results"} or {"document_id": "src_001"}
            min_score:  Minimum cosine similarity threshold (0.0 = no threshold)

        Returns:
            List of (document, score) tuples sorted by descending similarity.
        """
        if not self._documents:
            return []

        # Embed query
        try:
            query_vector = await embedding_service.get_embedding(query)
        except Exception as e:
            logger.warning(f"Query embedding failed: {e}")
            return []

        q_vec = np.array(query_vector, dtype=np.float32)

        # Apply metadata pre-filter to get candidate indices
        if filter_by:
            candidate_indices = [
                i for i, doc in enumerate(self._documents)
                if self._matches_filter(doc, filter_by)
            ]
        else:
            candidate_indices = list(range(len(self._documents)))

        if not candidate_indices:
            return []

        # Build candidate matrix
        candidate_vecs = np.array(
            [self._vectors[i] for i in candidate_indices],
            dtype=np.float32,
        )

        # Cosine similarity (vectors are pre-normalized)
        q_norm = np.linalg.norm(q_vec) + 1e-9
        doc_norms = np.linalg.norm(candidate_vecs, axis=1) + 1e-9
        similarities = np.dot(candidate_vecs, q_vec) / (doc_norms * q_norm)

        # Sort descending
        sorted_local = np.argsort(similarities)[::-1]

        results = []
        for local_idx in sorted_local:
            score = float(similarities[local_idx])
            if score < min_score:
                break
            orig_idx = candidate_indices[int(local_idx)]
            results.append((self._documents[orig_idx], score))
            if len(results) >= top_k:
                break

        return results

    async def search_by_section(
        self,
        query: str,
        section: str,
        top_k: int = 4,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Retrieve chunks only from a specific section (e.g. 'Results')."""
        return await self.search(query, top_k=top_k, filter_by={"section": section})

    async def search_by_document(
        self,
        query: str,
        document_id: str,
        top_k: int = 4,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Retrieve chunks only from a specific document."""
        return await self.search(query, top_k=top_k, filter_by={"document_id": document_id})

    # ------------------------------------------------------------------
    # Management
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all documents and vectors from the store."""
        self._documents.clear()
        self._vectors.clear()
        logger.debug("VectorStore: cleared all documents")

    def clear_document(self, document_id: str) -> int:
        """
        Remove all chunks belonging to a specific document_id.
        Returns number of chunks removed.
        """
        keep_docs: List[Dict[str, Any]] = []
        keep_vecs: List[List[float]] = []
        removed = 0

        for doc, vec in zip(self._documents, self._vectors):
            if doc.get("document_id") == document_id or doc.get("metadata", {}).get("document_id") == document_id:
                removed += 1
            else:
                keep_docs.append(doc)
                keep_vecs.append(vec)

        self._documents = keep_docs
        self._vectors = keep_vecs
        logger.debug(f"VectorStore: cleared {removed} chunks for document_id={document_id!r}")
        return removed

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """Total number of chunks stored."""
        return len(self._documents)

    @property
    def is_empty(self) -> bool:
        return len(self._documents) == 0

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics about the store contents."""
        if not self._documents:
            return {
                "total_chunks": 0,
                "unique_documents": 0,
                "sections": {},
                "embedding_dim": embedding_service.embedding_dim,
                "embedding_provider": embedding_service.provider,
                "cache_size": embedding_service.cache_size,
            }

        doc_ids = {
            doc.get("document_id") or doc.get("metadata", {}).get("document_id", "unknown")
            for doc in self._documents
        }
        sections: Dict[str, int] = {}
        for doc in self._documents:
            sec = doc.get("section") or doc.get("metadata", {}).get("section", "unknown")
            sections[sec] = sections.get(sec, 0) + 1

        return {
            "total_chunks": len(self._documents),
            "unique_documents": len(doc_ids),
            "sections": sections,
            "embedding_dim": embedding_service.embedding_dim,
            "embedding_provider": embedding_service.provider,
            "cache_size": embedding_service.cache_size,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_filter(doc: Dict[str, Any], filter_by: Dict[str, Any]) -> bool:
        """Check if a document matches all filter criteria."""
        meta = doc.get("metadata") or {}
        for key, value in filter_by.items():
            # Check top-level first, then metadata
            doc_val = doc.get(key) or meta.get(key)
            if doc_val != value:
                return False
        return True


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

vector_store = VectorStore()
