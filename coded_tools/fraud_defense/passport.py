"""Decision Passport construction and schema validation."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import Iterable

from coded_tools.fraud_defense.models import RiskLevel


PASSPORT_KEYS = {
    "case_id", "decision_id", "risk_level", "initial_alert", "hypotheses", "supporting_evidence", "counter_evidence",
    "missing_evidence", "graph_findings", "timeline_findings", "model_assessments", "model_disagreement", "attacker_analysis",
    "defense_candidates", "simulation_results", "selected_defense", "policy_checks", "human_approval_required", "decision",
    "confidence", "reason_codes", "created_at", "audit_events", "deployment_lifecycle",
}


def build_passport(case_id: str, level: RiskLevel, alert: Dict[str, Any], hypotheses: list[Dict[str, Any]], evidence: Dict[str, Any], graph: Dict[str, Any], timeline: Dict[str, Any], routing: Dict[str, Any], attacker: Dict[str, Any], defenses: list[Dict[str, Any]], simulations: list[Dict[str, Any]], selected_defense: Dict[str, Any], governance: Dict[str, Any], decision: str, confidence: float, reason_codes: Iterable[str], audit_events: list[Dict[str, Any]], deployment_lifecycle: str = "OBSERVE", created_at: str | None = None) -> Dict[str, Any]:
    """Build a complete concise passport, never including chain-of-thought."""
    passport = {
        "case_id": case_id,
        "decision_id": f"DEC-{case_id.replace('CASE-', '')}-001",
        "risk_level": level.value,
        "initial_alert": alert,
        "hypotheses": hypotheses,
        "supporting_evidence": evidence.get("supporting", []),
        "counter_evidence": evidence.get("counter", []),
        "missing_evidence": evidence.get("missing", []),
        "graph_findings": graph,
        "timeline_findings": timeline,
        "model_assessments": routing.get("assessments", []),
        "model_disagreement": routing.get("disagreement", {}),
        "attacker_analysis": attacker,
        "defense_candidates": defenses,
        "simulation_results": simulations,
        "selected_defense": selected_defense,
        "policy_checks": governance,
        "human_approval_required": governance.get("human_approval_required", True),
        "decision": decision,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "reason_codes": sorted(set(reason_codes)),
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "audit_events": audit_events,
        "deployment_lifecycle": deployment_lifecycle,
    }
    validate_passport(passport)
    return passport


def validate_passport(passport: Dict[str, Any]) -> None:
    """Raise a clear error when a passport is incomplete or unsafe."""
    missing = PASSPORT_KEYS - set(passport)
    if missing:
        raise ValueError(f"Decision Passport missing keys: {sorted(missing)}")
    if passport["risk_level"] not in {level.value for level in RiskLevel}:
        raise ValueError("Decision Passport has an invalid risk level")
    if not 0 <= float(passport["confidence"]) <= 1:
        raise ValueError("Decision Passport confidence must be between 0 and 1")
    if not isinstance(passport["audit_events"], list):
        raise ValueError("Decision Passport audit_events must be a list")
