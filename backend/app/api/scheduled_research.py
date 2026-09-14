from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from app.database.models.scheduled_research import (
    ScheduledResearch,
    ScheduledResearchCreate,
    ScheduledResearchUpdate,
    ScheduledChangeReport,
)
from app.database.repositories.scheduled_research_repo import scheduled_research_repo
from app.services.scheduled_research_service import scheduled_research_service
from app.database.models.user import UserInDB
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/scheduled-research", tags=["Scheduled Research"])


@router.post("", response_model=ScheduledResearch)
@router.post("/", response_model=ScheduledResearch, include_in_schema=False)
async def create_scheduled_research(
    request: ScheduledResearchCreate,
    current_user: Optional[UserInDB] = Depends(get_current_user),
):
    user_id = current_user.id if current_user else "anonymous"
    return await scheduled_research_service.create_schedule(request, user_id=user_id)


@router.get("", response_model=List[ScheduledResearch])
@router.get("/", response_model=List[ScheduledResearch], include_in_schema=False)
async def list_scheduled_research(
    limit: int = 50,
    current_user: Optional[UserInDB] = Depends(get_current_user),
):
    user_id = current_user.id if current_user else "anonymous"
    return await scheduled_research_service.list_user_schedules(user_id=user_id, limit=limit)


@router.get("/reports/{report_id}", response_model=ScheduledChangeReport)
async def get_change_report(report_id: str):
    report = await scheduled_research_repo.get_change_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Change report not found")
    return report


@router.get("/{id}", response_model=ScheduledResearch)
async def get_scheduled_research(id: str):
    return await scheduled_research_service.get_schedule(id)


@router.patch("/{id}", response_model=ScheduledResearch)
async def update_scheduled_research(id: str, request: ScheduledResearchUpdate):
    return await scheduled_research_service.update_schedule(id, request)


@router.delete("/{id}")
async def delete_scheduled_research(id: str):
    success = await scheduled_research_service.delete_schedule(id)
    return {"status": "deleted" if success else "failed", "id": id}


@router.post("/{id}/run", response_model=ScheduledChangeReport)
async def run_scheduled_research_manually(id: str):
    return await scheduled_research_service.execute_scheduled_task(id)


@router.get("/{id}/reports", response_model=List[ScheduledChangeReport])
async def list_schedule_change_reports(id: str, limit: int = 50):
    await scheduled_research_service.get_schedule(id)
    return await scheduled_research_repo.list_change_reports(scheduled_id=id, limit=limit)
