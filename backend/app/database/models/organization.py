from datetime import datetime
from typing import Optional, List, Dict, Set
from pydantic import BaseModel, Field

from app.utils.helpers import generate_uuid, get_utc_now


class OrganizationRole:
    ADMIN = "admin"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    VIEWER = "viewer"

    ALL = {ADMIN, RESEARCHER, ANALYST, VIEWER}


class Permission:
    MANAGE_ORG = "org:manage"
    MANAGE_MEMBERS = "org:members:manage"
    MANAGE_TEAMS = "org:teams:manage"
    CREATE_RESEARCH = "research:create"
    READ_RESEARCH = "research:read"
    DELETE_RESEARCH = "research:delete"
    COMPARE_RESEARCH = "research:compare"
    EXPORT_REPORTS = "reports:export"


ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    OrganizationRole.ADMIN: {
        Permission.MANAGE_ORG,
        Permission.MANAGE_MEMBERS,
        Permission.MANAGE_TEAMS,
        Permission.CREATE_RESEARCH,
        Permission.READ_RESEARCH,
        Permission.DELETE_RESEARCH,
        Permission.COMPARE_RESEARCH,
        Permission.EXPORT_REPORTS,
    },
    OrganizationRole.RESEARCHER: {
        Permission.MANAGE_TEAMS,
        Permission.CREATE_RESEARCH,
        Permission.READ_RESEARCH,
        Permission.COMPARE_RESEARCH,
        Permission.EXPORT_REPORTS,
    },
    OrganizationRole.ANALYST: {
        Permission.READ_RESEARCH,
        Permission.COMPARE_RESEARCH,
        Permission.EXPORT_REPORTS,
    },
    OrganizationRole.VIEWER: {
        Permission.READ_RESEARCH,
    },
}


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


class Team(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    organization_id: str
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TeamMember(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    team_id: str
    user_id: str
    role: str = OrganizationRole.VIEWER
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class TeamMemberCreate(BaseModel):
    user_id: str
    role: str = OrganizationRole.VIEWER


class TeamMemberResponse(BaseModel):
    membership: TeamMember
    user_email: Optional[str] = None
    user_name: Optional[str] = None


class TeamResponse(BaseModel):
    team: Team
    members_count: int = 0
