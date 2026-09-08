from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from app.utils.helpers import generate_uuid, get_utc_now


class UserRole:
    USER = "user"
    ADMIN = "admin"


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str = UserRole.USER
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserInDB(UserBase):
    id: str = Field(default_factory=generate_uuid)
    hashed_password: str
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class UserResponse(UserBase):
    id: str
    created_at: datetime
