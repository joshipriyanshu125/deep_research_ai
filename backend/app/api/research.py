import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.database.models.research import ResearchJob, ResearchRequest
from app.database.models.user import UserInDB
from app.services.research_service import research_service
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/research", tags=["Research"])


@router.post("/start", response_model=ResearchJob)
async def start_research(
    request: ResearchRequest,
    current_user: Optional[UserInDB] = Depends(get_current_user)
):
    user_id = current_user.id if current_user else "anonymous"
    job = await research_service.create_research_job(request, user_id=user_id)
    return job


@router.get("/{job_id}", response_model=ResearchJob)
async def get_research_status(job_id: str):
    return await research_service.get_job_status(job_id)


@router.get("/{job_id}/stream")
async def stream_research(job_id: str):
    async def event_generator():
        async for event in research_service.stream_research_progress(job_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
