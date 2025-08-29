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

    def _count_rel(self, kg: KnowledgeGraphManager, rel: str) -> int:
        rows = kg.run_query(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS c", {})
        return int(rows[0]["c"]) if rows else 0

    def enrich_relationships(self) -> dict:
        """Run robust Cypher passes and return per-relationship deltas."""
        kg = KnowledgeGraphManager()
        deltas: dict[str, int] = {}

        def run_with_delta(name: str, merge_cypher: str) -> None:
            before = self._count_rel(kg, name)
            kg.run_query(merge_cypher, {}, cache=False)
            after = self._count_rel(kg, name)
            deltas[name] = max(0, after - before)

        run_with_delta(
            "RELATED_TO",
            (
                "MATCH (f1:Fact)-[:HAS_FACT]-(d1:Document), (f2:Fact)-[:HAS_FACT]-(d2:Document) "
                "WHERE id(f1) < id(f2) AND d1.case_id = d2.case_id AND any(p IN f1.parties WHERE p IN f2.parties) "
                "MERGE (f1)-[:RELATED_TO {reason:'party_cooccurrence'}]->(f2)"
            ),
        )
        run_with_delta(
            "CO_SUPPORTS",
            (
                "MATCH (f1:Fact)-[:SUPPORTS]->(e:Element)<-[:SUPPORTS]-(f2:Fact) "
                "WHERE id(f1) < id(f2) "
                "MERGE (f1)-[:CO_SUPPORTS {element:e.name}]->(f2)"
            ),
        )
        run_with_delta(
            "TEMPORALLY_NEAR",
            (
                "MATCH (f1:Fact), (f2:Fact) "
                "WHERE id(f1) < id(f2) AND any(p IN f1.parties WHERE p IN f2.parties) "
                "AND size(f1.dates) > 0 AND size(f2.dates) > 0 "
                "WITH f1, f2, date(f1.dates[0]) AS d1, date(f2.dates[0]) AS d2 "
                "WHERE abs(duration.between(d1, d2).days) <= 14 "
                "MERGE (f1)-[:TEMPORALLY_NEAR {days:abs(duration.between(d1,d2).days)}]->(f2)"
            ),
        )
        run_with_delta(
            "SAME_OCCURRENCE",
            (
                "MATCH (f1:Fact), (f2:Fact) "
                "WHERE id(f1) < id(f2) AND any(a IN f1.actions WHERE a IN f2.actions) "
                "AND any(p IN f1.parties WHERE p IN f2.parties) "
                "AND size(f1.dates) > 0 AND size(f2.dates) > 0 "
                "WITH f1, f2, date(f1.dates[0]) AS d1, date(f2.dates[0]) AS d2 "
                "WHERE abs(duration.between(d1, d2).days) <= 1 "
                "MERGE (f1)-[:SAME_OCCURRENCE]->(f2)"
            ),
        )
        run_with_delta(
            "POTENTIAL_CONTRADICTION",
            (
                "MATCH (f1:Fact), (f2:Fact) "
                "WHERE id(f1) < id(f2) AND any(a IN f1.actions WHERE a IN f2.actions) "
                "AND ((toLower(f1.text) CONTAINS ' not ' OR toLower(f1.text) STARTS WITH 'no ' OR toLower(f1.text) CONTAINS ' never ') XOR "
                "     (toLower(f2.text) CONTAINS ' not ' OR toLower(f2.text) STARTS WITH 'no ' OR toLower(f2.text) CONTAINS ' never ')) "
                "MERGE (f1)-[:POTENTIAL_CONTRADICTION]->(f2)"
            ),
        )
        run_with_delta(
            "EVIDENCES",
            (
                "MATCH (f:Fact),(t:TimelineEvent) WHERE size(f.dates) > 0 AND exists(t.date) "
                "WITH f, t, date(f.dates[0]) AS df, date(t.date) AS dt "
                "WHERE abs(duration.between(df, dt).days) <= 3 "
                "MERGE (f)-[:EVIDENCES]->(t)"
            ),
        )
        kg.close()
        return deltas

    def analyze_timeline_paths(self) -> dict:
        kg = KnowledgeGraphManager()
        out: dict = {}
        try:
            rows = kg.run_query(
                "MATCH p=(f:Fact)-[:SUPPORTS]->(:Element)-[:BELONGS_TO]->(:CauseOfAction) RETURN count(p) AS c"
            )
            out["fact_to_cause_paths"] = int(rows[0]["c"]) if rows else 0
        except Exception:
            out["fact_to_cause_paths"] = 0
        finally:
            kg.close()
        return out

    def enrich_causation_and_timeline(self) -> dict:
        """Infer legal causation and timeline relationships.

        Adds the following graph structures:
        - CAUSES between Facts based on predicate/actions/text heuristics
        - OCCURS_BEFORE between consecutive TimelineEvent by date (per case)
        - CAUSES between TimelineEvent when the earlier description suggests causation
        - SAME_TRANSACTION between TimelineEvent that are within 1 day and share >=3 tokens
        Returns a dict of deltas per relationship created.
        """
        kg = KnowledgeGraphManager()
        deltas: dict[str, int] = {}

        def _count(label: str) -> int:
            rows = kg.run_query(f"MATCH ()-[r:{label}]->() RETURN count(r) AS c", {})
            return int(rows[0]["c"]) if rows else 0

        def _delta(rel: str, cypher: str, params: dict | None = None) -> None:
            before = _count(rel)
            kg.run_query(cypher, params or {}, cache=False)
            after = _count(rel)
            deltas[rel] = max(0, after - before)

        # 1) Fact -> Fact CAUSES based on predicate/actions/text
        _delta(
            "CAUSES",
            (
                "MATCH (f1:Fact), (f2:Fact) "
                "WHERE id(f1) < id(f2) "
                "AND (toLower(coalesce(f1.predicate,'')) IN ['causes','caused','results_in','leads_to'] "
                "  OR any(a IN coalesce(f1.actions,[]) WHERE toLower(a) IN ['cause','caused','resulted','led'])) "
                "AND any(p IN coalesce(f1.parties,[]) WHERE p IN coalesce(f2.parties,[])) "
                "MERGE (f1)-[:CAUSES]->(f2)"
            ),
        )

        # 2) Consecutive OCCURS_BEFORE edges between TimelineEvent per case
        _delta(
            "OCCURS_BEFORE",
            (
                "MATCH (t:TimelineEvent) WITH t.case_id AS cid, collect(t) AS ts "
                "WITH cid, [x IN ts | x] AS ts ORDER BY cid "
                "UNWIND CASE WHEN size(ts)>1 THEN range(0, size(ts)-2) ELSE [] END AS i "
                "WITH ts[i] AS a, ts[i+1] AS b "
                "WITH a,b WHERE a.date IS NOT NULL AND b.date IS NOT NULL AND date(a.date) < date(b.date) "
                "MERGE (a)-[:OCCURS_BEFORE]->(b)"
            ),
        )

        # 3) TimelineEvent CAUSES based on description hints and order
        _delta(
            "CAUSES",
            (
                "MATCH (a:TimelineEvent),(b:TimelineEvent) "
                "WHERE a.case_id=b.case_id AND a<>b AND a.date IS NOT NULL AND b.date IS NOT NULL "
                "AND date(a.date) < date(b.date) "
                "AND (toLower(a.description) CONTAINS 'cause' OR toLower(a.description) CONTAINS 'lead to' OR toLower(a.description) CONTAINS 'result in') "
                "MERGE (a)-[:CAUSES]->(b)"
            ),
        )

        # 4) SAME_TRANSACTION between TimelineEvent within 1 day and token overlap >= 3
        _delta(
            "SAME_TRANSACTION",
            (
                "MATCH (t1:TimelineEvent),(t2:TimelineEvent) "
                "WHERE t1.case_id=t2.case_id AND id(t1) < id(t2) AND t1.date IS NOT NULL AND t2.date IS NOT NULL "
                "WITH t1,t2, date(t1.date) AS d1, date(t2.date) AS d2, "
                "split(toLower(t1.description),' ') AS w1, split(toLower(t2.description),' ') AS w2 "
                "WITH t1,t2,d1,d2, [x IN w1 WHERE x IN w2 AND size(x)>=4] AS inter "
                "WHERE abs(duration.between(d1,d2).days) <= 1 AND size(inter) >= 3 "
                "MERGE (t1)-[:SAME_TRANSACTION]->(t2)"
            ),
        )

        kg.close()
        return deltas

    def analyze_timeline_sequences(self) -> dict:
        """Analyze timeline OCCURS_BEFORE paths and return simple stats."""
        kg = KnowledgeGraphManager()
        stats: dict[str, int | float] = {}
        try:
            # Longest path length across cases
            rows = kg.run_query(
                "MATCH p=(a:TimelineEvent)-[:OCCURS_BEFORE*]->(b:TimelineEvent) "
                "RETURN coalesce(max(length(p)),0) AS maxlen"
            )
            stats["max_timeline_chain"] = int(rows[0]["maxlen"]) if rows else 0
        except Exception:
            stats["max_timeline_chain"] = 0
        try:
            # Count of 3-hop sequences
            rows = kg.run_query(
                "MATCH p=(a:TimelineEvent)-[:OCCURS_BEFORE]->(:TimelineEvent)-[:OCCURS_BEFORE]->(c:TimelineEvent) "
                "RETURN count(p) AS c"
            )
            stats["three_hop_sequences"] = int(rows[0]["c"]) if rows else 0
        except Exception:
            stats["three_hop_sequences"] = 0
        finally:
            kg.close()
        return stats
