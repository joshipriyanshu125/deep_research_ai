from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status

from app.database.models.organization import (
    Organization,
    OrganizationMember,
    OrganizationRole,
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

    @staticmethod
    def validate_role(role: str) -> str:
        if role not in OrganizationRole.ALL:
            raise HTTPException(status_code=422, detail=f"Invalid organization role: {role}")
        return role

    async def add_member(
        self, organization_id: str, actor_id: str, user_id: str, role: str
    ) -> OrganizationMember:
        self.validate_role(role)
        await self.require_manager(organization_id, actor_id)
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


organization_service = OrganizationService()
