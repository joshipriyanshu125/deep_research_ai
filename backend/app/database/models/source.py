import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from pydantic import BaseModel, Field, model_validator, field_serializer
from app.utils.helpers import generate_uuid, get_utc_now


class SourceType:
    WEB = "web"
    ACADEMIC = "academic"
    NEWS = "news"
    COMPANY = "company"


def extract_domain_from_url(url: str) -> str:
    """Extract clean domain name without www or port."""
    if not url:
        return ""
    if not url.startswith(("http://", "https://", "ftp://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc or parsed.path.split("/")[0]
        # Remove port if present
        domain = netloc.split(":")[0].lower().strip()
        # Remove leading www.
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


class ProcessedSearchResult(BaseModel):
    """
    Day 13 — Standardized processed search result record.
    Represents every gathered search result with full metadata.
    """
    url: str
    title: str
    domain: str = ""
    snippet: Optional[str] = ""
    publication_date: Optional[str] = None
    retrieved_date: datetime = Field(default_factory=get_utc_now)
    query: Optional[str] = ""
    source_type: str = SourceType.WEB
    relevance_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "populate_by_name": True,
    }

    @model_validator(mode="before")
    @classmethod
    def populate_domain_and_dates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Auto-compute domain if omitted or empty
            if not data.get("domain") and data.get("url"):
                data["domain"] = extract_domain_from_url(data["url"])
            
            # Support published_date alias
            if not data.get("publication_date") and data.get("published_date"):
                data["publication_date"] = data["published_date"]
            elif not data.get("published_date") and data.get("publication_date"):
                data["published_date"] = data["publication_date"]

        return data

    @field_serializer("retrieved_date")
    def _serialize_dt(self, dt: datetime) -> str:
        return dt.isoformat()


class Source(BaseModel):
    """
    Full Source record stored in database and used by analysis / synthesis layers.
    Contains all search result processing fields plus full extracted text and scores.
    """
    id: str = Field(default_factory=generate_uuid)
    research_id: Optional[str] = ""
    url: str
    title: str
    domain: str = ""
    snippet: Optional[str] = ""
    publication_date: Optional[str] = None
    published_date: Optional[str] = None  # Backward compatibility
    retrieved_date: datetime = Field(default_factory=get_utc_now)
    query: Optional[str] = ""
    source_type: str = SourceType.WEB
    relevance_score: float = 0.0
    credibility_score: float = 0.8
    raw_content: Optional[str] = ""
    clean_text: Optional[str] = ""
    author: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=get_utc_now)

    model_config = {
        "populate_by_name": True,
    }

    @model_validator(mode="before")
    @classmethod
    def populate_source_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Auto-compute domain if empty
            if not data.get("domain") and data.get("url"):
                data["domain"] = extract_domain_from_url(data["url"])

            # Synchronize publication_date and published_date
            if data.get("published_date") and not data.get("publication_date"):
                data["publication_date"] = data["published_date"]
            elif data.get("publication_date") and not data.get("published_date"):
                data["published_date"] = data["publication_date"]

        return data

    @field_serializer("retrieved_date", "created_at")
    def _serialize_dt(self, dt: datetime) -> str:
        return dt.isoformat()
