from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from .condition_matcher_agent import ConditionMatcherAgent
from .data_loader import DataLoader
from .decision_engine_agent import DecisionEngineAgent
from .explanation_generator_agent import ExplanationGeneratorAgent
from .uw_manual_reader_agent import UWManualReaderAgent


class UWPipelineOrchestrator:
    def __init__(self) -> None:
        self.data_loader = DataLoader()
        self.manual_reader = UWManualReaderAgent()
        self.matcher = ConditionMatcherAgent()
        self.decision_engine = DecisionEngineAgent()
        self.explainer = ExplanationGeneratorAgent()
        self.execution_log: List[Dict[str, object]] = []
        self.last_successful_phase: Optional[str] = None
        self.first_failed_phase: Optional[str] = None

    def _mark(self, phase: str, status: str, details: Optional[Dict[str, object]] = None) -> None:
        entry: Dict[str, object] = {
            "phase": phase,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }
        if details:
            entry["details"] = details
        self.execution_log.append(entry)
        if status == "completed":
            self.last_successful_phase = phase
        elif status == "failed" and self.first_failed_phase is None:
            self.first_failed_phase = phase

    def _load_indices(self) -> Dict[str, Dict[str, object]]:
        datasets = self.data_loader.load_all()
        return {
            "datasets": datasets,
            "rule_index": {item.rule_id: item for item in datasets["rules"]},
            "case_index": {item.case_id: item for item in datasets["cases"]},
            "mapping_index": {item.case_id: item for item in datasets["mappings"]},
            "expected_index": {item.case_id: item for item in datasets["expected"]},
            "historical_index": {item.case_id: item for item in datasets["historical"]},
            "explainability_index": {item.case_id: item for item in datasets["explainability"]},
        }

    def summarize_grounding(self) -> Dict[str, object]:
        self._mark("Dataset Grounding", "started")
        indices = self._load_indices()
        datasets = indices["datasets"]
        rules = datasets["rules"]
        cases = datasets["cases"]
        summary = {
            "rules": len(rules),
            "cases": len(cases),
            "historical_decisions": len(datasets["historical"]),
            "rule_mappings": len(datasets["mappings"]),
            "expected_decisions": len(datasets["expected"]),
            "explainability_logs": len(datasets["explainability"]),
            "conditions": sorted({rule.condition for rule in rules}),
        }
        self._mark("Dataset Grounding", "completed", summary)
        return summary

    def extract_manual_rules(self) -> Dict[str, object]:
        self._mark("Manual Rule Extraction", "started")
        rules = self.data_loader.load_rules()
        result = self.manual_reader.extract_structured_rules(rules)
        self._mark("Manual Rule Extraction", "completed", {"rules_extracted": len(result["rules"])})
        return result

    def match_case_rules(self, case_id: str) -> Dict[str, object]:
        self._mark("Case Rule Matching", "started", {"case_id": case_id})
        indices = self._load_indices()
        result = self.matcher.match_case(
            case=indices["case_index"][case_id],
            mapping=indices["mapping_index"][case_id],
            rule_index=indices["rule_index"],
        )
        self._mark("Case Rule Matching", "completed", {"case_id": case_id, "matched_rules": len(result["matched_rules"])})
        return result

    def run_pipeline(self, case_id: str) -> Dict[str, object]:
        self._mark("End To End Decision", "started", {"case_id": case_id})
        indices = self._load_indices()
        case_match = self.matcher.match_case(
            case=indices["case_index"][case_id],
            mapping=indices["mapping_index"][case_id],
            rule_index=indices["rule_index"],
        )
        decision = self.decision_engine.compute_decision(
            case_id=case_id,
            matched_rule_ids=[item["rule_id"] for item in case_match["matched_rules"]],
            rule_index=indices["rule_index"],
            expected=indices["expected_index"][case_id],
            historical=indices["historical_index"].get(case_id),
        )
        result = self.explainer.build_audit_output(decision, indices["explainability_index"][case_id])
        self._mark(
            "End To End Decision",
            "completed",
            {
                "case_id": case_id,
                "final_decision": result["final_decision"],
                "matches_expected": decision["decision_matches_expected"],
            },
        )
        return result

    def validate_workflow_steps(self) -> Dict[str, object]:
        validations: List[Dict[str, object]] = []
        stop_after_step = None

        try:
            summary = self.summarize_grounding()
            validations.append(
                {
                    "step": "dataset_grounding_summary",
                    "status": "passed" if summary["cases"] == 200 and summary["rules"] == 44 else "failed",
                    "issues": [] if summary["cases"] == 200 and summary["rules"] == 44 else [summary],
                }
            )
            if validations[-1]["status"] != "passed":
                stop_after_step = "dataset_grounding_summary"
                raise ValueError("Grounding counts did not match packaged datasets")

            extracted = self.extract_manual_rules()
            validations.append(
                {
                    "step": "manual_rule_extraction",
                    "status": "passed" if len(extracted["rules"]) == 44 else "failed",
                    "issues": [] if len(extracted["rules"]) == 44 else ["rule extraction count mismatch"],
                }
            )
            if validations[-1]["status"] != "passed":
                stop_after_step = "manual_rule_extraction"
                raise ValueError("Manual extraction did not produce all rules")

            matched = self.match_case_rules("CASE-0001")
            validations.append(
                {
                    "step": "case_rule_matching",
                    "status": "passed" if [rule["rule_id"] for rule in matched["matched_rules"]] == ["R-HD-005"] else "failed",
                    "issues": [] if [rule["rule_id"] for rule in matched["matched_rules"]] == ["R-HD-005"] else [matched],
                }
            )
            if validations[-1]["status"] != "passed":
                stop_after_step = "case_rule_matching"
                raise ValueError("Case rule matching failed for CASE-0001")

            pipeline = self.run_pipeline("CASE-0001")
            validations.append(
                {
                    "step": "end_to_end_decision",
                    "status": "passed" if pipeline["final_decision"] == "Accept" else "failed",
                    "issues": [] if pipeline["final_decision"] == "Accept" else [pipeline],
                }
            )
            if validations[-1]["status"] != "passed":
                stop_after_step = "end_to_end_decision"
                raise ValueError("Final decision did not match packaged expectation")
        except Exception as error:
            if stop_after_step is None and validations:
                stop_after_step = validations[-1]["step"]
            elif stop_after_step is None:
                stop_after_step = "dataset_grounding_summary"
            self._mark(stop_after_step, "failed", {"error": str(error)})

        return {
            "validations": validations,
            "stop_after_step": stop_after_step,
            "network_running": stop_after_step is None,
            "execution_trace": {
                "execution_log": self.execution_log,
                "last_successful_phase": self.last_successful_phase,
                "first_failed_phase": self.first_failed_phase,
                "network_running": stop_after_step is None,
            },
        }
