from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.utils.helpers import generate_uuid, get_utc_now


class Evidence(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    research_id: str
    source_id: str
    claim: str
    quote: str
    confidence: float = 0.9
    sub_topic: Optional[str] = None
    supporting_entities: List[str] = Field(default_factory=list)
    verification_status: str = "verified"  # verified, disputed, unverified
    created_at: datetime = Field(default_factory=get_utc_now)
