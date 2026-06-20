from __future__ import annotations

from typing import Dict, List

from .data_models import UnderwritingRule


class UWManualReaderAgent:
    def extract_structured_rules(self, rules: List[UnderwritingRule]) -> Dict[str, object]:
        grouped_conditions: Dict[str, int] = {}
        for rule in rules:
            grouped_conditions[rule.condition] = grouped_conditions.get(rule.condition, 0) + 1

        return {
            "manual_version": "packaged_dataset_v1",
            "extraction_scope": "dataset_1_underwriting_manual_rule_base.json",
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "title": rule.rule_name,
                    "condition": rule.condition,
                    "criteria": rule.criteria,
                    "action": rule.decision,
                    "load_percentage": rule.load_percentage,
                    "exclusion_terms": rule.exclusion_terms or [],
                    "citation": "dataset_1_underwriting_manual_rule_base.json",
                    "notes": rule.description,
                }
                for rule in rules
            ],
            "missing_information": [],
            "extraction_confidence": "High",
            "audit_log": {
                "rules_extracted": len(rules),
                "condition_counts": grouped_conditions,
            },
        }
