from typing import Dict, List
from app.database.mongodb import db_manager
from app.database.models.observability import AgentLogRecord, ResearchEventRecord


class ObservabilityRepository:
    def __init__(self) -> None:
        self._events: Dict[str, List[ResearchEventRecord]] = {}
        self._agent_logs: Dict[str, List[AgentLogRecord]] = {}

    async def add_event(self, record: ResearchEventRecord) -> ResearchEventRecord:
        if db_manager.is_connected:
            await db_manager.db.research_events.insert_one(record.model_dump(mode="json"))
        else:
            self._events.setdefault(record.research_id, []).append(record)
        return record

    async def list_events(self, research_id: str, limit: int = 200) -> List[ResearchEventRecord]:
        if db_manager.is_connected:
            cursor = db_manager.db.research_events.find({"research_id": research_id}).sort("created_at", 1).limit(limit)
            return [ResearchEventRecord(**doc) async for doc in cursor]
        return self._events.get(research_id, [])[:limit]

    async def add_agent_log(self, record: AgentLogRecord) -> AgentLogRecord:
        if db_manager.is_connected:
            await db_manager.db.agent_logs.insert_one(record.model_dump(mode="json"))
        else:
            self._agent_logs.setdefault(record.research_id, []).append(record)
        return record

    async def list_agent_logs(self, research_id: str, limit: int = 200) -> List[AgentLogRecord]:
        if db_manager.is_connected:
            cursor = db_manager.db.agent_logs.find({"research_id": research_id}).sort("created_at", 1).limit(limit)
            return [AgentLogRecord(**doc) async for doc in cursor]
        return self._agent_logs.get(research_id, [])[:limit]


observability_repo = ObservabilityRepository()
