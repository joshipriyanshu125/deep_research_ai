from typing import List, Dict, Any
from app.rag.vector_store import vector_store
from app.rag.chunker import text_chunker


class RAGRetriever:
    async def index_sources(self, sources: List[Dict[str, Any]]):
        all_chunks = []
        for s in sources:
            text = s.get("clean_text") or s.get("snippet") or ""
            chunks = text_chunker.chunk_text(text, metadata={
                "source_id": s.get("id"),
                "url": s.get("url"),
                "title": s.get("title"),
                "source_type": s.get("source_type")
            })
            all_chunks.extend(chunks)
            
        if all_chunks:
            await vector_store.add_documents(all_chunks)

    async def retrieve_relevant_context(self, sub_query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        results = await vector_store.search(sub_query, top_k=top_k)
        return [
            {
                "content": item[0]["content"],
                "metadata": item[0]["metadata"],
                "score": item[1]
            }
            for item in results
        ]


rag_retriever = RAGRetriever()
