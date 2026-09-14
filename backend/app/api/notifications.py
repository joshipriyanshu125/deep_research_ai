"""
Days 67–69 — Notification API Router

Endpoints
---------
GET  /notifications               — List user's in-app notifications
PUT  /notifications/{id}/read      — Mark notification as read
POST /notifications/read-all      — Mark all notifications as read
GET  /notifications/webhook       — Get user webhook config
POST /notifications/webhook       — Set user webhook config
POST /notifications/test          — Send test notification across all channels
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl

from app.database.models.notification import (
    NotificationChannel,
    NotificationEventType,
    NotificationPayload,
    WebhookConfig,
)
from app.database.models.user import UserInDB
from app.middleware.auth import require_auth
from app.notifications.channels.in_app import in_app_channel
from app.notifications.channels.webhook import webhook_channel
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class WebhookConfigRequest(BaseModel):
    url: str
    secret: Optional[str] = None
    enabled: bool = True
    events: Optional[List[str]] = None


class TestNotificationRequest(BaseModel):
    event_type: str = NotificationEventType.RESEARCH_COMPLETED.value
    title: str = "Test Notification"
    message: str = "This is a test notification sent across all configured channels."
    research_id: str = "test_research_123"


@router.get("", response_model=List[Dict[str, Any]])
async def list_notifications(
    unread_only: bool = Query(False, description="Filter to unread notifications only"),
    limit: int = Query(50, ge=1, le=200, description="Max notifications to return"),
    current_user: UserInDB = Depends(require_auth),
):
    """List in-app notifications for the authenticated user."""
    return await in_app_channel.list_user_notifications(
        user_id=current_user.id, unread_only=unread_only, limit=limit
    )


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: UserInDB = Depends(require_auth),
):
    """Mark a specific in-app notification as read."""
    success = await in_app_channel.mark_as_read(notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "success", "message": "Notification marked as read"}


@router.post("/read-all")
async def mark_all_notifications_read(
    current_user: UserInDB = Depends(require_auth),
):
    """Mark all in-app notifications for the user as read."""
    count = await in_app_channel.mark_all_as_read(current_user.id)
    return {"status": "success", "marked_read_count": count}


@router.get("/webhook", response_model=Optional[WebhookConfig])
async def get_webhook_config(
    current_user: UserInDB = Depends(require_auth),
):
    """Get the authenticated user's webhook configuration."""
    config = await webhook_channel.get_user_webhook_config(current_user.id)
    if not config:
        return WebhookConfig(user_id=current_user.id, url="", enabled=False)
    return config


@router.post("/webhook", response_model=WebhookConfig)
async def configure_webhook(
    req: WebhookConfigRequest,
    current_user: UserInDB = Depends(require_auth),
):
    """Create or update user webhook configuration."""
    events = req.events or [
        NotificationEventType.RESEARCH_STARTED.value,
        NotificationEventType.RESEARCH_COMPLETED.value,
        NotificationEventType.RESEARCH_FAILED.value,
    ]

    config = WebhookConfig(
        user_id=current_user.id,
        url=req.url,
        secret=req.secret,
        enabled=req.enabled,
        events=events,
    )
    return await webhook_channel.save_user_webhook_config(config)


@router.post("/test")
async def send_test_notification(
    req: TestNotificationRequest,
    current_user: UserInDB = Depends(require_auth),
):
    """Send a test notification across email, in-app, push, and webhook channels."""
    payload = NotificationPayload(
        event_type=req.event_type,
        user_id=current_user.id,
        research_id=req.research_id,
        title=req.title,
        message=req.message,
    )

    results = await notification_service.dispatch(payload)
    return {
        "status": "completed",
        "user_id": current_user.id,
        "channels": results,
    }
