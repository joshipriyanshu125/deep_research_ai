from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator
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
    depth: Optional[int] = Field(default=None, ge=1, le=5)
    breadth: Optional[int] = Field(default=None, ge=1, le=8)
    categories: Optional[List[str]] = None
    tracks: Optional[Dict[str, Any]] = None
    llm_provider: Optional[str] = None
    custom_instructions: Optional[str] = None
    # Day 91–95 — Advanced Research Modes
    research_mode: Optional[str] = "standard"  # quick | standard | deep | expert

    @model_validator(mode="before")
    @classmethod
    def handle_tracks_alias(cls, data):
        if isinstance(data, dict):
            if "tracks" in data and not data.get("categories"):
                tracks = data.get("tracks")
                if isinstance(tracks, dict):
                    data["categories"] = [k for k, v in tracks.items() if v]
                elif isinstance(tracks, list):
                    data["categories"] = tracks
        return data


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
    # Public, structured audit of the pipeline.  Unlike the transient progress
    # message this survives completion and lets clients prove which engines and
    # depth iterations actually ran.
    execution_summary: Dict[str, Any] = Field(default_factory=dict)
    parent_research_id: Optional[str] = None
    # Day 91–95 — Advanced Research Modes
    research_mode: Optional[str] = "standard"  # quick | standard | deep | expert
