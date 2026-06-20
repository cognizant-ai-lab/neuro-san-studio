from __future__ import annotations

from typing import Dict, List

from .data_models import ExpectedDecision, HistoricalDecision, UnderwritingRule


class DecisionEngineAgent:
    PRECEDENCE = {"Exclusion": 4, "Refer": 3, "Load": 2, "Accept": 1}

    def compute_decision(
        self,
        case_id: str,
        matched_rule_ids: List[str],
        rule_index: Dict[str, UnderwritingRule],
        expected: ExpectedDecision,
        historical: HistoricalDecision | None,
    ) -> Dict[str, object]:
        ranked_rules = sorted(
            (rule_index[rule_id] for rule_id in matched_rule_ids),
            key=lambda rule: (-self.PRECEDENCE[rule.decision], rule.rule_id),
        )
        selected_rule = ranked_rules[0] if ranked_rules else None
        computed_decision = selected_rule.decision if selected_rule else "Refer"

        return {
            "case_id": case_id,
            "final_decision": computed_decision,
            "expected_decision": expected.ai_decision,
            "decision_matches_expected": computed_decision == expected.ai_decision,
            "rules_used": list(matched_rule_ids),
            "selected_rule_id": selected_rule.rule_id if selected_rule else None,
            "selected_rule_decision": selected_rule.decision if selected_rule else None,
            "reasoning_steps": list(expected.reasoning_steps),
            "confidence_level": expected.confidence_score,
            "historical_comparison": {
                "historical_decision": historical.underwriting_decision_human if historical else None,
                "historical_rule_ids": historical.applied_rule_ids if historical else [],
                "decision_delta": (
                    None
                    if historical is None or historical.underwriting_decision_human == computed_decision
                    else {
                        "historical": historical.underwriting_decision_human,
                        "current": computed_decision,
                    }
                ),
            },
        }
