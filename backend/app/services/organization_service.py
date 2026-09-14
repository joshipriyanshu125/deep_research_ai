from datetime import datetime, timezone
from typing import List, Optional, Set

from fastapi import HTTPException, status

from app.database.models.organization import (
    Organization,
    OrganizationMember,
    OrganizationRole,
    Permission,
    ROLE_PERMISSIONS,
    Team,
    TeamMember,
)
from app.database.repositories.organization_repo import organization_repo


class OrganizationService:
    async def create(self, name: str, owner_id: str) -> Organization:
        organization = await organization_repo.create_organization(
            Organization(name=name.strip(), owner_id=owner_id)
        )
        await organization_repo.add_member(
            OrganizationMember(
                organization_id=organization.id,
                user_id=owner_id,
                role=OrganizationRole.ADMIN,
            )
        )
        return organization

    async def require_manager(self, organization_id: str, user_id: str) -> OrganizationMember:
        member = await organization_repo.get_member(organization_id, user_id)
        if not member or member.role != OrganizationRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin access required")
        return member

    async def require_member(self, organization_id: str, user_id: str) -> OrganizationMember:
        member = await organization_repo.get_member(organization_id, user_id)
        if not member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization membership required")
        return member

    async def get_user_permissions(self, organization_id: str, user_id: str) -> Set[str]:
        member = await organization_repo.get_member(organization_id, user_id)
        if not member:
            return set()
        return ROLE_PERMISSIONS.get(member.role, set())

    async def has_permission(self, organization_id: str, user_id: str, permission: str) -> bool:
        permissions = await self.get_user_permissions(organization_id, user_id)
        return permission in permissions

    async def require_permission(self, organization_id: str, user_id: str, permission: str) -> OrganizationMember:
        member = await organization_repo.get_member(organization_id, user_id)
        if not member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization membership required")
        perms = ROLE_PERMISSIONS.get(member.role, set())
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required for role '{member.role}'",
            )
        return member

    @staticmethod
    def validate_role(role: str) -> str:
        if role not in OrganizationRole.ALL:
            raise HTTPException(status_code=422, detail=f"Invalid organization role: {role}")
        return role

    async def add_member(
        self, organization_id: str, actor_id: str, user_id: str, role: str
    ) -> OrganizationMember:
        self.validate_role(role)
        await self.require_permission(organization_id, actor_id, Permission.MANAGE_MEMBERS)
        existing = await organization_repo.get_member(organization_id, user_id)
        member = existing or OrganizationMember(organization_id=organization_id, user_id=user_id)
        member.role = role
        member.updated_at = datetime.now(timezone.utc)
        return await organization_repo.update_member(member) if existing else await organization_repo.add_member(member)

    async def update_member(self, organization_id: str, target_user_id: str, role: str) -> OrganizationMember:
        self.validate_role(role)
        member = await organization_repo.get_member(organization_id, target_user_id)
        if not member:
            raise HTTPException(status_code=404, detail="Organization member not found")
        member.role = role
        member.updated_at = datetime.now(timezone.utc)
        return await organization_repo.update_member(member)

    # Teams logic
    async def create_team(self, organization_id: str, actor_id: str, name: str, description: Optional[str] = None) -> Team:
        await self.require_permission(organization_id, actor_id, Permission.MANAGE_TEAMS)
        team = Team(organization_id=organization_id, name=name.strip(), description=description)
        created_team = await organization_repo.create_team(team)
        # Add creator as team admin/member
        await organization_repo.add_team_member(
            TeamMember(team_id=created_team.id, user_id=actor_id, role=OrganizationRole.ADMIN)
        )
        return created_team

    async def list_teams(self, organization_id: str, actor_id: str) -> List[Team]:
        await self.require_member(organization_id, actor_id)
        return await organization_repo.list_teams(organization_id)

    async def get_team(self, organization_id: str, team_id: str, actor_id: str) -> Team:
        await self.require_member(organization_id, actor_id)
        team = await organization_repo.get_team(team_id)
        if not team or team.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Team not found")
        return team

    async def add_team_member(self, organization_id: str, team_id: str, actor_id: str, user_id: str, role: str = OrganizationRole.VIEWER) -> TeamMember:
        await self.require_permission(organization_id, actor_id, Permission.MANAGE_TEAMS)
        team = await self.get_team(organization_id, team_id, actor_id)
        # Target user must be part of organization
        await self.require_member(organization_id, user_id)
        self.validate_role(role)
        existing = await organization_repo.get_team_member(team_id, user_id)
        if existing:
            existing.role = role
            existing.updated_at = datetime.now(timezone.utc)
            return existing
        member = TeamMember(team_id=team_id, user_id=user_id, role=role)
        return await organization_repo.add_team_member(member)

    async def list_team_members(self, organization_id: str, team_id: str, actor_id: str) -> List[TeamMember]:
        await self.get_team(organization_id, team_id, actor_id)
        return await organization_repo.list_team_members(team_id)

    async def remove_team_member(self, organization_id: str, team_id: str, actor_id: str, target_user_id: str) -> bool:
        await self.require_permission(organization_id, actor_id, Permission.MANAGE_TEAMS)
        await self.get_team(organization_id, team_id, actor_id)
        return await organization_repo.remove_team_member(team_id, target_user_id)


organization_service = OrganizationService()
