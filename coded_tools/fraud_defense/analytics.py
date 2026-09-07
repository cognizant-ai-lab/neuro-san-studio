"""Deterministic transaction, timeline, and campaign graph analytics."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from statistics import median
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Tuple

from coded_tools.fraud_defense.models import SyntheticEnvironment


def _dt(value: str) -> datetime:
    """Parse an ISO timestamp emitted by the generator."""
    return datetime.fromisoformat(value.rstrip("Z"))


class TransactionAnalytics:
    """Exact feature calculations over synthetic transactions."""

    def __init__(self, environment: SyntheticEnvironment):
        self.environment = environment
        self._by_case: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._graph: FraudGraph | None = None
        for transaction in environment.transactions:
            self._by_case[transaction["case_id"]].append(transaction)

    def transactions_for_case(self, case_id: str, include_history: bool = True) -> List[Dict[str, Any]]:
        """Return case transactions ordered by event time."""
        records = self._by_case[case_id]
        if not include_history:
            records = [record for record in records if record["event_type"] != "historical_purchase"]
        return sorted(records, key=lambda item: item["timestamp"])

    def current_transactions(self, case_id: str) -> List[Dict[str, Any]]:
        """Return non-history events for one case."""
        return self.transactions_for_case(case_id, include_history=False)

    def customer_profile(self, case_id: str) -> Dict[str, Any]:
        """Calculate the customer's historical behavioral baseline."""
        current = self.current_transactions(case_id)
        if not current:
            return {}
        history = [item for item in self.transactions_for_case(case_id) if item["event_type"] == "historical_purchase"]
        customer_id = current[0]["customer_id"]
        amounts = [float(item["amount"]) for item in history]
        return {
            "customer_id": customer_id,
            "historical_transaction_count": len(history),
            "median_amount": round(median(amounts), 2) if amounts else 0.0,
            "max_amount": round(max(amounts), 2) if amounts else 0.0,
            "usual_locations": sorted({item["location"] for item in history}),
            "usual_channels": sorted({item["channel"] for item in history}),
            "usual_devices": sorted({item["device_id"] for item in history}),
            "usual_beneficiaries": sorted({item["beneficiary_id"] for item in history}),
        }

    def signals(self, case_id: str) -> Dict[str, Any]:
        """Compute explainable behavioral signals without using hidden labels."""
        current = self.current_transactions(case_id)
        if not current:
            raise KeyError(f"No transactions for case {case_id}")
        history = [item for item in self.transactions_for_case(case_id) if item["event_type"] == "historical_purchase"]
        profile = self.customer_profile(case_id)
        latest = current[-1]
        latest_time = _dt(latest["timestamp"])
        recent = [item for item in current if latest_time - _dt(item["timestamp"]) <= timedelta(minutes=30)]
        historical_amounts = [float(item["amount"]) for item in history] or [1.0]
        baseline = max(median(historical_amounts), 1.0)
        amount_ratio = float(latest["amount"]) / baseline
        amount_anomaly = min(1.0, max(0.0, (amount_ratio - 2.0) / 10.0))
        new_beneficiary = latest["beneficiary_id"] not in profile.get("usual_beneficiaries", [])
        new_device = latest["device_id"] not in profile.get("usual_devices", [])
        new_location = latest["location"] not in profile.get("usual_locations", [])
        event_names = [item["event_type"] for item in current]
        has_test_then_transfer = "test_transfer" in event_names and "high_value_transfer" in event_names
        has_dormant_gap = any(
            _dt(right["timestamp"]) - _dt(left["timestamp"]) >= timedelta(minutes=20)
            for left, right in zip(current, current[1:])
        )
        if self._graph is None:
            self._graph = FraudGraph(self.environment)
        graph = self._graph
        graph_summary = graph.findings(case_id)
        network_link = len(graph_summary["linked_accounts"])
        velocity_score = min(1.0, max(0.0, (len(recent) - 1) / 4.0))
        sequence_score = min(1.0, 0.3 * bool(has_test_then_transfer) + 0.2 * bool(has_dormant_gap) + 0.2 * bool("connected_account_movement" in event_names) + 0.3 * bool(new_beneficiary and new_device))
        score = (
            0.20 * velocity_score
            + 0.18 * amount_anomaly
            + 0.16 * bool(new_beneficiary)
            + 0.16 * bool(new_device)
            + 0.10 * bool(new_location)
            + 0.12 * sequence_score
            + 0.08 * min(1.0, network_link / 3.0)
        )
        reasons = []
        if len(recent) >= 3:
            reasons.append("velocity_spike")
        if amount_ratio >= 5:
            reasons.append("amount_outlier_against_customer_baseline")
        if new_beneficiary:
            reasons.append("beneficiary_not_seen_in_history")
        if new_device:
            reasons.append("device_not_seen_in_history")
        if new_location:
            reasons.append("location_not_seen_in_history")
        if has_test_then_transfer:
            reasons.append("test_then_high_value_sequence")
        if network_link:
            reasons.append("connected_account_activity")
        return {
            "case_id": case_id,
            "latest_transaction_id": latest["transaction_id"],
            "velocity_30m": len(recent),
            "amount_ratio_to_median": round(amount_ratio, 3),
            "amount_anomaly": round(amount_anomaly, 3),
            "new_beneficiary": bool(new_beneficiary),
            "new_device": bool(new_device),
            "new_location": bool(new_location),
            "network_link_count": network_link,
            "has_test_then_transfer": bool(has_test_then_transfer),
            "has_dormant_gap": bool(has_dormant_gap),
            "sequence_score": round(sequence_score, 3),
            "risk_score": round(score, 3),
            "reason_codes": reasons,
            "baseline": profile,
        }

    def timeline(self, case_id: str) -> Dict[str, Any]:
        """Reconstruct a chronological process view for the case."""
        events = []
        for item in self.transactions_for_case(case_id, include_history=False):
            phase = {
                "session_start": "access",
                "beneficiary_added": "setup",
                "test_transfer": "probing",
                "high_value_transfer": "extraction",
                "connected_account_movement": "laundering",
            }.get(item["event_type"], "payment")
            events.append({
                "timestamp": item["timestamp"],
                "transaction_id": item["transaction_id"],
                "event_type": item["event_type"],
                "phase": phase,
                "amount": item["amount"],
                "device_id": item["device_id"],
                "location": item["location"],
            })
        return {"case_id": case_id, "event_count": len(events), "events": events, "sequence": [item["phase"] for item in events]}


class FraudGraph:
    """Small deterministic property graph for campaign investigations."""

    def __init__(self, environment: SyntheticEnvironment):
        self.environment = environment
        self.adjacency: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self.edges_by_node: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.edges: List[Dict[str, Any]] = []
        self._build()

    @staticmethod
    def node(kind: str, identifier: str) -> str:
        """Build a stable graph node identifier."""
        return f"{kind}:{identifier}"

    def _connect(self, left: str, right: str, relation: str, reference: str | None = None, traverse: bool = True) -> None:
        edge = {"source": left, "target": right, "relation": relation, "reference": reference}
        self.edges.append(edge)
        self.edges_by_node[left].append(edge)
        self.edges_by_node[right].append(edge)
        if traverse:
            self.adjacency[left][right] = edge
            self.adjacency[right][left] = {**edge, "source": right, "target": left}

    def _build(self) -> None:
        for transaction in self.environment.transactions:
            case = self.node("case", transaction["case_id"])
            account = self.node("account", transaction["account_id"])
            customer = self.node("customer", transaction["customer_id"])
            device = self.node("device", transaction["device_id"])
            beneficiary = self.node("beneficiary", transaction["beneficiary_id"])
            merchant = self.node("merchant", transaction["merchant_id"])
            tx = self.node("transaction", transaction["transaction_id"])
            self._connect(case, tx, "contains", transaction["transaction_id"])
            self._connect(tx, account, "posted_to", transaction["transaction_id"])
            self._connect(account, customer, "owned_by", transaction["transaction_id"])
            self._connect(tx, device, "initiated_on", transaction["transaction_id"])
            self._connect(tx, beneficiary, "sent_to", transaction["transaction_id"])
            # Common merchants are retained for evidence display but are not
            # traversal edges; otherwise one national merchant would collapse
            # every customer into a single campaign component.
            self._connect(tx, merchant, "merchant", transaction["transaction_id"], traverse=False)
        for session in self.environment.sessions:
            self._connect(self.node("session", session["session_id"]), self.node("device", session["device_id"]), "used_device", session["session_id"])
            self._connect(self.node("session", session["session_id"]), self.node("account", session["account_id"]), "authenticated_for", session["session_id"])
        for campaign in self.environment.campaigns:
            beneficiary = self.node("beneficiary", campaign["beneficiary_id"])
            for account_id in campaign["account_ids"]:
                self._connect(beneficiary, self.node("account", account_id), "campaign_link", campaign["campaign_id"])

    def component(self, start: str) -> List[str]:
        """Return all connected nodes reachable from a node."""
        if start not in self.adjacency:
            return []
        seen = {start}
        pending = [start]
        while pending:
            current = pending.pop()
            for neighbor in self.adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    pending.append(neighbor)
        return sorted(seen)

    def shortest_path(self, start: str, target: str) -> List[str]:
        """Find a shortest path without delegating traversal to an LLM."""
        if start == target:
            return [start]
        pending: List[Tuple[str, List[str]]] = [(start, [start])]
        visited = {start}
        while pending:
            current, path = pending.pop(0)
            for neighbor in sorted(self.adjacency[current]):
                if neighbor == target:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append((neighbor, path + [neighbor]))
        return []

    def centrality(self, nodes: Iterable[str] | None = None) -> List[Dict[str, Any]]:
        """Return degree centrality ordered by degree then node ID."""
        selected = set(nodes) if nodes is not None else set(self.adjacency)
        denominator = max(1, len(self.adjacency) - 1)
        ranked = [{"node": node, "degree": len(self.adjacency[node]), "centrality": round(len(self.adjacency[node]) / denominator, 4)} for node in selected]
        return sorted(ranked, key=lambda item: (-item["degree"], item["node"]))

    def findings(self, case_id: str) -> Dict[str, Any]:
        """Return investigator-safe graph findings for a case."""
        case_node = self.node("case", case_id)
        component = self.component(case_node)
        account_nodes = [node for node in component if node.startswith("account:")]
        beneficiary_nodes = [node for node in component if node.startswith("beneficiary:")]
        device_nodes = [node for node in component if node.startswith("device:")]
        linked_accounts = sorted(node.split(":", 1)[1] for node in account_nodes if node != self.node("account", self.environment.case(case_id)["account_id"]))
        relevant_edges = []
        seen_edges = set()
        for node in component:
            for edge in self.edges_by_node[node]:
                edge_key = (edge["source"], edge["target"], edge["relation"], edge["reference"])
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    relevant_edges.append(edge)
        ranked = self.centrality(component)[:8]
        return {
            "case_id": case_id,
            "component_size": len(component),
            "linked_accounts": linked_accounts,
            "beneficiaries": sorted(node.split(":", 1)[1] for node in beneficiary_nodes),
            "devices": sorted(node.split(":", 1)[1] for node in device_nodes),
            "central_entities": ranked,
            "campaign_signal": bool(len(linked_accounts) or len(beneficiary_nodes) > 1 or len(device_nodes) > 1),
            "edges": relevant_edges[:80],
        }

    def public_subgraph(self, case_id: str, limit: int = 30) -> Dict[str, Any]:
        """Return a compact graph payload for the dashboard."""
        findings = self.findings(case_id)
        nodes = set()
        for edge in findings["edges"]:
            nodes.add(edge["source"])
            nodes.add(edge["target"])
        node_list = []
        for node in sorted(nodes)[:limit]:
            kind, identifier = node.split(":", 1)
            node_list.append({"id": node, "type": kind, "label": identifier})
        keep = {node["id"] for node in node_list}
        return {"nodes": node_list, "edges": [edge for edge in findings["edges"] if edge["source"] in keep and edge["target"] in keep]}
