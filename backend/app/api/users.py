from typing import List
from fastapi import APIRouter, Depends, HTTPException
from app.database.models.user import UserResponse, UserInDB, UserRole
from app.database.repositories.user_repo import user_repo
from app.middleware.auth import require_auth

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=List[UserResponse])
async def list_users(current_user: UserInDB = Depends(require_auth)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    users = await user_repo.list_all()
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at
        )
        for u in users
    ]
