from typing import Dict, List, Optional

from app.database.models.organization import Organization, OrganizationMember
from app.database.mongodb import db_manager


class OrganizationRepository:
    def __init__(self):
        self._organizations: Dict[str, Organization] = {}
        self._members: Dict[str, OrganizationMember] = {}

    async def create_organization(self, organization: Organization) -> Organization:
        if db_manager.is_connected:
            await db_manager.db.organizations.insert_one(organization.model_dump())
        else:
            self._organizations[organization.id] = organization
        return organization

    async def get_organization(self, organization_id: str) -> Optional[Organization]:
        if db_manager.is_connected:
            doc = await db_manager.db.organizations.find_one({"id": organization_id})
            return Organization(**doc) if doc else None
        return self._organizations.get(organization_id)

    async def list_for_user(self, user_id: str, limit: int = 100) -> List[Organization]:
        memberships = await self.list_memberships_for_user(user_id, limit=limit)
        organizations = []
        for membership in memberships:
            organization = await self.get_organization(membership.organization_id)
            if organization:
                organizations.append(organization)
        return organizations

    async def add_member(self, member: OrganizationMember) -> OrganizationMember:
        if db_manager.is_connected:
            await db_manager.db.organization_members.update_one(
                {"organization_id": member.organization_id, "user_id": member.user_id},
                {"$set": member.model_dump()},
                upsert=True,
            )
        else:
            self._members[member.id] = member
        return member

    async def get_member(self, organization_id: str, user_id: str) -> Optional[OrganizationMember]:
        if db_manager.is_connected:
            doc = await db_manager.db.organization_members.find_one(
                {"organization_id": organization_id, "user_id": user_id}
            )
            return OrganizationMember(**doc) if doc else None
        return next(
            (member for member in self._members.values()
             if member.organization_id == organization_id and member.user_id == user_id),
            None,
        )

    async def list_members(self, organization_id: str) -> List[OrganizationMember]:
        if db_manager.is_connected:
            cursor = db_manager.db.organization_members.find({"organization_id": organization_id})
            return [OrganizationMember(**doc) async for doc in cursor]
        return [member for member in self._members.values() if member.organization_id == organization_id]

    async def list_memberships_for_user(self, user_id: str, limit: int = 100) -> List[OrganizationMember]:
        if db_manager.is_connected:
            cursor = db_manager.db.organization_members.find({"user_id": user_id}).limit(limit)
            return [OrganizationMember(**doc) async for doc in cursor]
        return [member for member in self._members.values() if member.user_id == user_id][:limit]

    async def update_member(self, member: OrganizationMember) -> OrganizationMember:
        if db_manager.is_connected:
            await db_manager.db.organization_members.replace_one(
                {"id": member.id}, member.model_dump()
            )
        else:
            self._members[member.id] = member
        return member

    async def remove_member(self, organization_id: str, user_id: str) -> bool:
        if db_manager.is_connected:
            result = await db_manager.db.organization_members.delete_one(
                {"organization_id": organization_id, "user_id": user_id}
            )
            return result.deleted_count > 0
        member = await self.get_member(organization_id, user_id)
        if not member:
            return False
        self._members.pop(member.id, None)
        return True


organization_repo = OrganizationRepository()
