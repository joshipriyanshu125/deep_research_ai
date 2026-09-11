"""
Day 26 — User Memory (Personalization & History)

Stores user preferences, research habits, domain whitelists/blacklists,
and past queries per user.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.utils.helpers import get_utc_now


class UserProfile(BaseModel):
    user_id: str
    preferred_depth: int = 2
    preferred_breadth: int = 3
    preferred_categories: List[str] = Field(default_factory=lambda: ["web", "academic", "market"])
    domain_whitelist: List[str] = Field(default_factory=list)
    domain_blacklist: List[str] = Field(default_factory=list)
    citation_style: str = "ieee"  # ieee, apa, harvard
    detail_level: str = "comprehensive"  # concise, comprehensive, executive
    custom_system_instructions: Optional[str] = None
    query_history: List[Dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=get_utc_now)


class UserMemory:
    """
    Manages user-specific preferences, constraints, and research history.
    """

    def __init__(self):
        self._profiles: Dict[str, UserProfile] = {}

    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """Fetch existing user profile or initialize with sensible defaults."""
        user_key = user_id or "anonymous"
        if user_key not in self._profiles:
            self._profiles[user_key] = UserProfile(user_id=user_key)
        return self._profiles[user_key]

    def update_preferences(
        self,
        user_id: str,
        preferred_depth: Optional[int] = None,
        preferred_breadth: Optional[int] = None,
        preferred_categories: Optional[List[str]] = None,
        domain_whitelist: Optional[List[str]] = None,
        domain_blacklist: Optional[List[str]] = None,
        citation_style: Optional[str] = None,
        detail_level: Optional[str] = None,
        custom_system_instructions: Optional[str] = None,
    ) -> UserProfile:
        """Update user preferences."""
        profile = self.get_or_create_profile(user_id)
        if preferred_depth is not None:
            profile.preferred_depth = preferred_depth
        if preferred_breadth is not None:
            profile.preferred_breadth = preferred_breadth
        if preferred_categories is not None:
            profile.preferred_categories = preferred_categories
        if domain_whitelist is not None:
            profile.domain_whitelist = [d.lower().strip() for d in domain_whitelist]
        if domain_blacklist is not None:
            profile.domain_blacklist = [d.lower().strip() for d in domain_blacklist]
        if citation_style is not None:
            profile.citation_style = citation_style
        if detail_level is not None:
            profile.detail_level = detail_level
        if custom_system_instructions is not None:
            profile.custom_system_instructions = custom_system_instructions

        profile.updated_at = get_utc_now()
        return profile

    def record_query(self, user_id: str, query: str, research_id: str) -> None:
        """Log a new research query to the user's history."""
        profile = self.get_or_create_profile(user_id)
        profile.query_history.append({
            "research_id": research_id,
            "query": query,
            "timestamp": get_utc_now().isoformat(),
        })

    def get_user_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent query history for a user."""
        profile = self.get_or_create_profile(user_id)
        return profile.query_history[-limit:]

    def clear(self) -> None:
        self._profiles.clear()


user_memory = UserMemory()
