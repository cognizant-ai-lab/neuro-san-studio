from __future__ import annotations

from typing import Dict, List

from .data_models import CaseRecord, RuleMapping, UnderwritingRule


class ConditionMatcherAgent:
    def match_case(
        self,
        case: CaseRecord,
        mapping: RuleMapping,
        rule_index: Dict[str, UnderwritingRule],
    ) -> Dict[str, object]:
        matched_rules: List[Dict[str, object]] = []
        for rule_id in mapping.applicable_rule_ids:
            rule = rule_index[rule_id]
            matched_rules.append(
                {
                    "rule_id": rule.rule_id,
                    "rule_name": rule.rule_name,
                    "manual_section": rule.condition,
                    "citation_text": rule.criteria,
                    "rule_type": rule.decision,
                    "status": "applicable",
                }
            )

        return {
            "case_id": case.case_id,
            "matched_rules": matched_rules,
            "matched_criteria": list(mapping.matched_criteria),
            "unmatched_criteria": list(mapping.unmatched_criteria),
            "supporting_case_attributes": dict(case.attributes),
            "missing_fields": [],
        }
