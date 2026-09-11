"""
Day 25 — Complete RAG Generation Pipeline

Architecture:
  Question (+ optional Research Context)
    ↓
  Hybrid Retriever (Semantic + BM25 + Quality + Recency + Context)
    ↓
  Reranked Top Chunks
    ↓
  Context Formatter with Provenance Tags [1], [2]
    ↓
  LLM Generation (evidence-grounded synthesis)
    ↓
  Structured RAG Response with inline Citations & Sources
"""

import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.rag.retriever import rag_retriever, RAGRetriever
from app.llm.service import llm_service, LLMService
from app.llm.prompts import rag_generation_prompt
from app.utils.logger import logger


class RAGCitation(BaseModel):
    index: int
    source_id: str
    title: str
    url: str
    page: Optional[int] = None
    section: Optional[str] = None
    hybrid_score: float = 0.0


class RAGResponse(BaseModel):
    question: str
    answer: str
    citations: List[RAGCitation] = Field(default_factory=list)
    retrieved_chunks: List[Dict[str, Any]] = Field(default_factory=list)
    research_context: Optional[str] = None
    total_chunks_found: int = 0


class RAGPipeline:
    """
    Day 25 — End-to-End RAG Pipeline with Hybrid Search and LLM Generation.
    """

    def __init__(
        self,
        retriever: Optional[RAGRetriever] = None,
        llm: Optional[LLMService] = None,
    ):
        self.retriever = retriever or rag_retriever
        self.llm = llm or llm_service

    async def answer(
        self,
        question: str,
        research_context: Optional[str] = None,
        top_k: int = 4,
        filter_by: Optional[Dict[str, Any]] = None,
        generate_answer: bool = True,
    ) -> RAGResponse:
        """
        Executes the full RAG pipeline for a question:
          1. Hybrid retrieval & reranking
          2. Formats structured context with numbered citations [1], [2]
          3. Prompts LLM for evidence-grounded answer
          4. Returns structured RAGResponse
        """
        if not question or not question.strip():
            return RAGResponse(
                question=question,
                answer="No question provided.",
                citations=[],
                retrieved_chunks=[],
                total_chunks_found=0,
            )

        # 1. Retrieve candidates via hybrid search
        chunks = await self.retriever.retrieve_hybrid(
            query=question,
            research_context=research_context,
            top_k=top_k,
            filter_by=filter_by,
        )

        if not chunks:
            # Fallback to simple semantic retrieval
            chunks = await self.retriever.retrieve_relevant_context(
                sub_query=question,
                top_k=top_k,
                filter_by=filter_by,
            )

        if not chunks:
            return RAGResponse(
                question=question,
                answer="No relevant evidence found in the indexed sources to answer this question.",
                citations=[],
                retrieved_chunks=[],
                research_context=research_context,
                total_chunks_found=0,
            )

        # 2. Build numbered context block & citation metadata
        context_lines: List[str] = []
        citations: List[RAGCitation] = []

        for idx, chunk in enumerate(chunks, start=1):
            content = chunk.get("content", "").strip()
            meta = chunk.get("metadata") or {}
            source_id = chunk.get("document_id") or meta.get("source_id") or f"src_{idx}"
            title = meta.get("title") or chunk.get("title") or "Source Document"
            url = meta.get("url") or chunk.get("url") or ""
            page = chunk.get("page") or meta.get("page")
            section = chunk.get("section") or meta.get("section") or "Body"
            score = chunk.get("hybrid_score") or chunk.get("score") or 0.0

            loc_str = f"Section: {section}"
            if page is not None:
                loc_str += f", Page: {page}"

            context_lines.append(f"[{idx}] Title: {title} ({loc_str})\nText: {content}")

            citations.append(
                RAGCitation(
                    index=idx,
                    source_id=str(source_id),
                    title=str(title),
                    url=str(url),
                    page=page,
                    section=str(section),
                    hybrid_score=float(score),
                )
            )

        context_text = "\n\n".join(context_lines)

        # 3. Optional research context formatting
        ctx_section = ""
        if research_context and research_context.strip():
            ctx_section = f"Overarching Research Context: {research_context.strip()}\n\n"

        # 4. Generate answer via LLM
        if generate_answer:
            try:
                answer = await self.llm.execute_prompt(
                    rag_generation_prompt,
                    variables={
                        "question": question,
                        "research_context_section": ctx_section,
                        "context_text": context_text,
                    },
                )
            except Exception as e:
                logger.warning(f"RAG LLM generation failed: {e}. Returning context preview.")
                answer = (
                    f"Retrieved {len(chunks)} relevant evidence chunks for '{question}', "
                    f"but LLM generation failed: {e}"
                )
        else:
            answer = f"Retrieved {len(chunks)} relevant chunks."

        return RAGResponse(
            question=question,
            answer=answer,
            citations=citations,
            retrieved_chunks=chunks,
            research_context=research_context,
            total_chunks_found=len(chunks),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

rag_pipeline = RAGPipeline()
