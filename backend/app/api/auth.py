from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from app.database.models.user import UserCreate, UserResponse, UserInDB
from app.services.user_service import user_service
from app.middleware.auth import require_auth, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", response_model=UserResponse)
async def register(user_in: UserCreate):
    return await user_service.register_user(user_in)


@router.post("/login")
async def login(req: LoginRequest):
    res = await user_service.authenticate_user(req.email, req.password)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    return res


@router.get("/me", response_model=UserResponse)
async def get_me(user: UserInDB = Depends(require_auth)):
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at
    )
