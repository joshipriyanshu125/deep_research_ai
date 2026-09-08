from app.utils.logger import logger


class NotificationService:
    async def notify_research_complete(self, user_id: str, research_id: str, title: str):
        logger.info(f"Notification sent to user {user_id}: Research '{title}' (ID: {research_id}) completed.")

    async def notify_error(self, user_id: str, research_id: str, error: str):
        logger.error(f"Notification sent to user {user_id}: Research {research_id} failed with error: {error}")


notification_service = NotificationService()
