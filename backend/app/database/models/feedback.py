from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.utils.helpers import generate_uuid, get_utc_now


class ReportFeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=4000)


class ReportFeedback(ReportFeedbackCreate):
    id: str = Field(default_factory=generate_uuid)
    report_id: str
    user_id: str = "anonymous"
    created_at: datetime = Field(default_factory=get_utc_now)
