"""
Tests for Days 67–69 — Multi-Channel Notification System
"""

import pytest
import hmac
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.database.models.notification import (
    NotificationChannel,
    NotificationEventType,
    NotificationPayload,
    WebhookConfig,
)
from app.notifications.channels.email import email_channel
from app.notifications.channels.in_app import in_app_channel, IN_APP_STORE
from app.notifications.channels.push import push_channel
from app.notifications.channels.webhook import webhook_channel
from app.services.notification_service import notification_service


@pytest.fixture(autouse=True)
def clear_stores():
    IN_APP_STORE.clear()
    yield
    IN_APP_STORE.clear()


@pytest.mark.asyncio
async def test_email_channel_simulation():
    payload = NotificationPayload(
        event_type=NotificationEventType.RESEARCH_COMPLETED.value,
        user_id="user_123",
        research_id="res_001",
        title="Research Completed",
        message="Your report is ready.",
    )
    result = await email_channel.send(payload, recipient_email="test@example.com")
    assert result is True


@pytest.mark.asyncio
async def test_email_channel_requires_a_recipient_address():
    payload = NotificationPayload(
        event_type=NotificationEventType.RESEARCH_COMPLETED.value,
        user_id="user_123",
        research_id="res_001",
        title="Research Completed",
        message="Your report is ready.",
    )

    result = await email_channel.send(payload)

    assert result is False


@pytest.mark.asyncio
async def test_in_app_channel_flow():
    payload = NotificationPayload(
        event_type=NotificationEventType.RESEARCH_STARTED.value,
        user_id="user_456",
        research_id="res_002",
        title="Research Started",
        message="Deep research started.",
    )
    notification = await in_app_channel.send(payload)
    assert notification.user_id == "user_456"
    assert notification.read is False

    # List notifications
    items = await in_app_channel.list_user_notifications("user_456")
    assert len(items) == 1
    assert items[0]["title"] == "Research Started"

    # Mark as read
    success = await in_app_channel.mark_as_read(notification.id, "user_456")
    assert success is True

    # Check unread filter
    unread_items = await in_app_channel.list_user_notifications("user_456", unread_only=True)
    assert len(unread_items) == 0


@pytest.mark.asyncio
async def test_push_channel_simulation():
    payload = NotificationPayload(
        event_type=NotificationEventType.RESEARCH_FAILED.value,
        user_id="user_789",
        research_id="res_003",
        title="Research Failed",
        message="Job failed due to timeout.",
    )
    result = await push_channel.send(payload)
    assert result is True


@pytest.mark.asyncio
async def test_webhook_channel_hmac_signing():
    config = WebhookConfig(
        user_id="user_webhook",
        url="https://example.com/webhook",
        secret="my_secret_key",
        enabled=True,
    )
    await webhook_channel.save_user_webhook_config(config)

    payload = NotificationPayload(
        event_type=NotificationEventType.RESEARCH_COMPLETED.value,
        user_id="user_webhook",
        research_id="res_004",
        title="Research Completed",
        message="Report generated.",
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        result = await webhook_channel.send(payload)
        assert result is True

        # Verify call headers contain HMAC signature
        call_kwargs = mock_post.call_args.kwargs
        headers = call_kwargs["headers"]
        assert "X-Hub-Signature-256" in headers
        assert headers["X-Hub-Signature-256"].startswith("sha256=")


@pytest.mark.asyncio
async def test_notification_service_dispatch():
    payload = NotificationPayload(
        event_type=NotificationEventType.RESEARCH_STARTED.value,
        user_id="user_all",
        research_id="res_005",
        title="Research Started",
        message="Started query processing.",
    )
    registered_user = MagicMock(email="registered.user@example.org")
    with patch(
        "app.services.notification_service.user_repo.get_by_id",
        new_callable=AsyncMock,
        return_value=registered_user,
    ), patch(
        "app.services.notification_service.email_channel.send",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_send:
        results = await notification_service.dispatch(payload)

    mock_send.assert_awaited_once_with(payload, recipient_email="registered.user@example.org")
    assert results[NotificationChannel.IN_APP.value] is True
    assert results[NotificationChannel.EMAIL.value] is True
    assert results[NotificationChannel.PUSH.value] is True
