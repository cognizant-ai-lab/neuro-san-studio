from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .data_models import (
    CaseRecord,
    ExpectedDecision,
    ExplainabilityLog,
    HistoricalDecision,
    RuleMapping,
    UnderwritingRule,
)


class DataLoader:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent

    def _load_json(self, filename: str) -> dict:
        with (self.data_dir / filename).open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def load_rules(self) -> List[UnderwritingRule]:
        payload = self._load_json("dataset_1_underwriting_manual_rule_base.json")
        return [
            UnderwritingRule(
                rule_id=item["rule_id"],
                rule_name=item["rule_name"],
                condition=item["condition"],
                criteria=item["criteria"],
                decision=item["decision"],
                load_percentage=item.get("load_percentage"),
                exclusion_terms=item.get("exclusion_terms"),
                description=item.get("description", ""),
            )
            for item in payload["underwriting_manual"]
        ]

    def load_cases(self) -> List[CaseRecord]:
        payload = self._load_json("dataset_2_structured_case_data.json")
        records: List[CaseRecord] = []
        for item in payload["case_data"]:
            case_id = item["case_id"]
            attrs = {key: value for key, value in item.items() if key != "case_id"}
            records.append(CaseRecord(case_id=case_id, attributes=attrs))
        return records

    def load_historical_decisions(self) -> List[HistoricalDecision]:
        payload = self._load_json("dataset_3_historical_underwriting_decisions.json")
        return [
            HistoricalDecision(
                case_id=item["case_id"],
                underwriting_decision_human=item["underwriting_decision_human"],
                decision_reason_human=item["decision_reason_human"],
                applied_rule_ids=item["applied_rule_ids"],
            )
            for item in payload["historical_decisions"]
        ]

    def load_rule_mappings(self) -> List[RuleMapping]:
        payload = self._load_json("dataset_4_rule_to_case_mapping.json")
        return [
            RuleMapping(
                case_id=item["case_id"],
                applicable_rule_ids=item["applicable_rule_ids"],
                matched_criteria=item["matched_criteria"],
                unmatched_criteria=item["unmatched_criteria"],
            )
            for item in payload["rule_case_mapping"]
        ]

    def load_expected_decisions(self) -> List[ExpectedDecision]:
        payload = self._load_json("dataset_5_ai_decision_output_expected.json")
        return [
            ExpectedDecision(
                case_id=item["case_id"],
                ai_decision=item["ai_decision"],
                rules_used=item["rules_used"],
                reasoning_steps=item["reasoning_steps"],
                confidence_score=item["confidence_score"],
            )
            for item in payload["ai_decisions"]
        ]

    def load_explainability_logs(self) -> List[ExplainabilityLog]:
        payload = self._load_json("dataset_6_explainability_audit_trail.json")
        return [
            ExplainabilityLog(
                case_id=item["case_id"],
                input_attributes=item["input_attributes"],
                rules_triggered=item["rules_triggered"],
                decision_path=item["decision_path"],
                final_decision=item["final_decision"],
                explanation_summary=item["explanation_summary"],
            )
            for item in payload["explainability_logs"]
        ]

    def load_all(self) -> Dict[str, object]:
        rules = self.load_rules()
        cases = self.load_cases()
        historical = self.load_historical_decisions()
        mappings = self.load_rule_mappings()
        expected = self.load_expected_decisions()
        explainability = self.load_explainability_logs()
        return {
            "rules": rules,
            "cases": cases,
            "historical": historical,
            "mappings": mappings,
            "expected": expected,
            "explainability": explainability,
        }
