from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.utils.helpers import generate_uuid, get_utc_now


class Conversation(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    user_id: str = "anonymous"
    title: str = "Research conversation"
    research_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class ConversationMessage(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    conversation_id: str
    role: str = "user"
    content: str
    research_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=get_utc_now)


class ConversationCreate(BaseModel):
    title: str = "Research conversation"


class MessageCreate(BaseModel):
    content: str
    research_ids: List[str] = Field(default_factory=list)
