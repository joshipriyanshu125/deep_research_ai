import hashlib
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from pydantic import BaseModel, Field, model_validator, field_serializer
from app.utils.helpers import generate_uuid, get_utc_now


class SourceType:
    """
    Standardized source categories for Day 16 Source Management.
    """
    NEWS = "news"
    GOVERNMENT = "government"
    COMPANY = "company"
    ACADEMIC = "academic"
    FINANCIAL = "financial"
    BLOG = "blog"
    FORUM = "forum"
    SOCIAL = "social"
    OTHER = "other"

    # Backward compatibility alias
    WEB = "web"

    ALL_TYPES = {
        NEWS, GOVERNMENT, COMPANY, ACADEMIC, FINANCIAL,
        BLOG, FORUM, SOCIAL, OTHER, WEB
    }


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of text for deduplication and content integrity."""
    if not text:
        text = ""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def extract_domain_from_url(url: str) -> str:
    """Extract clean domain name without www or port."""
    if not url:
        return ""
    if not url.startswith(("http://", "https://", "ftp://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc or parsed.path.split("/")[0]
        domain = netloc.split(":")[0].lower().strip()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


class ProcessedSearchResult(BaseModel):
    """
    Standardized processed search result record.
    """
    url: str
    title: str
    domain: str = ""
    snippet: Optional[str] = ""
    publication_date: Optional[str] = None
    published_at: Optional[str] = None
    retrieved_date: datetime = Field(default_factory=get_utc_now)
    retrieved_at: datetime = Field(default_factory=get_utc_now)
    query: Optional[str] = ""
    source_type: str = SourceType.OTHER
    relevance_score: float = 0.0
    language: str = "en"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "populate_by_name": True,
    }

    @model_validator(mode="before")
    @classmethod
    def populate_domain_and_dates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("domain") and data.get("url"):
                data["domain"] = extract_domain_from_url(data["url"])
            
            pub_date = (
                data.get("published_at")
                or data.get("publication_date")
                or data.get("published_date")
            )
            data["published_at"] = pub_date
            data["publication_date"] = pub_date

            ret_date = data.get("retrieved_at") or data.get("retrieved_date") or get_utc_now()
            data["retrieved_at"] = ret_date
            data["retrieved_date"] = ret_date

        return data

    @field_serializer("retrieved_date", "retrieved_at")
    def _serialize_dt(self, dt: datetime) -> str:
        return dt.isoformat()


class Source(BaseModel):
    """
    Day 16 — Research Source Record stored in the `research_sources` collection.
    Captures full source content, metadata, scores, language, and SHA-256 hash.
    """
    source_id: str = Field(default_factory=generate_uuid)
    id: str = Field(default_factory=generate_uuid)  # Backward compatibility alias
    research_id: str = ""
    url: str
    title: str
    domain: str = ""
    content: str = ""
    clean_text: Optional[str] = ""  # Backward compatibility alias
    raw_content: Optional[str] = ""  # Backward compatibility alias
    source_type: str = SourceType.OTHER
    published_at: Optional[str] = None
    publication_date: Optional[str] = None  # Backward compatibility alias
    published_date: Optional[str] = None    # Backward compatibility alias
    retrieved_at: datetime = Field(default_factory=get_utc_now)
    retrieved_date: datetime = Field(default_factory=get_utc_now)  # Backward compatibility alias
    author: Optional[str] = None
    language: str = "en"
    relevance_score: float = 0.0
    credibility_score: float = 0.8
    content_hash: str = ""
    snippet: Optional[str] = ""
    query: Optional[str] = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=get_utc_now)

    model_config = {
        "populate_by_name": True,
    }

    @model_validator(mode="before")
    @classmethod
    def populate_source_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # 1. Sync source_id and id
            sid = data.get("source_id") or data.get("id") or generate_uuid()
            data["source_id"] = sid
            data["id"] = sid

            # 2. Domain extraction
            if not data.get("domain") and data.get("url"):
                data["domain"] = extract_domain_from_url(data["url"])

            # 3. Content synchronization
            cnt = data.get("content") or data.get("clean_text") or data.get("raw_content") or data.get("snippet") or ""
            data["content"] = cnt
            data["clean_text"] = cnt
            if not data.get("raw_content"):
                data["raw_content"] = cnt

            # 4. Content hash calculation
            if not data.get("content_hash"):
                data["content_hash"] = compute_content_hash(cnt or data.get("url", ""))

            # 5. Publication dates sync
            pub_date = (
                data.get("published_at")
                or data.get("publication_date")
                or data.get("published_date")
            )
            data["published_at"] = pub_date
            data["publication_date"] = pub_date
            data["published_date"] = pub_date

            # 6. Retrieval timestamps sync
            ret_date = data.get("retrieved_at") or data.get("retrieved_date") or get_utc_now()
            data["retrieved_at"] = ret_date
            data["retrieved_date"] = ret_date

            # 7. Normalize source_type
            st = data.get("source_type")
            if st and str(st).lower() in SourceType.ALL_TYPES:
                data["source_type"] = str(st).lower()
            elif not st:
                data["source_type"] = SourceType.OTHER

        return data

    @field_serializer("retrieved_at", "retrieved_date", "created_at")
    def _serialize_dt(self, dt: datetime) -> str:
        return dt.isoformat()


# Type alias for clarity
ResearchSource = Source
