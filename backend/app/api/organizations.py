from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.database.models.organization import (
    Organization,
    OrganizationCreate,
    OrganizationMember,
    OrganizationMemberCreate,
    OrganizationMemberResponse,
    OrganizationMemberUpdate,
    Team,
    TeamCreate,
    TeamMember,
    TeamMemberCreate,
    TeamMemberResponse,
    TeamResponse,
)
from app.database.repositories.organization_repo import organization_repo
from app.database.repositories.user_repo import user_repo
from app.database.models.user import UserInDB
from app.services.organization_service import organization_service
from app.middleware.auth import require_auth

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=Organization, status_code=201)
async def create_organization(
    request: OrganizationCreate,
    user: UserInDB = Depends(require_auth),
):
    return await organization_service.create(request.name, user.id)


@router.get("", response_model=List[Organization])
async def list_organizations(user: UserInDB = Depends(require_auth)):
    return await organization_repo.list_for_user(user.id)


@router.get("/{organization_id}", response_model=Organization)
async def get_organization(organization_id: str, user: UserInDB = Depends(require_auth)):
    await organization_service.require_member(organization_id, user.id)
    org = await organization_repo.get_organization(organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("/{organization_id}/members", response_model=List[OrganizationMemberResponse])
async def list_members(organization_id: str, user: UserInDB = Depends(require_auth)):
    await organization_service.require_member(organization_id, user.id)
    members = await organization_repo.list_members(organization_id)
    response = []
    for member in members:
        member_user = await user_repo.get_by_id(member.user_id)
        response.append(OrganizationMemberResponse(
            membership=member,
            user_email=member_user.email if member_user else None,
            user_name=member_user.full_name if member_user else None,
        ))
    return response


@router.post("/{organization_id}/members", response_model=OrganizationMember, status_code=201)
async def add_member(
    organization_id: str,
    request: OrganizationMemberCreate,
    user: UserInDB = Depends(require_auth),
):
    if not await user_repo.get_by_id(request.user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return await organization_service.add_member(
        organization_id, user.id, request.user_id, request.role
    )


@router.patch("/{organization_id}/members/{target_user_id}", response_model=OrganizationMember)
async def update_member(
    organization_id: str,
    target_user_id: str,
    request: OrganizationMemberUpdate,
    user: UserInDB = Depends(require_auth),
):
    await organization_service.require_manager(organization_id, user.id)
    return await organization_service.update_member(organization_id, target_user_id, request.role)


@router.delete("/{organization_id}/members/{target_user_id}", status_code=204)
async def remove_member(
    organization_id: str,
    target_user_id: str,
    user: UserInDB = Depends(require_auth),
):
    await organization_service.require_manager(organization_id, user.id)
    if not await organization_repo.remove_member(organization_id, target_user_id):
        raise HTTPException(status_code=404, detail="Organization member not found")


@router.get("/{organization_id}/permissions")
async def get_my_permissions(organization_id: str, user: UserInDB = Depends(require_auth)):
    perms = await organization_service.get_user_permissions(organization_id, user.id)
    return {"organization_id": organization_id, "user_id": user.id, "permissions": list(perms)}


# --- Teams Endpoints ---

@router.post("/{organization_id}/teams", response_model=Team, status_code=201)
async def create_team(
    organization_id: str,
    request: TeamCreate,
    user: UserInDB = Depends(require_auth),
):
    return await organization_service.create_team(
        organization_id=organization_id,
        actor_id=user.id,
        name=request.name,
        description=request.description,
    )


@router.get("/{organization_id}/teams", response_model=List[TeamResponse])
async def list_teams(organization_id: str, user: UserInDB = Depends(require_auth)):
    teams = await organization_service.list_teams(organization_id, user.id)
    res = []
    for team in teams:
        members = await organization_repo.list_team_members(team.id)
        res.append(TeamResponse(team=team, members_count=len(members)))
    return res


@router.get("/{organization_id}/teams/{team_id}", response_model=TeamResponse)
async def get_team(organization_id: str, team_id: str, user: UserInDB = Depends(require_auth)):
    team = await organization_service.get_team(organization_id, team_id, user.id)
    members = await organization_repo.list_team_members(team.id)
    return TeamResponse(team=team, members_count=len(members))


@router.post("/{organization_id}/teams/{team_id}/members", response_model=TeamMember, status_code=201)
async def add_team_member(
    organization_id: str,
    team_id: str,
    request: TeamMemberCreate,
    user: UserInDB = Depends(require_auth),
):
    return await organization_service.add_team_member(
        organization_id=organization_id,
        team_id=team_id,
        actor_id=user.id,
        user_id=request.user_id,
        role=request.role,
    )


@router.get("/{organization_id}/teams/{team_id}/members", response_model=List[TeamMemberResponse])
async def list_team_members(organization_id: str, team_id: str, user: UserInDB = Depends(require_auth)):
    members = await organization_service.list_team_members(organization_id, team_id, user.id)
    response = []
    for member in members:
        member_user = await user_repo.get_by_id(member.user_id)
        response.append(TeamMemberResponse(
            membership=member,
            user_email=member_user.email if member_user else None,
            user_name=member_user.full_name if member_user else None,
        ))
    return response


@router.delete("/{organization_id}/teams/{team_id}/members/{target_user_id}", status_code=204)
async def remove_team_member(
    organization_id: str,
    team_id: str,
    target_user_id: str,
    user: UserInDB = Depends(require_auth),
):
    success = await organization_service.remove_team_member(
        organization_id=organization_id,
        team_id=team_id,
        actor_id=user.id,
        target_user_id=target_user_id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Team member not found")
