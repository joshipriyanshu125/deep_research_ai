"""
Days 67–69 — In-App Notification Channel

Stores in-app notifications in MongoDB / memory for query and mark-as-read operations.
"""

from typing import Any, Dict, List, Optional
from app.database.models.notification import InAppNotification, NotificationPayload
from app.database.mongodb import db_manager
from app.utils.logger import logger

# In-memory storage fallback when MongoDB is offline
IN_APP_STORE: List[InAppNotification] = []


class InAppNotificationChannel:
    """Delivers in-app notifications and manages read status."""

    async def send(self, payload: NotificationPayload) -> InAppNotification:
        notification = InAppNotification(
            user_id=payload.user_id,
            research_id=payload.research_id,
            event_type=payload.event_type,
            title=payload.title,
            message=payload.message,
            metadata=payload.data,
        )

        if db_manager.db is not None:
            try:
                await db_manager.db["notifications"].insert_one(notification.model_dump(mode="json"))
            except Exception as exc:
                logger.warning(f"[InAppChannel] DB write failed, falling back to memory: {exc}")
                IN_APP_STORE.append(notification)
        else:
            IN_APP_STORE.append(notification)

        logger.info(f"[InAppChannel] Notification created for user {payload.user_id}: '{payload.title}'")
        return notification

    async def list_user_notifications(
        self, user_id: str, unread_only: bool = False, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List notifications for a user."""
        if db_manager.db is not None:
            try:
                query: Dict[str, Any] = {"user_id": user_id}
                if unread_only:
                    query["read"] = False
                cursor = db_manager.db["notifications"].find(query).sort("created_at", -1).limit(limit)
                docs = await cursor.to_list(length=limit)
                for d in docs:
                    d.pop("_id", None)
                return docs
            except Exception as exc:
                logger.warning(f"[InAppChannel] DB query failed, using memory fallback: {exc}")

        # In-memory fallback
        results = [
            n.to_dict() for n in IN_APP_STORE
            if n.user_id == user_id and (not unread_only or not n.read)
        ]
        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results[:limit]

    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Mark notification as read."""
        if db_manager.db is not None:
            try:
                res = await db_manager.db["notifications"].update_one(
                    {"id": notification_id, "user_id": user_id},
                    {"$set": {"read": True}},
                )
                if res.modified_count > 0 or res.matched_count > 0:
                    return True
            except Exception as exc:
                logger.warning(f"[InAppChannel] DB update failed: {exc}")

        # In-memory fallback
        for n in IN_APP_STORE:
            if n.id == notification_id and n.user_id == user_id:
                n.read = True
                return True
        return False

    async def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications for user as read."""
        count = 0
        if db_manager.db is not None:
            try:
                res = await db_manager.db["notifications"].update_many(
                    {"user_id": user_id, "read": False},
                    {"$set": {"read": True}},
                )
                count = res.modified_count
            except Exception as exc:
                logger.warning(f"[InAppChannel] DB batch update failed: {exc}")

        for n in IN_APP_STORE:
            if n.user_id == user_id and not n.read:
                n.read = True
                count += 1
        return count


in_app_channel = InAppNotificationChannel()
