from typing import Dict, List
from app.database.mongodb import db_manager
from app.database.models.feedback import ReportFeedback


class FeedbackRepository:
    def __init__(self) -> None:
        self._items: Dict[str, List[ReportFeedback]] = {}

    async def create(self, feedback: ReportFeedback) -> ReportFeedback:
        if db_manager.is_connected:
            await db_manager.db.feedback.insert_one(feedback.model_dump(mode="json"))
        else:
            self._items.setdefault(feedback.report_id, []).append(feedback)
        return feedback

    async def list_by_report(self, report_id: str, limit: int = 100) -> List[ReportFeedback]:
        if db_manager.is_connected:
            cursor = db_manager.db.feedback.find({"report_id": report_id}).sort("created_at", -1).limit(limit)
            return [ReportFeedback(**doc) async for doc in cursor]
        return self._items.get(report_id, [])[:limit]


feedback_repo = FeedbackRepository()
