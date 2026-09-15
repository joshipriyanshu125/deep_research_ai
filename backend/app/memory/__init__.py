"""
Day 26 & Day 85–90 — Research Memory & Knowledge Graph Package

Multi-tier memory architecture for autonomous research agents:
  - Short-Term Memory: Active research run state, task notes, visited URLs
  - Long-Term Memory: Cross-session persistent knowledge & findings lookup
  - User Memory: User profiles, preferences, constraints & history
  - Source Memory: Global URL content cache, reuse tracking & domain ledger
  - Entity Memory: Entity knowledge base, previous conclusions & domain hierarchies (Day 85–87)
  - Knowledge Graph: Rich domain relationships, multi-hop path finding & subgraph queries (Day 88–90)
  - Memory Manager: Unified coordinator for session lifecycle and knowledge reuse
"""

from app.memory.short_term import ShortTermMemory, WorkingNote
from app.memory.long_term import LongTermMemory, ResearchKnowledgeRecord, long_term_memory
from app.memory.user_memory import UserMemory, UserProfile, user_memory
from app.memory.source_memory import SourceMemory, CachedSource, source_memory
from app.memory.entity_memory import (
    EntityType,
    EntityKnowledge,
    HierarchicalEntity,
    PreviousConclusion,
    EntityMemoryManager,
    entity_memory
)
from app.memory.knowledge_graph import (
    RelationType,
    GraphNode,
    GraphEdge,
    GraphPath,
    KnowledgeGraph,
    knowledge_graph
)
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
    # Entity Memory (Day 85–87)
    "EntityType",
    "EntityKnowledge",
    "HierarchicalEntity",
    "PreviousConclusion",
    "EntityMemoryManager",
    "entity_memory",
    # Knowledge Graph (Day 88–90)
    "RelationType",
    "GraphNode",
    "GraphEdge",
    "GraphPath",
    "KnowledgeGraph",
    "knowledge_graph",
    # Manager
    "ResearchMemoryManager",
    "memory_manager",
]
