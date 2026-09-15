"""
Day 88–90 — Knowledge Graph
Represents rich domain entities and relationships:
  - Company → competes_with → Company
  - Company → operates_in → Market
  - Policy → affects → Market
  - Company → manufactures → Product
  - Supplier → supplies → Company / Product
  - Division → subsidiary_of → Company
  - Policy → regulates → Market / Industry
  - Entity → has_evidence → Evidence

Provides multi-hop path finding, neighborhood exploration, ecosystem query,
and graph-augmented context retrieval for deep research agents.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any, Set, Tuple
from pydantic import BaseModel, Field
from collections import deque
from app.utils.helpers import generate_uuid, get_utc_now
from app.memory.entity_memory import EntityType


class RelationType(str, Enum):
    COMPETES_WITH = "competes_with"
    OPERATES_IN = "operates_in"
    AFFECTS = "affects"
    MANUFACTURES = "manufactures"
    SUPPLIES = "supplies"
    SUBSIDIARY_OF = "subsidiary_of"
    REGULATES = "regulates"
    HAS_EVIDENCE = "has_evidence"
    INVESTS_IN = "invests_in"
    DEVELOPS = "develops"
    LOCATED_IN = "located_in"
    PARTNERS_WITH = "partners_with"


class GraphNode(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    label: str
    entity_type: EntityType = EntityType.GENERAL
    properties: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=get_utc_now)


class GraphEdge(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=get_utc_now)


class GraphPath(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    length: int
    readable_path: str


class KnowledgeGraph:
    """
    In-memory / Persistent Knowledge Graph engine for autonomous research agents.
    Supports multi-hop traversal, semantic neighborhood queries, and domain graph reasoning.
    """

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._node_by_label: Dict[str, str] = {}  # normalized_label -> node_id
        self._edges: Dict[str, GraphEdge] = {}
        # Adjacency lists
        self._out_edges: Dict[str, List[str]] = {}  # node_id -> list of edge_ids
        self._in_edges: Dict[str, List[str]] = {}   # node_id -> list of edge_ids

    # -------------------------------------------------------------
    # Node & Edge Management
    # -------------------------------------------------------------
    def add_node(
        self,
        label: str,
        entity_type: EntityType = EntityType.GENERAL,
        properties: Optional[Dict[str, Any]] = None,
        evidence_id: Optional[str] = None,
        node_id: Optional[str] = None
    ) -> GraphNode:
        norm_label = label.strip().lower()
        if norm_label in self._node_by_label:
            existing_id = self._node_by_label[norm_label]
            node = self._nodes[existing_id]
            if properties:
                node.properties.update(properties)
            if evidence_id and evidence_id not in node.evidence_ids:
                node.evidence_ids.append(evidence_id)
            return node

        nid = node_id or generate_uuid()
        node = GraphNode(
            id=nid,
            label=label.strip(),
            entity_type=entity_type,
            properties=properties or {},
            evidence_ids=[evidence_id] if evidence_id else []
        )
        self._nodes[nid] = node
        self._node_by_label[norm_label] = nid
        self._out_edges[nid] = []
        self._in_edges[nid] = []
        return node

    def add_edge(
        self,
        source_label_or_id: str,
        target_label_or_id: str,
        relation_type: RelationType,
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
        evidence_id: Optional[str] = None,
        source_type: EntityType = EntityType.GENERAL,
        target_type: EntityType = EntityType.GENERAL
    ) -> GraphEdge:
        # Resolve source
        src_node = self.get_node(source_label_or_id)
        if not src_node:
            src_node = self.add_node(source_label_or_id, entity_type=source_type)

        # Resolve target
        tgt_node = self.get_node(target_label_or_id)
        if not tgt_node:
            tgt_node = self.add_node(target_label_or_id, entity_type=target_type)

        # Check existing edge of same relation
        for edge_id in self._out_edges.get(src_node.id, []):
            edge = self._edges[edge_id]
            if edge.target_id == tgt_node.id and edge.relation_type == relation_type:
                if properties:
                    edge.properties.update(properties)
                if evidence_id and evidence_id not in edge.evidence_ids:
                    edge.evidence_ids.append(evidence_id)
                edge.weight = max(edge.weight, weight)
                return edge

        # Create new edge
        new_edge = GraphEdge(
            source_id=src_node.id,
            target_id=tgt_node.id,
            relation_type=relation_type,
            weight=weight,
            properties=properties or {},
            evidence_ids=[evidence_id] if evidence_id else []
        )
        self._edges[new_edge.id] = new_edge
        self._out_edges[src_node.id].append(new_edge.id)
        self._in_edges[tgt_node.id].append(new_edge.id)
        return new_edge

    def get_node(self, label_or_id: str) -> Optional[GraphNode]:
        if label_or_id in self._nodes:
            return self._nodes[label_or_id]
        norm = label_or_id.strip().lower()
        if norm in self._node_by_label:
            return self._nodes[self._node_by_label[norm]]
        return None

    def get_outgoing_edges(self, node_id: str) -> List[GraphEdge]:
        return [self._edges[eid] for eid in self._out_edges.get(node_id, [])]

    def get_incoming_edges(self, node_id: str) -> List[GraphEdge]:
        return [self._edges[eid] for eid in self._in_edges.get(node_id, [])]

    # -------------------------------------------------------------
    # Multi-Hop Traversal & Path Finding
    # -------------------------------------------------------------
    def find_path(
        self,
        source_label_or_id: str,
        target_label_or_id: str,
        max_depth: int = 6
    ) -> Optional[GraphPath]:
        """
        Finds the shortest semantic relationship path between two entities
        using Breadth-First Search (BFS).
        e.g., Tata Motors → EV division → India → EV market → Battery → Supplier
        """
        src = self.get_node(source_label_or_id)
        tgt = self.get_node(target_label_or_id)

        if not src or not tgt:
            return None

        if src.id == tgt.id:
            return GraphPath(nodes=[src], edges=[], length=0, readable_path=src.label)

        queue = deque([(src.id, [src.id], [])])  # (current_node_id, node_path, edge_path)
        visited = {src.id}

        while queue:
            curr_id, node_path, edge_path = queue.popleft()

            if len(node_path) - 1 >= max_depth:
                continue

            for edge_id in self._out_edges.get(curr_id, []):
                edge = self._edges[edge_id]
                nxt_id = edge.target_id

                if nxt_id == tgt.id:
                    final_node_path = [self._nodes[nid] for nid in node_path + [nxt_id]]
                    final_edge_path = [self._edges[eid] for eid in edge_path + [edge_id]]
                    
                    readable_elements = []
                    for i, node in enumerate(final_node_path):
                        readable_elements.append(node.label)
                        if i < len(final_edge_path):
                            readable_elements.append(f"──[{final_edge_path[i].relation_type.value}]──>")

                    return GraphPath(
                        nodes=final_node_path,
                        edges=final_edge_path,
                        length=len(final_edge_path),
                        readable_path=" ".join(readable_elements)
                    )

                if nxt_id not in visited:
                    visited.add(nxt_id)
                    queue.append((nxt_id, node_path + [nxt_id], edge_path + [edge_id]))

        return None

    # -------------------------------------------------------------
    # Neighborhood & Domain Exploration
    # -------------------------------------------------------------
    def get_neighborhood(
        self,
        node_label_or_id: str,
        depth: int = 2,
        relation_filter: Optional[List[RelationType]] = None
    ) -> Dict[str, Any]:
        """
        Extracts subgraph centered at node up to specified depth.
        """
        root = self.get_node(node_label_or_id)
        if not root:
            return {"nodes": [], "edges": []}

        visited_nodes: Set[str] = {root.id}
        collected_edges: Set[str] = set()

        queue = deque([(root.id, 0)])

        while queue:
            curr_id, curr_depth = queue.popleft()
            if curr_depth >= depth:
                continue

            # Outgoing & Incoming edges
            candidate_edges = self._out_edges.get(curr_id, []) + self._in_edges.get(curr_id, [])
            for eid in candidate_edges:
                edge = self._edges[eid]
                if relation_filter and edge.relation_type not in relation_filter:
                    continue

                collected_edges.add(eid)
                neighbor_id = edge.target_id if edge.source_id == curr_id else edge.source_id
                if neighbor_id not in visited_nodes:
                    visited_nodes.add(neighbor_id)
                    queue.append((neighbor_id, curr_depth + 1))

        nodes_list = [self._nodes[nid].model_dump(mode="json") for nid in visited_nodes]
        edges_list = [self._edges[eid].model_dump(mode="json") for eid in collected_edges]

        return {
            "root_node": root.model_dump(mode="json"),
            "nodes": nodes_list,
            "edges": edges_list,
            "total_nodes": len(nodes_list),
            "total_edges": len(edges_list)
        }

    def find_competitors(self, company_label_or_id: str) -> List[GraphNode]:
        """Find all competitors of a company."""
        comp = self.get_node(company_label_or_id)
        if not comp:
            return []

        competitors = []
        # Check direct outgoing competes_with
        for eid in self._out_edges.get(comp.id, []):
            edge = self._edges[eid]
            if edge.relation_type == RelationType.COMPETES_WITH:
                competitors.append(self._nodes[edge.target_id])

        # Check incoming competes_with
        for eid in self._in_edges.get(comp.id, []):
            edge = self._edges[eid]
            if edge.relation_type == RelationType.COMPETES_WITH:
                competitors.append(self._nodes[edge.source_id])

        # Deduplicate
        seen = set()
        unique = []
        for c in competitors:
            if c.id not in seen:
                seen.add(c.id)
                unique.append(c)
        return unique

    def find_market_ecosystem(self, company_label_or_id: str) -> Dict[str, Any]:
        """
        Discovers the complete company ecosystem:
        - Markets operated in
        - Products manufactured
        - Key suppliers
        - Direct competitors
        - Subsidiaries / divisions
        """
        node = self.get_node(company_label_or_id)
        if not node:
            return {}

        markets = []
        products = []
        suppliers = []
        subsidiaries = []
        competitors = self.find_competitors(node.id)

        for eid in self._out_edges.get(node.id, []):
            edge = self._edges[eid]
            target = self._nodes[edge.target_id]
            if edge.relation_type == RelationType.OPERATES_IN:
                markets.append(target)
            elif edge.relation_type == RelationType.MANUFACTURES:
                products.append(target)
            elif edge.relation_type == RelationType.SUBSIDIARY_OF:
                pass

        # Check who supplies this company (Supplier → supplies → Company)
        for eid in self._in_edges.get(node.id, []):
            edge = self._edges[eid]
            source = self._nodes[edge.source_id]
            if edge.relation_type == RelationType.SUPPLIES:
                suppliers.append(source)
            elif edge.relation_type == RelationType.SUBSIDIARY_OF:
                subsidiaries.append(source)

        return {
            "company": node.model_dump(mode="json"),
            "markets": [m.model_dump(mode="json") for m in markets],
            "products": [p.model_dump(mode="json") for p in products],
            "suppliers": [s.model_dump(mode="json") for s in suppliers],
            "competitors": [c.model_dump(mode="json") for c in competitors],
            "subsidiaries": [sub.model_dump(mode="json") for sub in subsidiaries],
        }

    def find_policy_impacts(self, policy_label_or_id: str) -> Dict[str, Any]:
        """Traces policy impacts across markets and companies."""
        pol = self.get_node(policy_label_or_id)
        if not pol:
            return {}

        affected_markets = []
        regulated_industries = []

        for eid in self._out_edges.get(pol.id, []):
            edge = self._edges[eid]
            target = self._nodes[edge.target_id]
            if edge.relation_type == RelationType.AFFECTS:
                affected_markets.append(target)
            elif edge.relation_type == RelationType.REGULATES:
                regulated_industries.append(target)

        return {
            "policy": pol.model_dump(mode="json"),
            "affected_markets": [m.model_dump(mode="json") for m in affected_markets],
            "regulated_industries": [i.model_dump(mode="json") for i in regulated_industries],
        }

    # -------------------------------------------------------------
    # Serialization & Graph Ingestion
    # -------------------------------------------------------------
    def export_graph(self) -> Dict[str, Any]:
        """Export entire knowledge graph for visualization or persistence."""
        nodes = [n.model_dump(mode="json") for n in self._nodes.values()]
        edges = [e.model_dump(mode="json") for e in self._edges.values()]
        return {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "timestamp": get_utc_now().isoformat()
        }

    def import_graph(self, data: Dict[str, Any]):
        """Import nodes and edges into graph."""
        for n_data in data.get("nodes", []):
            self.add_node(
                label=n_data["label"],
                entity_type=EntityType(n_data.get("entity_type", "general")),
                properties=n_data.get("properties", {}),
                node_id=n_data.get("id")
            )
        for e_data in data.get("edges", []):
            src_node = self._nodes.get(e_data["source_id"])
            tgt_node = self._nodes.get(e_data["target_id"])
            if src_node and tgt_node:
                self.add_edge(
                    source_label_or_id=src_node.label,
                    target_label_or_id=tgt_node.label,
                    relation_type=RelationType(e_data["relation_type"]),
                    weight=float(e_data.get("weight", 1.0)),
                    properties=e_data.get("properties", {})
                )

    def ingest_from_research(
        self,
        research_id: str,
        topic: str,
        entities: Optional[List[Dict[str, Any]]] = None,
        relationships: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Auto-populates knowledge graph from structured research extractions.
        """
        # Register topic node
        self.add_node(label=topic, entity_type=EntityType.GENERAL, properties={"research_id": research_id})

        if entities:
            for ent in entities:
                name = ent.get("name")
                etype = ent.get("entity_type", EntityType.GENERAL)
                if isinstance(etype, str):
                    try:
                        etype = EntityType(etype.lower())
                    except ValueError:
                        etype = EntityType.GENERAL
                self.add_node(
                    label=name,
                    entity_type=etype,
                    properties=ent.get("properties", {})
                )

        if relationships:
            for rel in relationships:
                src = rel.get("source")
                tgt = rel.get("target")
                rtype = rel.get("relation_type", RelationType.OPERATES_IN)
                if isinstance(rtype, str):
                    try:
                        rtype = RelationType(rtype.lower())
                    except ValueError:
                        rtype = RelationType.OPERATES_IN
                if src and tgt:
                    self.add_edge(
                        source_label_or_id=src,
                        target_label_or_id=tgt,
                        relation_type=rtype,
                        weight=float(rel.get("weight", 1.0)),
                        properties=rel.get("properties", {})
                    )

    def clear(self):
        self._nodes.clear()
        self._node_by_label.clear()
        self._edges.clear()
        self._out_edges.clear()
        self._in_edges.clear()


knowledge_graph = KnowledgeGraph()
