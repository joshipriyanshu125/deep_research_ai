import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from app.database.models.research import ResearchJob, ResearchRequest, FollowUpRequest
from app.database.repositories.research_repo import research_repo
from app.database.repositories.report_repo import report_repo
from app.database.models.user import UserInDB
from app.services.research_service import research_service
from app.middleware.auth import get_current_user
from app.research.events import research_event_bus
from app.database.models.comparison import ResearchComparison, ResearchComparisonRequest
from app.services.comparison_service import comparison_service
# Day 91–95 — Advanced Research Modes
from app.research.research_modes import list_modes

router = APIRouter(prefix="/research", tags=["Research"])



@router.post("/compare", response_model=ResearchComparison)
async def compare_research_runs(
    request: ResearchComparisonRequest,
    current_user: Optional[UserInDB] = Depends(get_current_user),
):
    comparison = await comparison_service.compare(request.run_a_id, request.run_b_id)
    if current_user and comparison.run_a_id and comparison.run_b_id:
        run_a = await research_service.get_job_status(comparison.run_a_id)
        if run_a.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Research run access denied")
    return comparison

@router.get("", response_model=List[ResearchJob])
@router.get("/", response_model=List[ResearchJob], include_in_schema=False)
async def list_research(limit: int = 50, current_user: Optional[UserInDB] = Depends(get_current_user)):
    return await research_service.list_user_jobs(current_user.id if current_user else "anonymous", limit)


@router.post("/start", response_model=ResearchJob)
async def start_research(
    request: ResearchRequest,
    current_user: Optional[UserInDB] = Depends(get_current_user)
):
    user_id = current_user.id if current_user else "anonymous"
    job = await research_service.create_research_job(request, user_id=user_id)
    return job


# Day 91–95 — Advanced Research Modes
@router.get("/modes", summary="List all available research modes")
async def list_research_modes():
    """
    Return configuration details for all four research modes:
    quick, standard, deep, expert.
    Clients can use this to populate a mode-selector UI component.
    """
    return {"modes": list_modes()}


@router.get("/{job_id}", response_model=ResearchJob)

async def get_research_status(job_id: str):
    return await research_service.get_job_status(job_id)

@router.get("/{job_id}/sources")
async def get_research_sources(job_id: str):
    await research_service.get_job_status(job_id)
    return [s.model_dump(mode="json") for s in await research_repo.get_sources_by_research(job_id)]

@router.get("/{job_id}/report")
async def get_research_report(job_id: str):
    await research_service.get_job_status(job_id)
    report = await report_repo.get_by_research_id(job_id)
    if not report:
        raise HTTPException(status_code=404, detail="Research report not found")
    return report

@router.post("/{job_id}/follow-up", response_model=ResearchJob)
async def follow_up_research(job_id: str, request: FollowUpRequest):
    parent = await research_service.get_job_status(job_id)
    return await research_service.create_follow_up(parent, request.query)

@router.post("/{job_id}/resume", response_model=ResearchJob)
async def resume_research(job_id: str):
    job = await research_service.get_job_status(job_id)
    return await research_service.resume_research(job)


@router.get("/{job_id}/stream")
async def stream_research(job_id: str):
    async def event_generator():
        try:
            async for event in research_service.stream_research_progress(job_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception:
            yield f"data: {json.dumps({'event': 'stream_error', 'data': {'job_id': job_id, 'error': 'Stream closed unexpectedly'}})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.websocket("/ws/{job_id}")
async def stream_research_websocket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        job = await research_service.get_job_status(job_id)
        await websocket.send_json({"event": "job_status", "data": job.model_dump(mode="json")})
        for historical in research_event_bus.get_history(job_id):
            await websocket.send_json(historical)
        async for event in research_event_bus.subscribe(job_id):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.send_json({
            "event": "stream_error",
            "data": {"job_id": job_id, "error": "Unable to stream research events"},
        })
        await websocket.close(code=1011)
