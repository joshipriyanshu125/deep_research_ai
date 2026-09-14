"""
Days 67–69 — Notification Service & Event Listener

Orchestrates multi-channel notification dispatch (Email, In-App, Push, Webhook)
for research lifecycle events:
  - research_started
  - research_completed
  - research_failed
"""

import asyncio
from typing import Any, Dict, List, Optional
from app.database.models.notification import (
    NotificationChannel,
    NotificationEventType,
    NotificationPayload,
    InAppNotification,
    WebhookConfig,
)
from app.notifications.channels.email import email_channel
from app.notifications.channels.in_app import in_app_channel
from app.notifications.channels.push import push_channel
from app.notifications.channels.webhook import webhook_channel
from app.research.events import (
    RESEARCH_STARTED,
    REPORT_COMPLETED,
    RESEARCH_FAILED,
    research_event_bus,
)
from app.utils.logger import logger


class NotificationService:
    """Central service managing multi-channel notification dispatch."""

    def __init__(self) -> None:
        self._is_listening = False

    async def dispatch(self, payload: NotificationPayload) -> Dict[str, bool]:
        """
        Dispatch notification across all 4 channels in parallel.
        Returns channel delivery status dictionary.
        """
        results = {}

        # 1. In-App Notification (Always stored)
        try:
            await in_app_channel.send(payload)
            results[NotificationChannel.IN_APP.value] = True
        except Exception as exc:
            logger.error(f"[NotificationService] In-App dispatch error: {exc}")
            results[NotificationChannel.IN_APP.value] = False

        # 2. Email Notification
        try:
            results[NotificationChannel.EMAIL.value] = await email_channel.send(payload)
        except Exception as exc:
            logger.error(f"[NotificationService] Email dispatch error: {exc}")
            results[NotificationChannel.EMAIL.value] = False

        # 3. Push Notification
        try:
            results[NotificationChannel.PUSH.value] = await push_channel.send(payload)
        except Exception as exc:
            logger.error(f"[NotificationService] Push dispatch error: {exc}")
            results[NotificationChannel.PUSH.value] = False

        # 4. Webhook Notification
        try:
            results[NotificationChannel.WEBHOOK.value] = await webhook_channel.send(payload)
        except Exception as exc:
            logger.error(f"[NotificationService] Webhook dispatch error: {exc}")
            results[NotificationChannel.WEBHOOK.value] = False

        logger.info(
            f"[NotificationService] Dispatched '{payload.event_type}' for research {payload.research_id}: {results}"
        )
        return results

    # -----------------------------------------------------------------------
    # Lifecycle Event Methods
    # -----------------------------------------------------------------------

    async def notify_research_started(self, user_id: str, research_id: str, query: str) -> Dict[str, bool]:
        """Dispatch research_started notification."""
        payload = NotificationPayload(
            event_type=NotificationEventType.RESEARCH_STARTED.value,
            user_id=user_id,
            research_id=research_id,
            title="Research Started",
            message=f"Deep research has started for query: '{query}'",
            data={"query": query},
        )
        return await self.dispatch(payload)

    async def notify_research_complete(
        self, user_id: str, research_id: str, title: str
    ) -> Dict[str, bool]:
        """Dispatch research_completed notification."""
        payload = NotificationPayload(
            event_type=NotificationEventType.RESEARCH_COMPLETED.value,
            user_id=user_id,
            research_id=research_id,
            title="Research Completed",
            message=f"Your deep research report '{title}' is now ready for review.",
            data={"report_title": title},
        )
        return await self.dispatch(payload)

    async def notify_error(
        self, user_id: str, research_id: str, error: str
    ) -> Dict[str, bool]:
        """Dispatch research_failed notification."""
        payload = NotificationPayload(
            event_type=NotificationEventType.RESEARCH_FAILED.value,
            user_id=user_id,
            research_id=research_id,
            title="Research Failed",
            message=f"Research job {research_id} failed: {error}",
            data={"error": error},
        )
        return await self.dispatch(payload)

    # -----------------------------------------------------------------------
    # Event Bus Subscription Listener
    # -----------------------------------------------------------------------

    def handle_event(self, event_data: Dict[str, Any]) -> None:
        """Handle research_event_bus events synchronously/async task."""
        event_name = event_data.get("event")
        job_id = event_data.get("job_id", "unknown")
        user_id = event_data.get("data", {}).get("user_id", "anonymous")

        if event_name == RESEARCH_STARTED:
            query = event_data.get("data", {}).get("query", "Deep Research Task")
            asyncio.create_task(self.notify_research_started(user_id, job_id, query))
        elif event_name == REPORT_COMPLETED:
            report_title = event_data.get("data", {}).get("message", "Deep Research Report")
            asyncio.create_task(self.notify_research_complete(user_id, job_id, report_title))
        elif event_name == RESEARCH_FAILED:
            err_msg = event_data.get("data", {}).get("error", "Unknown error")
            asyncio.create_task(self.notify_error(user_id, job_id, err_msg))


notification_service = NotificationService()
