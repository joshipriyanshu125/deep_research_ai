"""Durable observability records for research jobs and agents."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.utils.helpers import generate_uuid, get_utc_now


class ResearchEventRecord(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    research_id: str
    event: str
    message: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=get_utc_now)


class AgentLogRecord(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    research_id: str
    agent: str
    status: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=get_utc_now)
