import numpy as np
from typing import List, Dict, Any, Tuple
from app.rag.embeddings import embedding_service
from app.utils.logger import logger


class VectorStore:
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.vectors: List[List[float]] = []

    async def add_documents(self, docs: List[Dict[str, Any]]):
        for doc in docs:
            text = doc.get("content", "")
            if not text:
                continue
            vector = await embedding_service.get_embedding(text)
            self.documents.append(doc)
            self.vectors.append(vector)

    async def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        if not self.documents:
            return []

        query_vector = await embedding_service.get_embedding(query)
        q_vec = np.array(query_vector, dtype=np.float32)
        doc_matrix = np.array(self.vectors, dtype=np.float32)

        # Compute cosine similarity
        q_norm = np.linalg.norm(q_vec) + 1e-9
        doc_norms = np.linalg.norm(doc_matrix, axis=1) + 1e-9
        similarities = np.dot(doc_matrix, q_vec) / (doc_norms * q_norm)

        # Top k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            results.append((self.documents[idx], float(similarities[idx])))
            
        return results

    def clear(self):
        self.documents = []
        self.vectors = []


vector_store = VectorStore()
