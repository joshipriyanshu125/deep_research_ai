from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.utils.helpers import generate_uuid, get_utc_now


class APIKeyScope:
    RESEARCH_CREATE = "research:create"
    RESEARCH_READ = "research:read"
    RESEARCH_DELETE = "research:delete"
    USAGE_READ = "usage:read"
    KEYS_MANAGE = "keys:manage"

    ALL = {
        RESEARCH_CREATE,
        RESEARCH_READ,
        RESEARCH_DELETE,
        USAGE_READ,
        KEYS_MANAGE
    }


class APIKey(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    name: str = Field(default="Default API Key", min_length=1, max_length=100)
    key_prefix: str  # e.g., "dra_live_abc123" (first 12 chars for display/identification)
    hashed_key: str  # SHA-256 hash of the full secret key
    user_id: str
    organization_id: Optional[str] = None
    scopes: List[str] = Field(default_factory=lambda: list(APIKeyScope.ALL))
    rate_limit_per_minute: int = Field(default=60, ge=1)
    monthly_quota: int = Field(default=1000, ge=1)  # Max requests per month
    monthly_token_quota: int = Field(default=2_000_000, ge=1)  # Max tokens per month
    is_active: bool = True
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
    last_used_at: Optional[datetime] = None


class APIKeyCreate(BaseModel):
    name: str = Field(default="My API Key", min_length=1, max_length=100)
    organization_id: Optional[str] = None
    scopes: Optional[List[str]] = None
    rate_limit_per_minute: Optional[int] = 60
    monthly_quota: Optional[int] = 1000
    monthly_token_quota: Optional[int] = 2_000_000
    expires_in_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    user_id: str
    organization_id: Optional[str] = None
    scopes: List[str]
    rate_limit_per_minute: int
    monthly_quota: int
    monthly_token_quota: int
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None


class APIKeySecretResponse(APIKeyResponse):
    secret_key: str  # Full plaintext key, returned ONLY on creation


class APIUsageRecord(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    api_key_id: str
    user_id: str
    organization_id: Optional[str] = None
    endpoint: str
    method: str = "POST"
    status_code: int = 200
    request_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0
    model_used: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: datetime = Field(default_factory=get_utc_now)


class APIUsageSummary(BaseModel):
    api_key_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    total_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    requests_remaining: int = 0
    tokens_remaining: int = 0
    rate_limit_per_minute: int = 60
    monthly_quota: int = 1000
    monthly_token_quota: int = 2_000_000
    period_start: datetime = Field(default_factory=get_utc_now)
    period_end: datetime = Field(default_factory=get_utc_now)
