from fastapi import APIRouter, Depends, HTTPException
from app.database.models.user import UserInDB, UserRole
from app.middleware.auth import require_auth
from app.config.settings import settings

router = APIRouter(prefix="/admin", tags=["Admin System Control"])


@router.get("/status")
async def get_system_status(current_user: UserInDB = Depends(require_auth)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    return {
        "project_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "llm_provider": settings.LLM_PROVIDER,
        "default_model": settings.DEFAULT_MODEL
    }
