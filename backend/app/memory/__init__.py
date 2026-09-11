"""
Day 26 — Research Memory Package

Multi-tier memory architecture for autonomous research agents:
  - Short-Term Memory: Active research run state, task notes, visited URLs
  - Long-Term Memory: Cross-session persistent knowledge & findings lookup
  - User Memory: User profiles, preferences, constraints & history
  - Source Memory: Global URL content cache, reuse tracking & domain ledger
  - Memory Manager: Unified coordinator for session lifecycle and knowledge reuse
"""

from app.memory.short_term import ShortTermMemory, WorkingNote
from app.memory.long_term import LongTermMemory, ResearchKnowledgeRecord, long_term_memory
from app.memory.user_memory import UserMemory, UserProfile, user_memory
from app.memory.source_memory import SourceMemory, CachedSource, source_memory
from app.memory.manager import ResearchMemoryManager, memory_manager

__all__ = [
    # Short-Term
    "ShortTermMemory",
    "WorkingNote",
    # Long-Term
    "LongTermMemory",
    "ResearchKnowledgeRecord",
    "long_term_memory",
    # User Memory
    "UserMemory",
    "UserProfile",
    "user_memory",
    # Source Memory
    "SourceMemory",
    "CachedSource",
    "source_memory",
    # Manager
    "ResearchMemoryManager",
    "memory_manager",
]
