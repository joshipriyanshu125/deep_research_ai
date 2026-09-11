"""
Day 26 — Research Memory Test Suite

Tests:
  - ShortTermMemory: session working notes, visited URLs, task state tracking, scratchpad
  - LongTermMemory: persistent research records, cross-session semantic & lexical recall
  - UserMemory: user preferences, domain whitelists/blacklists, query history
  - SourceMemory: global URL cache, reuse counter, citation tracking, domain metrics
  - ResearchMemoryManager: end-to-end cross-research knowledge reuse (Research A -> Research B)
"""

import pytest
from app.memory.short_term import ShortTermMemory, WorkingNote
from app.memory.long_term import LongTermMemory, ResearchKnowledgeRecord, long_term_memory
from app.memory.user_memory import UserMemory, UserProfile, user_memory
from app.memory.source_memory import SourceMemory, CachedSource, source_memory
from app.memory.manager import ResearchMemoryManager, memory_manager


# ---------------------------------------------------------------------------
# 1. Short-Term Memory Tests
# ---------------------------------------------------------------------------

class TestShortTermMemory:
    def test_short_term_memory_initialization(self):
        stm = ShortTermMemory(research_id="job_001", query="Quantum computing algorithms", user_id="user_123")
        assert stm.research_id == "job_001"
        assert stm.query == "Quantum computing algorithms"
        assert stm.user_id == "user_123"
        assert len(stm.visited_urls) == 0

    def test_visited_urls_tracking(self):
        stm = ShortTermMemory(research_id="job_001", query="test")
        stm.record_visited_url("https://example.com/paper1.pdf")
        assert stm.is_url_visited("https://example.com/paper1.pdf")
        assert stm.is_url_visited("HTTPS://EXAMPLE.COM/PAPER1.PDF")  # case insensitive
        assert not stm.is_url_visited("https://example.com/paper2.pdf")

    def test_working_notes_and_tasks(self):
        stm = ShortTermMemory(research_id="job_001", query="test")
        note = stm.add_note("Observed 40% increase in capacity retention", category="metric", task_id="task_1")
        assert note.note_id == "note_001"
        assert note.category == "metric"
        assert len(stm.working_notes) == 1

        stm.update_task_state("task_1", status="completed", summary="Analyzed 5 papers")
        assert "task_1" in stm.task_states
        assert stm.task_states["task_1"]["status"] == "completed"

    def test_scratchpad_and_summary(self):
        stm = ShortTermMemory(research_id="job_001", query="test")
        stm.set_scratchpad_value("target_metric", 99.5)
        assert stm.get_scratchpad_value("target_metric") == 99.5
        assert stm.get_scratchpad_value("missing", default="none") == "none"

        summary = stm.get_summary()
        assert summary["research_id"] == "job_001"
        assert "notes" in summary


# ---------------------------------------------------------------------------
# 2. Long-Term Memory Tests
# ---------------------------------------------------------------------------

class TestLongTermMemory:
    @pytest.fixture
    def ltm(self):
        return LongTermMemory()

    @pytest.mark.asyncio
    async def test_store_and_recall_knowledge(self, ltm: LongTermMemory):
        # Store Research A findings
        await ltm.store_research_knowledge(
            research_id="res_ev_battery_01",
            query="Solid-state lithium battery silicon anodes",
            summary="Silicon-carbon composite anodes achieve 1500 mAh/g capacity with 85% retention after 1000 cycles.",
            topic="Solid-State EV Battery Anodes",
            key_claims=[
                {"claim": "Silicon-carbon composite anodes achieve 1500 mAh/g", "confidence": 0.95}
            ],
            top_sources=[{"title": "Silicon Anode Breakthrough", "url": "https://nature.com/silicon"}],
        )

        assert ltm.count() == 1

        # Recall for Research B (related topic)
        recalled = await ltm.recall_related_knowledge(
            query="silicon anode capacity retention in lithium batteries",
            top_k=2,
            min_similarity=0.30,
        )

        assert len(recalled) == 1
        top = recalled[0]
        assert top["research_id"] == "res_ev_battery_01"
        assert "1500 mAh/g" in top["summary"]
        assert top["relevance_score"] > 0.30

    @pytest.mark.asyncio
    async def test_unrelated_query_not_recalled(self, ltm: LongTermMemory):
        await ltm.store_research_knowledge(
            research_id="res_crops_01",
            query="Agricultural wheat drought resistance genetics",
            summary="CRISPR gene editing of TaDREB genes improved wheat drought tolerance by 30%.",
        )

        recalled = await ltm.recall_related_knowledge(
            query="autonomous rocket propulsion landing algorithms",
            top_k=2,
            min_similarity=0.50,
        )

        assert len(recalled) == 0


# ---------------------------------------------------------------------------
# 3. User Memory Tests
# ---------------------------------------------------------------------------

class TestUserMemory:
    @pytest.fixture
    def um(self):
        return UserMemory()

    def test_user_preferences_and_history(self, um: UserMemory):
        profile = um.get_or_create_profile("user_researcher_1")
        assert profile.preferred_depth == 2
        assert profile.preferred_breadth == 3

        # Update preferences
        um.update_preferences(
            user_id="user_researcher_1",
            preferred_depth=4,
            preferred_categories=["academic"],
            domain_whitelist=["nature.com", "arxiv.org"],
            domain_blacklist=["quora.com"],
            citation_style="apa",
        )

        updated = um.get_or_create_profile("user_researcher_1")
        assert updated.preferred_depth == 4
        assert updated.preferred_categories == ["academic"]
        assert "nature.com" in updated.domain_whitelist
        assert "quora.com" in updated.domain_blacklist
        assert updated.citation_style == "apa"

        # Record query history
        um.record_query("user_researcher_1", "Perovskite solar cell efficiency", "job_01")
        history = um.get_user_history("user_researcher_1")
        assert len(history) == 1
        assert history[0]["query"] == "Perovskite solar cell efficiency"


# ---------------------------------------------------------------------------
# 4. Source Memory Tests
# ---------------------------------------------------------------------------

class TestSourceMemory:
    @pytest.fixture
    def sm(self):
        return SourceMemory()

    def test_source_caching_and_reuse_tracking(self, sm: SourceMemory):
        # Run 1: Store source
        src1 = sm.record_source(
            url="https://arxiv.org/abs/2401.99999",
            title="Transformer Battery Model",
            domain="arxiv.org",
            clean_text="Detailed experimental methodology on attention models for battery state estimation.",
            source_type="academic",
            credibility_score=0.95,
            research_id="job_01",
        )
        assert src1.reuse_count == 1

        # Run 2: Same URL recorded in second research run
        src2 = sm.record_source(
            url="https://arxiv.org/abs/2401.99999",
            title="Transformer Battery Model",
            domain="arxiv.org",
            clean_text="Detailed experimental methodology on attention models for battery state estimation.",
            research_id="job_02",
        )
        assert src2.reuse_count == 2
        assert "job_01" in src2.research_ids
        assert "job_02" in src2.research_ids

        # Look up cached source
        cached = sm.find_cached_source("https://arxiv.org/abs/2401.99999")
        assert cached is not None
        assert cached.title == "Transformer Battery Model"

        # Record citation
        sm.record_citation("https://arxiv.org/abs/2401.99999")
        assert cached.cited_count == 1


# ---------------------------------------------------------------------------
# 5. Unified Research Memory Manager Tests
# ---------------------------------------------------------------------------

class TestResearchMemoryManager:
    @pytest.fixture(autouse=True)
    def clean_manager(self):
        memory_manager.clear_all()
        yield
        memory_manager.clear_all()

    @pytest.mark.asyncio
    async def test_cross_research_knowledge_reuse(self):
        """
        Tests the core Day 26 scenario:
        Research A (Topic: EV Solid State Batteries) completes and saves knowledge.
        Research B (Topic: Solid state battery safety) starts and recalls Research A knowledge.
        """
        # --- Session A ---
        session_a = memory_manager.start_session(
            research_id="res_run_A",
            query="Solid-state EV battery cathode safety and stability",
            user_id="user_john",
        )
        session_a.add_note("NMC811 cathode with solid electrolyte demonstrated no thermal runaway up to 280C.")

        # Complete Session A
        await memory_manager.complete_session(
            research_id="res_run_A",
            topic="Solid-State EV Battery Cathode Safety",
            summary="Solid-state electrolytes prevent thermal runaway in high-nickel cathodes up to 280°C under nail penetration tests.",
            key_claims=[
                {"claim": "No thermal runaway up to 280C under solid electrolyte", "confidence": 0.96}
            ],
            top_sources=[
                {
                    "url": "https://nature.com/articles/solid-state-safety",
                    "title": "Thermal Stability of Solid Electrolytes",
                    "domain": "nature.com",
                    "source_type": "academic",
                    "credibility_score": 0.95,
                    "clean_text": "Solid-state electrolytes prevent thermal runaway in high-nickel cathodes up to 280°C.",
                }
            ],
        )

        # Verify source memory cached the source
        cached = memory_manager.source_mem.find_cached_source("https://nature.com/articles/solid-state-safety")
        assert cached is not None
        assert cached.domain == "nature.com"

        # --- Session B (New research asking related question) ---
        prior_context = await memory_manager.recall_prior_context(
            query="thermal runaway prevention in solid-state lithium batteries",
            user_id="user_john",
            top_k=2,
        )

        assert prior_context["has_prior_knowledge"] is True
        assert len(prior_context["prior_research_findings"]) >= 1
        finding = prior_context["prior_research_findings"][0]
        assert finding["research_id"] == "res_run_A"
        assert "280°C" in finding["summary"]
        assert "user_preferences" in prior_context
