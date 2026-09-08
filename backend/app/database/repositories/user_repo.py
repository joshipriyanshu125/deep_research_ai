from typing import Optional, List, Dict
from app.database.mongodb import db_manager
from app.database.models.user import UserInDB


class UserRepository:
    def __init__(self):
        self._memory_users: Dict[str, UserInDB] = {}

    async def create(self, user: UserInDB) -> UserInDB:
        if db_manager.is_connected:
            await db_manager.db.users.insert_one(user.model_dump())
        else:
            self._memory_users[user.id] = user
        return user

    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        if db_manager.is_connected:
            doc = await db_manager.db.users.find_one({"email": email})
            return UserInDB(**doc) if doc else None
        for u in self._memory_users.values():
            if u.email == email:
                return u
        return None

    async def get_by_id(self, user_id: str) -> Optional[UserInDB]:
        if db_manager.is_connected:
            doc = await db_manager.db.users.find_one({"id": user_id})
            return UserInDB(**doc) if doc else None
        return self._memory_users.get(user_id)

    async def list_all(self, limit: int = 100) -> List[UserInDB]:
        if db_manager.is_connected:
            cursor = db_manager.db.users.find().limit(limit)
            return [UserInDB(**doc) async for doc in cursor]
        return list(self._memory_users.values())[:limit]


user_repo = UserRepository()
