from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.utils.helpers import generate_uuid, get_utc_now


class ResearchStatus:
    PENDING = "pending"
    PLANNING = "planning"
    SEARCHING = "searching"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchTask(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    query: str
    question: Optional[str] = None
    category: str = "web"  # web, academic, market
    status: str = "pending"  # pending, in_progress, completed, failed
    depth: int = 1
    results_count: int = 0
    duration_ms: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    source_urls: List[str] = Field(default_factory=list)



class ResearchPlan(BaseModel):
    research_goal: str
    tasks: List[ResearchTask] = Field(default_factory=list)
    depth: int = 2
    breadth: int = 3
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResearchRequest(BaseModel):
    query: str
    depth: int = Field(default=2, ge=1, le=5)
    breadth: int = Field(default=3, ge=1, le=8)
    categories: List[str] = Field(default=["web", "academic", "market"])
    llm_provider: Optional[str] = None
    custom_instructions: Optional[str] = None


class FollowUpRequest(BaseModel):
    query: str


class ResearchJob(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    user_id: Optional[str] = "anonymous"
    query: str
    depth: int = 2
    breadth: int = 3
    categories: List[str] = Field(default=["web", "academic", "market"])
    status: str = ResearchStatus.PENDING
    current_step: str = "Initializing research orchestrator..."
    progress_percentage: int = 0
    tasks: List[ResearchTask] = Field(default_factory=list)
    source_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    report_id: Optional[str] = None
    logs: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=get_utc_now)
    completed_at: Optional[datetime] = None
    checkpoint_phase: str = "pending"
    checkpoint_data: Dict[str, Any] = Field(default_factory=dict)
    parent_research_id: Optional[str] = None
