from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.utils.helpers import generate_uuid, get_utc_now


class Citation(BaseModel):
    index: int
    title: str
    url: str
    source_type: str = "web"
    snippet: Optional[str] = None


class ReportSection(BaseModel):
    title: str
    content: str
    citations: List[int] = Field(default_factory=list)


class ResearchReport(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    research_id: str
    title: str
    executive_summary: str
    markdown_content: str
    sections: List[ReportSection] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    key_findings: List[str] = Field(default_factory=list)
    quality_score: float = 9.5
    created_at: datetime = Field(default_factory=get_utc_now)
