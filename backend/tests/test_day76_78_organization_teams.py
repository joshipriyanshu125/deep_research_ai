"""
Tests for Day 76–78 — Team & Organization Support (SaaS Functionality)
"""

import pytest
from fastapi import HTTPException
from app.database.models.organization import (
    Organization,
    OrganizationRole,
    Permission,
    ROLE_PERMISSIONS,
    Team,
    TeamMember,
)
from app.database.models.user import UserInDB
from app.database.repositories.organization_repo import organization_repo
from app.database.repositories.user_repo import user_repo
from app.services.organization_service import organization_service


@pytest.fixture(autouse=True)
def clear_stores():
    organization_repo._organizations.clear()
    organization_repo._members.clear()
    organization_repo._teams.clear()
    organization_repo._team_members.clear()
    user_repo._memory_users.clear()
    yield
    organization_repo._organizations.clear()
    organization_repo._members.clear()
    organization_repo._teams.clear()
    organization_repo._team_members.clear()
    user_repo._memory_users.clear()


@pytest.mark.asyncio
async def test_organization_and_role_permissions():
    owner_id = "user_admin_01"
    
    # 1. Create Organization
    org = await organization_service.create("Acme Intelligence", owner_id=owner_id)
    assert org.id is not None
    assert org.name == "Acme Intelligence"
    assert org.owner_id == owner_id

    # Check creator is Admin
    owner_member = await organization_repo.get_member(org.id, owner_id)
    assert owner_member is not None
    assert owner_member.role == OrganizationRole.ADMIN

    # Check permissions
    owner_perms = await organization_service.get_user_permissions(org.id, owner_id)
    assert Permission.MANAGE_ORG in owner_perms
    assert Permission.MANAGE_TEAMS in owner_perms
    assert Permission.CREATE_RESEARCH in owner_perms

    # 2. Add Researcher and Viewer members
    researcher_user = UserInDB(id="user_res_02", email="res@acme.com", hashed_password="pw")
    viewer_user = UserInDB(id="user_view_03", email="view@acme.com", hashed_password="pw")
    await user_repo.create(researcher_user)
    await user_repo.create(viewer_user)

    await organization_service.add_member(org.id, actor_id=owner_id, user_id=researcher_user.id, role=OrganizationRole.RESEARCHER)
    await organization_service.add_member(org.id, actor_id=owner_id, user_id=viewer_user.id, role=OrganizationRole.VIEWER)

    # Verify Researcher permissions
    res_perms = await organization_service.get_user_permissions(org.id, researcher_user.id)
    assert Permission.CREATE_RESEARCH in res_perms
    assert Permission.MANAGE_ORG not in res_perms

    # Verify Viewer permissions
    view_perms = await organization_service.get_user_permissions(org.id, viewer_user.id)
    assert Permission.READ_RESEARCH in view_perms
    assert Permission.CREATE_RESEARCH not in view_perms
    assert Permission.MANAGE_TEAMS not in view_perms

    # Permission check requirement tests
    await organization_service.require_permission(org.id, owner_id, Permission.MANAGE_ORG)
    with pytest.raises(HTTPException) as exc_info:
        await organization_service.require_permission(org.id, viewer_user.id, Permission.CREATE_RESEARCH)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_team_creation_and_member_management():
    owner_id = "user_admin_10"
    org = await organization_service.create("DeepTech Labs", owner_id=owner_id)

    res_user = UserInDB(id="user_res_11", email="analyst@deeptech.com", hashed_password="pw")
    await user_repo.create(res_user)
    await organization_service.add_member(org.id, actor_id=owner_id, user_id=res_user.id, role=OrganizationRole.ANALYST)

    # 1. Create Team
    team = await organization_service.create_team(
        organization_id=org.id,
        actor_id=owner_id,
        name="Quantum Computing Team",
        description="Focus on qubit architectures and error mitigation",
    )
    assert team.id is not None
    assert team.organization_id == org.id
    assert team.name == "Quantum Computing Team"

    # 2. Add Team Member
    team_member = await organization_service.add_team_member(
        organization_id=org.id,
        team_id=team.id,
        actor_id=owner_id,
        user_id=res_user.id,
        role=OrganizationRole.ANALYST,
    )
    assert team_member.team_id == team.id
    assert team_member.user_id == res_user.id

    # 3. List Teams & Team Members
    teams = await organization_service.list_teams(org.id, actor_id=owner_id)
    assert len(teams) == 1

    members = await organization_service.list_team_members(org.id, team.id, actor_id=owner_id)
    assert len(members) == 2  # Creator (Admin) + added Analyst

    # 4. Remove Team Member
    removed = await organization_service.remove_team_member(org.id, team.id, owner_id, res_user.id)
    assert removed is True

    members_after = await organization_service.list_team_members(org.id, team.id, actor_id=owner_id)
    assert len(members_after) == 1
