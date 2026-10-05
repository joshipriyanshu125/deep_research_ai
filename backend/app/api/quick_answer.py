"""
Quick Answer API — POST /api/v1/quick-answer

Routes the query through the classifier and either:
  • Returns a direct Gemini answer (quick mode), or
  • Signals the client to use the full deep-research pipeline.

Also exposes GET /api/v1/quick-answer/classify for the frontend to
pre-flight a query and decide which UI branch to show.
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
    Smart query router:
    - Simple queries  → direct Gemini answer (no pipeline overhead)
    - Complex queries → instructs client to launch Deep Research pipeline
    """
    query = request.query.strip()
    mode = classify_query(query)

    if mode == "deep":
        logger.info(f"[QueryRouter] Routing '{query[:60]}...' → Deep Research pipeline")
        return RouteResponse(
            query=query,
            mode="deep",
            message=(
                "This query requires deep research. "
                "Please use the Deep Research pipeline for a comprehensive report."
            ),
        )

    # Quick mode — call Gemini
    logger.info(f"[QueryRouter] Routing '{query[:60]}...' → Quick Answer (Gemini)")
    try:
        result = await quick_answer_service.answer(query)
        return RouteResponse(
            query=query,
            mode="quick",
            answer=result["answer"],
            model=result["model"],
        )
    except RuntimeError as exc:
        # Gemini key not configured — fall back gracefully to deep pipeline
        logger.warning(f"[QuickAnswer] Gemini unavailable ({exc}). Falling back to deep mode.")
        return RouteResponse(
            query=query,
            mode="deep",
            message=(
                "Quick Answer is not configured (missing GEMINI_API_KEY). "
                "Launching the full Deep Research pipeline instead."
            ),
        )
    except Exception as exc:
        logger.error(f"[QuickAnswer] Unexpected error: {exc}")
        raise HTTPException(status_code=500, detail=f"Quick Answer failed: {exc}")
