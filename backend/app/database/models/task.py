from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_serializer
from app.utils.helpers import generate_uuid, get_utc_now


# ---------------------------------------------------------------------------
# Status & Type Constants
# ---------------------------------------------------------------------------

class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"

    ALL = {PENDING, RUNNING, COMPLETED, FAILED, RETRYING, CANCELLED}

    # Allowed transitions: current_status -> set of allowed next statuses
    TRANSITIONS: Dict[str, set] = {
        PENDING:   {RUNNING, CANCELLED},
        RUNNING:   {COMPLETED, FAILED, CANCELLED},
        FAILED:    {RETRYING, CANCELLED},
        RETRYING:  {RUNNING, CANCELLED},
        COMPLETED: set(),   # terminal
        CANCELLED: set(),   # terminal
    }

    @classmethod
    def can_transition(cls, current: str, target: str) -> bool:
        return target in cls.TRANSITIONS.get(current, set())

    @classmethod
    def is_terminal(cls, status: str) -> bool:
        return status in {cls.COMPLETED, cls.CANCELLED}


class TaskType:
    WEB_SEARCH = "web_search"
    ACADEMIC_SEARCH = "academic_search"
    MARKET_SEARCH = "market_search"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"

    ALL = {WEB_SEARCH, ACADEMIC_SEARCH, MARKET_SEARCH, ANALYSIS, SYNTHESIS}


# ---------------------------------------------------------------------------
# Core Document Model
# ---------------------------------------------------------------------------

class ResearchTaskRecord(BaseModel):
    """
    Persistent, document-level record for a single research sub-task.
    Stored in the `research_tasks` MongoDB collection.
    Independent of the in-process ResearchTask used inside ResearchJob.
    """
    id: str = Field(default_factory=generate_uuid, alias="_id")
    research_id: str
    question: str
    type: str = TaskType.WEB_SEARCH
    status: str = TaskStatus.PENDING
    priority: int = Field(default=1, ge=1, le=10, description="1 = highest priority")
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    assigned_agent: str = "web_research_agent"

    # Optional tracking fields
    error_message: Optional[str] = None
    result_summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,  # allow both 'id' and '_id'
    }

    @field_serializer("created_at", "updated_at", "started_at", "completed_at")
    def _serialize_dt(self, v: Optional[datetime]) -> Optional[str]:
        return v.isoformat() if v is not None else None

    def touch(self) -> None:
        """Refresh updated_at timestamp."""
        self.updated_at = get_utc_now()

    def can_transition_to(self, new_status: str) -> bool:
        return TaskStatus.can_transition(self.status, new_status)

    def is_terminal(self) -> bool:
        return TaskStatus.is_terminal(self.status)

    def is_retryable(self) -> bool:
        return self.status == TaskStatus.FAILED and self.attempts < self.max_attempts


# ---------------------------------------------------------------------------
# API Request/Response Schemas
# ---------------------------------------------------------------------------

class TaskCreateRequest(BaseModel):
    research_id: str
    question: str
    type: str = TaskType.WEB_SEARCH
    priority: int = Field(default=1, ge=1, le=10)
    assigned_agent: str = "web_research_agent"
    max_attempts: int = Field(default=3, ge=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskUpdateRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=10)
    assigned_agent: Optional[str] = None
    error_message: Optional[str] = None
    result_summary: Optional[str] = None


class TaskStatusTransitionRequest(BaseModel):
    status: str
    error_message: Optional[str] = None
    result_summary: Optional[str] = None


class TaskBulkCreateRequest(BaseModel):
    research_id: str
    tasks: list[TaskCreateRequest]


class TaskStatsResponse(BaseModel):
    research_id: str
    total: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    retrying: int = 0
    cancelled: int = 0
    completion_rate: float = 0.0
