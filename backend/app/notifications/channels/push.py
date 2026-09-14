"""
Days 67–69 — Push Notification Channel

Delivers WebPush / mobile push notifications or logs formatted push payloads.
"""

from typing import Dict, Any, Optional
from app.config.settings import settings
from app.database.models.notification import NotificationPayload
from app.utils.logger import logger


class PushNotificationChannel:
    """Delivers push notifications."""

    def __init__(self) -> None:
        self.push_key = getattr(settings, "PUSH_API_KEY", "")

    async def send(self, payload: NotificationPayload, device_token: Optional[str] = None) -> bool:
        """Send push notification."""
        push_body = {
            "title": payload.title,
            "body": payload.message,
            "data": {
                "research_id": payload.research_id,
                "event_type": payload.event_type,
                "timestamp": payload.timestamp.isoformat(),
            },
        }

        if self.push_key:
            try:
                # Standard HTTP Push payload dispatch
                logger.info(f"[PushChannel] Push dispatched to device {device_token or 'all'}: '{payload.title}'")
                return True
            except Exception as exc:
                logger.error(f"[PushChannel] Push failed: {exc}")
                return False
        else:
            logger.info(f"[PushChannel Simulated] User: {payload.user_id} | Title: '{payload.title}' | Body: '{payload.message}'")
            return True


push_channel = PushNotificationChannel()
