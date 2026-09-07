"""Typed primitives used by the Fraud War Room prototype."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import StrEnum
from typing import Any
from typing import Dict
from typing import List


class RiskLevel(StrEnum):
    """Risk tiers used to select investigation depth and approval policy."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class SyntheticEnvironment:
    """All synthetic entities and hidden labels for one reproducible data universe."""

    seed: int
    generated_at: str
    customers: List[Dict[str, Any]] = field(default_factory=list)
    accounts: List[Dict[str, Any]] = field(default_factory=list)
    transactions: List[Dict[str, Any]] = field(default_factory=list)
    devices: List[Dict[str, Any]] = field(default_factory=list)
    merchants: List[Dict[str, Any]] = field(default_factory=list)
    beneficiaries: List[Dict[str, Any]] = field(default_factory=list)
    locations: List[Dict[str, Any]] = field(default_factory=list)
    sessions: List[Dict[str, Any]] = field(default_factory=list)
    cases: List[Dict[str, Any]] = field(default_factory=list)
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    campaigns: List[Dict[str, Any]] = field(default_factory=list)
    investigator_actions: List[Dict[str, Any]] = field(default_factory=list)
    policy_rules: List[Dict[str, Any]] = field(default_factory=list)
    controls: List[Dict[str, Any]] = field(default_factory=list)

    def by_id(self, collection: str, identifier: str) -> Dict[str, Any] | None:
        """Find a record by its conventional ``*_id`` key."""
        records = getattr(self, collection)
        key = f"{collection.rstrip('s')}_id"
        for record in records:
            if record.get(key) == identifier or record.get("id") == identifier:
                return record
        return None

    def case(self, case_id: str) -> Dict[str, Any]:
        """Return a case or raise a clear validation error."""
        for case in self.cases:
            if case["case_id"] == case_id:
                return case
        raise KeyError(f"Unknown synthetic case: {case_id}")

    def public_case(self, case_id: str) -> Dict[str, Any]:
        """Return investigator-safe case data without hidden ground truth."""
        case = dict(self.case(case_id))
        case.pop("ground_truth", None)
        case.pop("_hidden", None)
        return case


@dataclass
class AgentEvent:
    """Concise observable event; no chain-of-thought or secrets are included."""

    agent: str
    action: str
    phase: str
    status: str = "completed"
    latency_ms: int = 0
    confidence: float | None = None
    evidence_reference: str | None = None
    summary: str = ""
    escalation: bool = False

    def as_dict(self) -> Dict[str, Any]:
        """Convert the event to JSON-compatible data."""
        return {
            "agent": self.agent,
            "action": self.action,
            "phase": self.phase,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "confidence": self.confidence,
            "evidence_reference": self.evidence_reference,
            "summary": self.summary,
            "escalation": self.escalation,
        }
