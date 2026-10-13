"""
Quick Answer API — POST /api/v1/quick-answer

Returns a direct Gemini answer. Deep Research is an explicit user choice and
this endpoint never auto-routes a question into a background research job.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.services.quick_answer_service import quick_answer_service, classify_query
from app.utils.logger import logger

router = APIRouter(prefix="/quick-answer", tags=["Quick Answer"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class QuickAnswerRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="The user's question")


class QueryClassificationResponse(BaseModel):
    query: str
    mode: str           # "quick" | "deep"
    reason: str


class QuickAnswerResponse(BaseModel):
    query: str
    answer: str
    model: str
    mode: str           # always "quick" here


class RouteResponse(BaseModel):
    query: str
    mode: str           # "quick" | "deep"
    answer: Optional[str] = None   # present when mode == "quick"
    model: Optional[str] = None
    message: Optional[str] = None  # present when mode == "deep"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/classify", response_model=QueryClassificationResponse)
async def classify_query_endpoint(q: str):
    """
    Classify a query as 'quick' (simple factual) or 'deep' (research-worthy).
    The frontend can call this to decide which UI path to present before submitting.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=422, detail="Query parameter 'q' is required.")

    mode = classify_query(q)
    reason = (
        "Query appears simple and factual — a direct answer is sufficient."
        if mode == "quick"
        else "Query is complex or research-intensive — the full pipeline is recommended."
    )
    return QueryClassificationResponse(query=q, mode=mode, reason=reason)


@router.post("", response_model=RouteResponse)
@router.post("/", response_model=RouteResponse, include_in_schema=False)
async def quick_answer(request: QuickAnswerRequest):
    """
    Explicit Quick Answer endpoint — direct Gemini response, no research job.
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query cannot be empty.")

    # Quick mode — call Gemini
    logger.info("[QuickAnswer] Requesting a direct Gemini answer.")
    try:
        result = await quick_answer_service.answer(query)
        return RouteResponse(
            query=query,
            mode="quick",
            answer=result["answer"],
            model=result["model"],
        )
    except RuntimeError as exc:
        logger.warning(f"[QuickAnswer] Gemini unavailable: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"[QuickAnswer] Unexpected error: {exc}")
        raise HTTPException(status_code=500, detail=f"Quick Answer failed: {exc}")
