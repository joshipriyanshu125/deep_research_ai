"""
Tests for DAY 85–87 — Advanced Agent Memory
Tests:
- Entity Knowledge (Companies, Industries, Countries, Technologies, etc.)
- Hierarchical Entity Structure: Entity → Company → Industry → Country → Evidence
- Previous Conclusions & Hypotheses tracking
- Research Memory Manager cross-session recall and enrichment
"""

import pytest
from app.memory.entity_memory import (
    EntityMemoryManager,
    EntityType,
    EntityKnowledge,
    HierarchicalEntity,
    PreviousConclusion,
    entity_memory
)
from app.memory.manager import ResearchMemoryManager, memory_manager


@pytest.fixture(autouse=True)
def clear_memory_stores():
    entity_memory.clear()
    memory_manager.clear_all()
    yield
    entity_memory.clear()
    memory_manager.clear_all()


@pytest.mark.asyncio
async def test_entity_upsert_and_retrieval():
    # 1. Upsert new entity
    ent = await entity_memory.upsert_entity(
        name="Tata Motors",
        entity_type=EntityType.COMPANY,
        description="Major Indian multinational automotive manufacturer",
        company="Tata Group",
        industry="Automotive",
        country="India",
        aliases=["Tata", "TML", "Tata Passenger Vehicles"],
        attributes={"market_cap_usd_bn": 35.0, "ev_market_share": "70%"},
        research_id="res_101"
    )
    assert ent.id is not None
    assert ent.name == "Tata Motors"
    assert ent.entity_type == EntityType.COMPANY
    assert ent.industry == "Automotive"
    assert ent.country == "India"
    assert "TML" in ent.aliases

    # 2. Lookup by alias
    by_alias = await entity_memory.get_entity("TML")
    assert by_alias is not None
    assert by_alias.id == ent.id

    # 3. Lookup by case-insensitive name
    by_name = await entity_memory.get_entity("tata motors")
    assert by_name is not None
    assert by_name.id == ent.id

    # 4. Upsert with new attributes/evidence updates existing
    updated = await entity_memory.upsert_entity(
        name="Tata Motors",
        evidence_id="ev_999",
        attributes={"battery_supplier": "Tata AutoComp"}
    )
    assert updated.id == ent.id
    assert "ev_999" in updated.evidence_ids
    assert updated.attributes.get("battery_supplier") == "Tata AutoComp"
    assert updated.attributes.get("market_cap_usd_bn") == 35.0


@pytest.mark.asyncio
async def test_hierarchical_entity_lineage():
    ent = await entity_memory.upsert_entity(
        name="EV Division",
        entity_type=EntityType.COMPANY,
        company="Tata Motors",
        industry="Clean Mobility",
        country="India"
    )

    hierarchy = entity_memory.build_hierarchy(
        entity=ent,
        evidence_list=[{"id": "ev_1", "claim": "Over 100,000 EVs deployed in India"}]
    )

    assert hierarchy.name == "EV Division"
    assert hierarchy.company == "Tata Motors"
    assert hierarchy.industry == "Clean Mobility"
    assert hierarchy.country == "India"
    assert len(hierarchy.evidence_items) == 1

    lineage = hierarchy.to_lineage_path()
    assert "EV Division → Company: Tata Motors → Industry: Clean Mobility → Country: India" == lineage


@pytest.mark.asyncio
async def test_previous_conclusions_tracking():
    # Record conclusions
    c1 = await entity_memory.record_conclusion(
        topic="Indian EV Charging Infrastructure",
        conclusion_text="Grid capacity in Tier-1 cities is sufficient for 2026 EV adoption targets, but highway DC fast charging remains a bottleneck.",
        key_findings=["Tier-1 capacity ok", "Highway DC fast charging bottleneck"],
        confidence=0.92,
        consensus_status="established",
        research_id="res_ev_01",
        tags=["ev", "india", "grid"]
    )
    assert c1.id is not None
    assert c1.confidence == 0.92
    assert c1.consensus_status == "established"

    c2 = await entity_memory.record_conclusion(
        topic="Solid State Battery Commercialization",
        conclusion_text="Mass market automotive commercialization of solid-state cells is delayed to 2028–2030 due to manufacturing yields.",
        confidence=0.88,
        consensus_status="emerging",
        research_id="res_battery_02",
        tags=["battery", "solid_state", "automotive"]
    )

    # Search by topic
    ev_conclusions = await entity_memory.get_conclusions_by_topic("EV Charging")
    assert len(ev_conclusions) == 1
    assert ev_conclusions[0].id == c1.id

    battery_conclusions = await entity_memory.get_conclusions_by_topic("Solid State")
    assert len(battery_conclusions) == 1
    assert battery_conclusions[0].id == c2.id


@pytest.mark.asyncio
async def test_memory_manager_integration_entities_and_conclusions():
    mgr = ResearchMemoryManager(entity_mem=entity_memory)

    # Start session
    mgr.start_session("job_100", query="Indian EV Market Overview", user_id="user_analyst_1")

    # Complete session with entities & conclusions
    await mgr.complete_session(
        research_id="job_100",
        summary="India EV ecosystem is expanding rapidly led by 2W and 4W fleet electrification.",
        topic="Indian EV Market",
        entities=[
            {"name": "Tata Motors", "entity_type": "company", "industry": "Automotive", "country": "India"},
            {"name": "Ola Electric", "entity_type": "company", "industry": "2W EV", "country": "India"}
        ],
        conclusions=[
            "2W electric vehicle penetration will cross 20% by 2026.",
            "PLI scheme has accelerated local battery assembly."
        ],
        tags=["ev", "india"]
    )

    # Now recall prior context for a related query
    context = await mgr.recall_prior_context(query="Tata Motors in India EV Market")
    assert context["has_prior_knowledge"] is True
    assert len(context["entities"]) >= 1
    assert any(e["name"] == "Tata Motors" for e in context["entities"])
    assert len(context["previous_conclusions"]) >= 1
