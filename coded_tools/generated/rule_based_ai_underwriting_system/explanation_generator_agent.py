from __future__ import annotations

from typing import Dict

from .data_models import ExplainabilityLog


class ExplanationGeneratorAgent:
    def build_audit_output(
        self,
        decision_payload: Dict[str, object],
        explainability_log: ExplainabilityLog,
    ) -> Dict[str, object]:
        return {
            "case_id": decision_payload["case_id"],
            "final_decision": decision_payload["final_decision"],
            "rules_used": decision_payload["rules_used"],
            "step_by_step_reasoning_chain": list(explainability_log.decision_path),
            "supporting_case_attributes": dict(explainability_log.input_attributes),
            "confidence_level": decision_payload["confidence_level"],
            "audit_log": {
                "rules_triggered": list(explainability_log.rules_triggered),
                "explanation_summary": explainability_log.explanation_summary,
                "decision_matches_expected": decision_payload["decision_matches_expected"],
                "selected_rule_id": decision_payload["selected_rule_id"],
            },
            "historical_comparison": decision_payload["historical_comparison"],
        }
