from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from app.database.mongodb import db_manager
from app.database.models.api_key import APIKey, APIUsageRecord, APIUsageSummary
from app.utils.helpers import get_utc_now


class APIKeyRepository:
    def __init__(self):
        self._memory_keys: Dict[str, APIKey] = {}
        self._memory_usage: List[APIUsageRecord] = []

    # -------------------------------------------------------------
    # API Key Operations
    # -------------------------------------------------------------
    async def create_key(self, api_key: APIKey) -> APIKey:
        if db_manager.is_connected:
            await db_manager.db.api_keys.insert_one(api_key.model_dump())
        else:
            self._memory_keys[api_key.id] = api_key
        return api_key

    async def get_by_id(self, key_id: str) -> Optional[APIKey]:
        if db_manager.is_connected:
            doc = await db_manager.db.api_keys.find_one({"id": key_id})
            return APIKey(**doc) if doc else None
        return self._memory_keys.get(key_id)

    async def get_by_hash(self, hashed_key: str) -> Optional[APIKey]:
        if db_manager.is_connected:
            doc = await db_manager.db.api_keys.find_one({"hashed_key": hashed_key})
            return APIKey(**doc) if doc else None
        for k in self._memory_keys.values():
            if k.hashed_key == hashed_key:
                return k
        return None

    async def get_by_prefix(self, prefix: str) -> Optional[APIKey]:
        if db_manager.is_connected:
            doc = await db_manager.db.api_keys.find_one({"key_prefix": prefix})
            return APIKey(**doc) if doc else None
        for k in self._memory_keys.values():
            if k.key_prefix == prefix:
                return k
        return None

    async def list_by_user(self, user_id: str, limit: int = 50) -> List[APIKey]:
        if db_manager.is_connected:
            cursor = db_manager.db.api_keys.find({"user_id": user_id}).limit(limit)
            return [APIKey(**doc) async for doc in cursor]
        return [k for k in self._memory_keys.values() if k.user_id == user_id][:limit]

    async def list_by_organization(self, organization_id: str, limit: int = 50) -> List[APIKey]:
        if db_manager.is_connected:
            cursor = db_manager.db.api_keys.find({"organization_id": organization_id}).limit(limit)
            return [APIKey(**doc) async for doc in cursor]
        return [k for k in self._memory_keys.values() if k.organization_id == organization_id][:limit]

    async def revoke_key(self, key_id: str) -> Optional[APIKey]:
        if db_manager.is_connected:
            doc = await db_manager.db.api_keys.find_one_and_update(
                {"id": key_id},
                {"$set": {"is_active": False, "updated_at": get_utc_now()}},
                return_document=True
            )
            return APIKey(**doc) if doc else None
        key = self._memory_keys.get(key_id)
        if key:
            key.is_active = False
            key.updated_at = get_utc_now()
        return key

    async def update_last_used(self, key_id: str) -> None:
        now = get_utc_now()
        if db_manager.is_connected:
            await db_manager.db.api_keys.update_one(
                {"id": key_id},
                {"$set": {"last_used_at": now, "updated_at": now}}
            )
        else:
            if key_id in self._memory_keys:
                self._memory_keys[key_id].last_used_at = now
                self._memory_keys[key_id].updated_at = now

    # -------------------------------------------------------------
    # Usage Tracking & Quota Telemetry
    # -------------------------------------------------------------
    async def record_usage(self, record: APIUsageRecord) -> APIUsageRecord:
        if db_manager.is_connected:
            await db_manager.db.api_usage.insert_one(record.model_dump())
        else:
            self._memory_usage.append(record)
        return record

    async def get_usage_records(
        self,
        api_key_id: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[APIUsageRecord]:
        query: Dict[str, Any] = {}
        if api_key_id:
            query["api_key_id"] = api_key_id
        if user_id:
            query["user_id"] = user_id
        if organization_id:
            query["organization_id"] = organization_id
        if since:
            query["timestamp"] = {"$gte": since}

        if db_manager.is_connected:
            cursor = db_manager.db.api_usage.find(query).sort("timestamp", -1).limit(limit)
            return [APIUsageRecord(**doc) async for doc in cursor]

        records = self._memory_usage
        if api_key_id:
            records = [r for r in records if r.api_key_id == api_key_id]
        if user_id:
            records = [r for r in records if r.user_id == user_id]
        if organization_id:
            records = [r for r in records if r.organization_id == organization_id]
        if since:
            records = [r for r in records if r.timestamp >= since]

        records = sorted(records, key=lambda r: r.timestamp, reverse=True)
        return records[:limit]

    async def get_minute_request_count(self, api_key_id: str) -> int:
        now = get_utc_now()
        one_minute_ago = now - timedelta(minutes=1)
        if db_manager.is_connected:
            count = await db_manager.db.api_usage.count_documents({
                "api_key_id": api_key_id,
                "timestamp": {"$gte": one_minute_ago}
            })
            return count
        return len([
            r for r in self._memory_usage
            if r.api_key_id == api_key_id and r.timestamp >= one_minute_ago
        ])

    async def get_monthly_usage(
        self,
        api_key_id: Optional[str] = None,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        now = get_utc_now()
        # Start of current calendar month
        start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

        if db_manager.is_connected:
            match_stage: Dict[str, Any] = {"timestamp": {"$gte": start_of_month}}
            if api_key_id:
                match_stage["api_key_id"] = api_key_id
            if user_id:
                match_stage["user_id"] = user_id
            if organization_id:
                match_stage["organization_id"] = organization_id

            pipeline = [
                {"$match": match_stage},
                {
                    "$group": {
                        "_id": None,
                        "total_requests": {"$sum": 1},
                        "total_tokens": {"$sum": "$total_tokens"},
                        "total_cost_usd": {"$sum": "$estimated_cost_usd"}
                    }
                }
            ]
            cursor = db_manager.db.api_usage.aggregate(pipeline)
            results = [doc async for doc in cursor]
            if results:
                return {
                    "total_requests": results[0].get("total_requests", 0),
                    "total_tokens": results[0].get("total_tokens", 0),
                    "total_cost_usd": round(results[0].get("total_cost_usd", 0.0), 6),
                    "period_start": start_of_month,
                    "period_end": now
                }
            return {
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "period_start": start_of_month,
                "period_end": now
            }

        # In-memory aggregation
        filtered = [
            r for r in self._memory_usage
            if r.timestamp >= start_of_month
            and (api_key_id is None or r.api_key_id == api_key_id)
            and (user_id is None or r.user_id == user_id)
            and (organization_id is None or r.organization_id == organization_id)
        ]

        total_requests = len(filtered)
        total_tokens = sum(r.total_tokens for r in filtered)
        total_cost = sum(r.estimated_cost_usd for r in filtered)

        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "period_start": start_of_month,
            "period_end": now
        }

    def clear_memory(self):
        """Helper for test isolation."""
        self._memory_keys.clear()
        self._memory_usage.clear()


api_key_repo = APIKeyRepository()
