from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.utils.helpers import generate_uuid, get_utc_now


class SourceType:
    WEB = "web"
    ACADEMIC = "academic"
    NEWS = "news"
    COMPANY = "company"


class Source(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    research_id: str
    url: str
    title: str
    source_type: str = SourceType.WEB
    snippet: Optional[str] = ""
    raw_content: Optional[str] = ""
    clean_text: Optional[str] = ""
    author: Optional[str] = None
    published_date: Optional[str] = None
    relevance_score: float = 0.0
    credibility_score: float = 0.8
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=get_utc_now)
