from typing import List, Optional
from fastapi import APIRouter, Depends
from app.database.models.research import ResearchJob
from app.database.models.user import UserInDB
from app.services.research_service import research_service
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/history", tags=["Research History"])


@router.get("/", response_model=List[ResearchJob])
async def get_history(
    limit: int = 50,
    current_user: Optional[UserInDB] = Depends(get_current_user)
):
    user_id = current_user.id if current_user else "anonymous"
    return await research_service.list_user_jobs(user_id=user_id, limit=limit)
