"""
Day 26 — Short-Term Memory

Manages the working state and intermediate findings for an active research run:
  - Active research goal & query
  - Task execution states & intermediate findings
  - Visited URLs and scrape status in this session
  - Working notes & scratchpad evidence
  - Session metrics
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.utils.helpers import get_utc_now


class WorkingNote(BaseModel):
    note_id: str
    content: str
    category: str = "observation"  # observation, hypothesis, metric, warning
    task_id: Optional[str] = None
    created_at: datetime = Field(default_factory=get_utc_now)


class ShortTermMemory:
    """
    Session-scoped working memory for an individual research run.
    """

    def __init__(self, research_id: str, query: str, user_id: Optional[str] = "anonymous"):
        self.research_id = research_id
        self.query = query
        self.user_id = user_id
        self.created_at = get_utc_now()

        self.visited_urls: set = set()
        self.working_notes: List[WorkingNote] = []
        self.task_states: Dict[str, Dict[str, Any]] = {}
        self.collected_evidence_ids: List[str] = []
        self.scratchpad: Dict[str, Any] = {}

    def record_visited_url(self, url: str) -> None:
        """Mark a URL as visited in this research run."""
        if url:
            self.visited_urls.add(url.strip().lower())

    def is_url_visited(self, url: str) -> bool:
        """Check if a URL was already visited in this session."""
        return url.strip().lower() in self.visited_urls if url else False

    def add_note(self, content: str, category: str = "observation", task_id: Optional[str] = None) -> WorkingNote:
        """Append an analytical note or intermediate finding."""
        note = WorkingNote(
            note_id=f"note_{len(self.working_notes) + 1:03d}",
            content=content.strip(),
            category=category,
            task_id=task_id,
        )
        self.working_notes.append(note)
        return note

    def update_task_state(self, task_id: str, status: str, summary: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update working state for an active sub-task."""
        self.task_states[task_id] = {
            "status": status,
            "summary": summary or "",
            "metadata": metadata or {},
            "updated_at": get_utc_now(),
        }

    def add_evidence_id(self, evidence_id: str) -> None:
        """Register an extracted evidence ID."""
        if evidence_id and evidence_id not in self.collected_evidence_ids:
            self.collected_evidence_ids.append(evidence_id)

    def set_scratchpad_value(self, key: str, value: Any) -> None:
        """Store scratchpad variable for agent collaboration."""
        self.scratchpad[key] = value

    def get_scratchpad_value(self, key: str, default: Any = None) -> Any:
        return self.scratchpad.get(key, default)

    def get_summary(self) -> Dict[str, Any]:
        """Return snapshot of the active research session memory."""
        return {
            "research_id": self.research_id,
            "query": self.query,
            "user_id": self.user_id,
            "visited_url_count": len(self.visited_urls),
            "notes_count": len(self.working_notes),
            "task_count": len(self.task_states),
            "evidence_count": len(self.collected_evidence_ids),
            "notes": [n.model_dump() for n in self.working_notes],
        }

    def clear(self) -> None:
        """Reset short term working state."""
        self.visited_urls.clear()
        self.working_notes.clear()
        self.task_states.clear()
        self.collected_evidence_ids.clear()
        self.scratchpad.clear()
