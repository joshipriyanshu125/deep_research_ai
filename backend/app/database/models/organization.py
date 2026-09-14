from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.utils.helpers import generate_uuid, get_utc_now


class OrganizationRole:
    ADMIN = "admin"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    VIEWER = "viewer"

    ALL = {ADMIN, RESEARCHER, ANALYST, VIEWER}


class Organization(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    name: str = Field(min_length=1, max_length=120)
    owner_id: str
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class OrganizationMember(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    organization_id: str
    user_id: str
    role: str = OrganizationRole.VIEWER
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class OrganizationMemberCreate(BaseModel):
    user_id: str
    role: str = OrganizationRole.VIEWER


class OrganizationMemberUpdate(BaseModel):
    role: str


class OrganizationMemberResponse(BaseModel):
    membership: OrganizationMember
    user_email: Optional[str] = None
    user_name: Optional[str] = None
