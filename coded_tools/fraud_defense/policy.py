"""Explicit governance checks for fraud-defense decisions."""

from __future__ import annotations

from typing import Any
from typing import Dict

from coded_tools.fraud_defense.models import RiskLevel


def governance_check(level: RiskLevel, simulation_results: list[Dict[str, Any]], disagreement: Dict[str, Any], evidence_count: int, lifecycle: str = "RECOMMEND") -> Dict[str, Any]:
    """Apply policy rules and return an auditable approval requirement."""
    checks = [
        {"policy_id": "POL-EVIDENCE", "name": "Evidence coverage", "passed": evidence_count >= 3, "detail": "At least three evidence references are required."},
        {"policy_id": "POL-SIM-FIRST", "name": "Simulation before deployment", "passed": bool(simulation_results), "detail": "At least one counterfactual result is required."},
        {"policy_id": "POL-SHADOW", "name": "Shadow first", "passed": lifecycle in {"OBSERVE", "RECOMMEND", "SHADOW"}, "detail": "Controls may not skip shadow mode."},
        {"policy_id": "POL-HIGH-APPROVAL", "name": "Human approval for high risk", "passed": True, "detail": "Approval is required for HIGH and CRITICAL; the approval gate is recorded and enforced separately."},
        {"policy_id": "POL-DISAGREEMENT", "name": "Model disagreement handling", "passed": not disagreement.get("triggered", False) or evidence_count >= 5, "detail": "Disagreement requires additional evidence before approval."},
    ]
    approval_required = level in {RiskLevel.HIGH, RiskLevel.CRITICAL} or disagreement.get("triggered", False)
    autonomous_execution_allowed = not approval_required and all(check["passed"] for check in checks)
    return {
        "checks": checks,
        "all_passed": all(check["passed"] for check in checks),
        "human_approval_required": approval_required,
        "autonomous_execution_allowed": autonomous_execution_allowed,
        "recommended_lifecycle": "SHADOW" if simulation_results else "RECOMMEND",
        "governance_decision": "approve_for_human_review" if all(check["passed"] for check in checks) else "request_more_investigation",
    }
