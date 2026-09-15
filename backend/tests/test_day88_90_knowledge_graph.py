"""
Tests for DAY 88–90 — Knowledge Graph
Tests:
- Entity and Relationship representations:
    - Company → competes_with → Company
    - Company → operates_in → Market
    - Policy → affects → Market
    - Company → manufactures → Product
    - Supplier → supplies → Company / Product
    - Division → subsidiary_of → Company
- Multi-hop traversal:
    Tata Motors → EV division → India → EV market → Battery → Supplier
- Competitor discovery, Market ecosystem exploration, Policy impact tracing
- Graph export & import
- Memory & Knowledge Graph REST APIs
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.memory.knowledge_graph import (
    KnowledgeGraph,
    RelationType,
    knowledge_graph
)
from app.memory.entity_memory import EntityType, entity_memory


@pytest.fixture(autouse=True)
def clear_graph_stores():
    knowledge_graph.clear()
    entity_memory.clear()
    yield
    knowledge_graph.clear()
    entity_memory.clear()


def test_graph_node_and_edge_creation():
    kg = KnowledgeGraph()

    # Company → manufactures → Product
    e1 = kg.add_edge(
        source_label_or_id="Tata Motors",
        target_label_or_id="Nexon EV",
        relation_type=RelationType.MANUFACTURES,
        source_type=EntityType.COMPANY,
        target_type=EntityType.PRODUCT
    )
    assert e1.relation_type == RelationType.MANUFACTURES

    # Company → operates_in → Market
    e2 = kg.add_edge(
        source_label_or_id="Tata Motors",
        target_label_or_id="Indian EV Market",
        relation_type=RelationType.OPERATES_IN,
        source_type=EntityType.COMPANY,
        target_type=EntityType.MARKET
    )
    assert e2.relation_type == RelationType.OPERATES_IN

    # Company → competes_with → Company
    e3 = kg.add_edge(
        source_label_or_id="Tata Motors",
        target_label_or_id="Mahindra Electric",
        relation_type=RelationType.COMPETES_WITH,
        source_type=EntityType.COMPANY,
        target_type=EntityType.COMPANY
    )
    assert e3.relation_type == RelationType.COMPETES_WITH

    # Policy → affects → Market
    e4 = kg.add_edge(
        source_label_or_id="FAME II Policy",
        target_label_or_id="Indian EV Market",
        relation_type=RelationType.AFFECTS,
        source_type=EntityType.POLICY,
        target_type=EntityType.MARKET
    )
    assert e4.relation_type == RelationType.AFFECTS


def test_multi_hop_path_traversal():
    """
    Test prompt example:
    Tata Motors → EV division → India → EV market → Battery → Supplier
    """
    kg = KnowledgeGraph()

    # Build the multi-hop chain
    kg.add_edge("Tata Motors", "EV Division", RelationType.SUBSIDIARY_OF)
    kg.add_edge("EV Division", "India", RelationType.LOCATED_IN)
    kg.add_edge("India", "EV Market", RelationType.OPERATES_IN)
    kg.add_edge("EV Market", "Battery", RelationType.DEVELOPS)
    kg.add_edge("Battery", "Supplier", RelationType.SUPPLIES)

    path = kg.find_path("Tata Motors", "Supplier", max_depth=6)

    assert path is not None
    assert path.length == 5
    assert len(path.nodes) == 6
    assert path.nodes[0].label == "Tata Motors"
    assert path.nodes[-1].label == "Supplier"

    # Readable representation
    assert "Tata Motors" in path.readable_path
    assert "Supplier" in path.readable_path
    assert "subsidiary_of" in path.readable_path
    assert "supplies" in path.readable_path


def test_competitor_and_ecosystem_discovery():
    kg = KnowledgeGraph()

    # Set up ecosystem
    kg.add_edge("Tata Motors", "Mahindra", RelationType.COMPETES_WITH, source_type=EntityType.COMPANY, target_type=EntityType.COMPANY)
    kg.add_edge("Tata Motors", "MG Motor", RelationType.COMPETES_WITH, source_type=EntityType.COMPANY, target_type=EntityType.COMPANY)
    kg.add_edge("Tata Motors", "Indian EV Market", RelationType.OPERATES_IN, source_type=EntityType.COMPANY, target_type=EntityType.MARKET)
    kg.add_edge("Tata Motors", "Nexon EV", RelationType.MANUFACTURES, source_type=EntityType.COMPANY, target_type=EntityType.PRODUCT)
    kg.add_edge("Gotion High-Tech", "Tata Motors", RelationType.SUPPLIES, source_type=EntityType.COMPANY, target_type=EntityType.COMPANY)

    # 1. Competitors
    competitors = kg.find_competitors("Tata Motors")
    assert len(competitors) == 2
    comp_labels = [c.label for c in competitors]
    assert "Mahindra" in comp_labels
    assert "MG Motor" in comp_labels

    # 2. Ecosystem
    eco = kg.find_market_ecosystem("Tata Motors")
    assert eco["company"]["label"] == "Tata Motors"
    assert len(eco["markets"]) == 1
    assert eco["markets"][0]["label"] == "Indian EV Market"
    assert len(eco["products"]) == 1
    assert eco["products"][0]["label"] == "Nexon EV"
    assert len(eco["suppliers"]) == 1
    assert eco["suppliers"][0]["label"] == "Gotion High-Tech"
    assert len(eco["competitors"]) == 2


def test_policy_impact_tracing():
    kg = KnowledgeGraph()

    kg.add_edge("FAME II Scheme", "Electric Vehicles", RelationType.AFFECTS, source_type=EntityType.POLICY, target_type=EntityType.MARKET)
    kg.add_edge("FAME II Scheme", "Automotive Sector", RelationType.REGULATES, source_type=EntityType.POLICY, target_type=EntityType.INDUSTRY)

    impacts = kg.find_policy_impacts("FAME II Scheme")
    assert impacts["policy"]["label"] == "FAME II Scheme"
    assert len(impacts["affected_markets"]) == 1
    assert impacts["affected_markets"][0]["label"] == "Electric Vehicles"
    assert len(impacts["regulated_industries"]) == 1
    assert impacts["regulated_industries"][0]["label"] == "Automotive Sector"


def test_graph_export_and_import():
    kg1 = KnowledgeGraph()
    kg1.add_edge("Tata Motors", "India", RelationType.LOCATED_IN)
    kg1.add_edge("Tata Motors", "Nexon EV", RelationType.MANUFACTURES)

    data = kg1.export_graph()
    assert data["total_nodes"] == 3
    assert data["total_edges"] == 2

    # Import into fresh graph
    kg2 = KnowledgeGraph()
    kg2.import_graph(data)

    exported2 = kg2.export_graph()
    assert exported2["total_nodes"] == 3
    assert exported2["total_edges"] == 2
    assert kg2.find_path("Tata Motors", "Nexon EV") is not None


@pytest.mark.asyncio
async def test_memory_and_graph_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Prepopulate
        await entity_memory.upsert_entity(
            name="Tesla",
            entity_type=EntityType.COMPANY,
            industry="Automotive",
            country="USA"
        )
        await entity_memory.record_conclusion(
            topic="Autonomous Driving",
            conclusion_text="End-to-end neural network driving models surpass rule-based planners in latency and corner-case handling."
        )
        knowledge_graph.add_edge("Tesla", "Full Self Driving", RelationType.MANUFACTURES)
        knowledge_graph.add_edge("Tesla", "Rivian", RelationType.COMPETES_WITH)

        # 1. GET /api/v1/memory/entities
        res_ent = await client.get("/api/v1/memory/entities?query=Tesla")
        assert res_ent.status_code == 200
        ents = res_ent.json()
        assert len(ents) == 1
        assert ents[0]["name"] == "Tesla"

        # 2. GET /api/v1/memory/conclusions
        res_conc = await client.get("/api/v1/memory/conclusions?topic=Autonomous")
        assert res_conc.status_code == 200
        concs = res_conc.json()
        assert len(concs) == 1
        assert "End-to-end neural network" in concs[0]["conclusion_text"]

        # 3. GET /api/v1/memory/graph
        res_graph = await client.get("/api/v1/memory/graph")
        assert res_graph.status_code == 200
        g_data = res_graph.json()
        assert g_data["total_nodes"] >= 3

        # 4. POST /api/v1/memory/graph/query (path search)
        res_query = await client.post(
            "/api/v1/memory/graph/query",
            json={"source_entity": "Tesla", "target_entity": "Full Self Driving"}
        )
        assert res_query.status_code == 200
        q_data = res_query.json()
        assert q_data["found"] is True
        assert q_data["path"]["length"] == 1

        # 5. GET /api/v1/memory/ecosystem/Tesla
        res_eco = await client.get("/api/v1/memory/ecosystem/Tesla")
        assert res_eco.status_code == 200
        eco_data = res_eco.json()
        assert eco_data["company"]["label"] == "Tesla"
        assert len(eco_data["competitors"]) == 1
