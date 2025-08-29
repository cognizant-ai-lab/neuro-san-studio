import networkx as nx
from neuro_san.interfaces.coded_tool import CodedTool
from .knowledge_graph_manager import KnowledgeGraphManager


class GraphAnalyzer(CodedTool):
    """Analyze relationships in the knowledge graph."""

    def analyze_centrality(self, subnet: str | None = None) -> list[dict]:
        kg = KnowledgeGraphManager()
        nodes, edges = kg.get_subgraph(subnet or "*")
        kg.close()

        graph = nx.DiGraph()
        for n in nodes:
            graph.add_node(n["id"], label=n.get("labels", [""])[0])
        for e in edges:
            graph.add_edge(e["source"], e["target"], type=e.get("type"))

        centrality = nx.degree_centrality(graph)
        ranked = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
        return [{"id": nid, "score": round(score, 3)} for nid, score in ranked]

    def enrich_relationships(self) -> None:
        """Run robust Cypher passes to discover deeper links beyond trivial metadata.

        - Party co-occurrence links across documents for the same case
        - Element-level co-support links between facts
        - Temporal proximity links within a 14-day window for shared parties

        Writes use MERGE for idempotency.
        """
        kg = KnowledgeGraphManager()
        kg.run_query(
            (
                "MATCH (f1:Fact)-[:HAS_FACT]-(d1:Document), (f2:Fact)-[:HAS_FACT]-(d2:Document) "
                "WHERE id(f1) < id(f2) AND d1.case_id = d2.case_id AND any(p IN f1.parties WHERE p IN f2.parties) "
                "MERGE (f1)-[:RELATED_TO {reason:'party_cooccurrence'}]->(f2)"
            ),
            cache=False,
        )
        kg.run_query(
            (
                "MATCH (f1:Fact)-[:SUPPORTS]->(e:Element)<-[:SUPPORTS]-(f2:Fact) "
                "WHERE id(f1) < id(f2) "
                "MERGE (f1)-[:CO_SUPPORTS {element:e.name}]->(f2)"
            ),
            cache=False,
        )
        kg.run_query(
            (
                "MATCH (f1:Fact), (f2:Fact) "
                "WHERE id(f1) < id(f2) AND any(p IN f1.parties WHERE p IN f2.parties) "
                "AND size(f1.dates) > 0 AND size(f2.dates) > 0 "
                "WITH f1, f2, date(f1.dates[0]) AS d1, date(f2.dates[0]) AS d2 "
                "WHERE abs(duration.between(d1, d2).days) <= 14 "
                "MERGE (f1)-[:TEMPORALLY_NEAR {days:abs(duration.between(d1,d2).days)}]->(f2)"
            ),
            cache=False,
        )
        kg.close()
