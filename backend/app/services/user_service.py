from typing import Optional, List
from fastapi import HTTPException, status
from app.database.models.user import UserCreate, UserInDB, UserResponse
from app.database.repositories.user_repo import user_repo
from app.middleware.auth import get_password_hash, verify_password, create_access_token


class UserService:
    async def register_user(self, user_in: UserCreate) -> UserResponse:
        existing = await user_repo.get_by_email(user_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        hashed = get_password_hash(user_in.password)
        db_user = UserInDB(
            email=user_in.email,
            full_name=user_in.full_name,
            role=user_in.role,
            hashed_password=hashed
        )
        saved = await user_repo.create(db_user)
        return UserResponse(
            id=saved.id,
            email=saved.email,
            full_name=saved.full_name,
            role=saved.role,
            is_active=saved.is_active,
            created_at=saved.created_at
        )

    async def authenticate_user(self, email: str, password: str) -> Optional[dict]:
        user = await user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        
        access_token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role
            }
        }


user_service = UserService()
