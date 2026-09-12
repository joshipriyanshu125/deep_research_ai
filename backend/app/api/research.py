import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from app.database.models.research import ResearchJob, ResearchRequest
from app.database.models.user import UserInDB
from app.services.research_service import research_service
from app.middleware.auth import get_current_user
from app.research.events import research_event_bus

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
