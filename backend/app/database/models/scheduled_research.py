"""
Days 70–72 — Scheduled Research Data Models

Collection: scheduled_research
Supports scheduled queries (e.g. "Research the Indian EV market every Monday and tell me what changed")
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class ScheduledResearchFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CRON = "cron"


class ScheduledResearch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = "anonymous"
    query: str
    title: Optional[str] = None
    frequency: str = ScheduledResearchFrequency.WEEKLY.value
    schedule_day: str = "monday"
    cron_expression: Optional[str] = None
    is_active: bool = True
    depth: int = 2
    breadth: int = 3
    categories: List[str] = Field(default_factory=lambda: ["web", "academic", "market"])
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


class ScheduledResearchCreate(BaseModel):
    query: str
    title: Optional[str] = None
    frequency: str = ScheduledResearchFrequency.WEEKLY.value
    schedule_day: str = "monday"
    cron_expression: Optional[str] = None
    depth: int = 2
    breadth: int = 3
    categories: List[str] = Field(default_factory=lambda: ["web", "academic", "market"])


class ScheduledResearchUpdate(BaseModel):
    title: Optional[str] = None
    frequency: Optional[str] = None
    schedule_day: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: Optional[bool] = None
    depth: Optional[int] = None
    breadth: Optional[int] = None


class ScheduledChangeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    scheduled_id: str
    user_id: str = "anonymous"
    query: str
    current_research_id: str
    current_report_id: Optional[str] = None
    previous_research_id: Optional[str] = None
    previous_report_id: Optional[str] = None
    summary_of_changes: str
    new_findings: List[str] = Field(default_factory=list)
    market_shifts_or_updates: List[str] = Field(default_factory=list)
    metrics_comparison: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")
