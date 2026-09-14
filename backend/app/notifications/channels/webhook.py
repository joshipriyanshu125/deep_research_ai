"""
Days 67–69 — Webhook Notification Channel

Posts HTTP POST JSON payloads to user-configured webhook endpoints,
supporting HMAC-SHA256 signatures for signature verification.
"""

import hmac
import hashlib
import json
from typing import Any, Dict, List, Optional
import httpx

from app.database.models.notification import NotificationPayload, WebhookConfig
from app.database.mongodb import db_manager
from app.utils.logger import logger

# In-memory webhook configuration store fallback
WEBHOOK_CONFIG_STORE: Dict[str, WebhookConfig] = {}


class WebhookNotificationChannel:
    """Delivers webhook notifications to configured external URLs."""

    async def get_user_webhook_config(self, user_id: str) -> Optional[WebhookConfig]:
        """Fetch user webhook configuration."""
        if db_manager.db is not None:
            try:
                doc = await db_manager.db["webhook_configs"].find_one({"user_id": user_id})
                if doc:
                    doc.pop("_id", None)
                    return WebhookConfig(**doc)
            except Exception as exc:
                logger.warning(f"[WebhookChannel] Failed fetching webhook config from DB: {exc}")

        return WEBHOOK_CONFIG_STORE.get(user_id)

    async def save_user_webhook_config(self, config: WebhookConfig) -> WebhookConfig:
        """Save user webhook configuration."""
        if db_manager.db is not None:
            try:
                await db_manager.db["webhook_configs"].update_one(
                    {"user_id": config.user_id},
                    {"$set": config.model_dump(mode="json")},
                    upsert=True,
                )
            except Exception as exc:
                logger.warning(f"[WebhookChannel] Failed saving webhook config to DB: {exc}")

        WEBHOOK_CONFIG_STORE[config.user_id] = config
        logger.info(f"[WebhookChannel] Saved webhook config for user {config.user_id}: {config.url}")
        return config

    async def send(self, payload: NotificationPayload, target_url: Optional[str] = None) -> bool:
        """Post webhook payload to URL."""
        config = await self.get_user_webhook_config(payload.user_id)
        url = target_url or (config.url if config and config.enabled else None)

        if not url:
            logger.debug(f"[WebhookChannel] No active webhook URL for user {payload.user_id}")
            return False

        # Check if event is enabled in user config
        if config and config.events and payload.event_type not in config.events:
            logger.debug(f"[WebhookChannel] Event '{payload.event_type}' not enabled for user {payload.user_id}")
            return False

        body_dict = {
            "event": payload.event_type,
            "user_id": payload.user_id,
            "research_id": payload.research_id,
            "title": payload.title,
            "message": payload.message,
            "data": payload.data,
            "timestamp": payload.timestamp.isoformat(),
        }

        body_json = json.dumps(body_dict, sort_keys=True)
        headers = {"Content-Type": "application/json", "User-Agent": "DeepResearchAI-Webhook/1.0"}

        secret = config.secret if config else None
        if secret:
            signature = hmac.new(
                secret.encode("utf-8"),
                body_json.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            headers["X-Hub-Signature-256"] = f"sha256={signature}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, content=body_json, headers=headers)
                if response.status_code < 300:
                    logger.info(f"[WebhookChannel] Webhook delivered to {url} ({response.status_code})")
                    return True
                else:
                    logger.warning(f"[WebhookChannel] Webhook return status {response.status_code} from {url}")
                    return False
        except Exception as exc:
            logger.warning(f"[WebhookChannel] Webhook delivery to {url} failed: {exc}")
            return False


webhook_channel = WebhookNotificationChannel()
