"""
Days 67–69 — Notification Data Models

Supported Channels: email, in_app, push, webhook
Supported Events: research_started, research_completed, research_failed
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class NotificationChannel(str, Enum):
    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"
    WEBHOOK = "webhook"


class NotificationEventType(str, Enum):
    RESEARCH_STARTED = "research_started"
    RESEARCH_COMPLETED = "research_completed"
    RESEARCH_FAILED = "research_failed"


class InAppNotification(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    research_id: Optional[str] = None
    event_type: str
    title: str
    message: str
    read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump(mode="json")
        return d


class WebhookConfig(BaseModel):
    user_id: str
    url: str
    secret: Optional[str] = None
    enabled: bool = True
    events: List[str] = Field(
        default_factory=lambda: [
            NotificationEventType.RESEARCH_STARTED.value,
            NotificationEventType.RESEARCH_COMPLETED.value,
            NotificationEventType.RESEARCH_FAILED.value,
        ]
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationPayload(BaseModel):
    event_type: str
    user_id: str
    research_id: str
    title: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
