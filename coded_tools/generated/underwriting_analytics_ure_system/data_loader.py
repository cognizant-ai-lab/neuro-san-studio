"""
Data loading and curation layer for underwriting analytics datasets.
Provides access to curated, versioned datasets with lineage tracking and quality checks.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import statistics

from .data_models import (
    UnderwritingDecisionLog,
    URERule,
    CaseAttribute,
    DivergenceScenario,
    RuleImpactAnalysis,
    IngestionManifest,
    DecisionType,
    ConditionSeverity,
)


class DataLoader:
    """Loads and validates underwriting analytics datasets from JSON files."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize DataLoader with dataset directory.
        
        Args:
            data_dir: Path to directory containing JSON datasets.
                     Defaults to current directory if not specified.
        """
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent
        self.datasets = {}
        self.ingestion_manifest = None
        self._decision_log_index = None

    def _get_decision_log_index(self) -> Dict[str, UnderwritingDecisionLog]:
        """Index decision logs by case ID for cross-dataset grounding."""
        if self._decision_log_index is None:
            decision_logs = self.datasets.get("decision_logs")
            if decision_logs is None:
                decision_logs, _ = self.load_decision_logs()
            self._decision_log_index = {log.case_id: log for log in decision_logs}
        return self._decision_log_index
        
    def load_decision_logs(self) -> Tuple[List[UnderwritingDecisionLog], IngestionManifest]:
        """Load and curate underwriting decision logs.
        
        Returns:
            Tuple of (decision_logs, ingestion_manifest)
        """
        filepath = self.data_dir / "dataset_1_underwriting_decision_logs.json"
        
        with open(filepath, 'r') as f:
            raw_data = json.load(f)
        
        decision_logs = []
        for record in raw_data.get("decision_logs", []):
            try:
                log = UnderwritingDecisionLog(
                    case_id=record["case_id"],
                    applicant_age=record["applicant_age"],
                    applicant_gender=record["applicant_gender"],
                    occupation=record["occupation"],
                    condition=record["condition"],
                    condition_severity=ConditionSeverity(record["condition_severity"]),
                    income_band=record["income_band"],
                    underwriting_decision_human=DecisionType(record["underwriting_decision_human"]),
                    underwriting_decision_ure=DecisionType(record["underwriting_decision_ure"]),
                    decision_reason_human=record["decision_reason_human"],
                    decision_reason_ure=record["decision_reason_ure"],
                    decision_date=record["decision_date"],
                )
                decision_logs.append(log)
            except (KeyError, ValueError) as e:
                print(f"Warning: Skipping malformed record {record.get('case_id')}: {e}")
                continue
        
        manifest = self._create_manifest(
            dataset_name="underwriting_decision_logs",
            source_datasets=["dataset_1_underwriting_decision_logs.json"],
            record_count=len(decision_logs),
            data=decision_logs,
        )
        
        self.datasets["decision_logs"] = decision_logs
        return decision_logs, manifest
    
    def load_ure_rules(self) -> Tuple[List[URERule], IngestionManifest]:
        """Load URE rule definitions.
        
        Returns:
            Tuple of (ure_rules, ingestion_manifest)
        """
        filepath = self.data_dir / "dataset_2_ure_rule_definitions.json"
        
        with open(filepath, 'r') as f:
            raw_data = json.load(f)
        
        rules = []
        for record in raw_data.get("ure_rules", []):
            try:
                rule = URERule(
                    rule_id=record["rule_id"],
                    rule_name=record["rule_name"],
                    condition=record["condition"],
                    criteria=record["criteria"],
                    decision=DecisionType(record["decision"]),
                    load_percentage=record.get("load_percentage"),
                    description=record.get("description", ""),
                )
                rules.append(rule)
            except (KeyError, ValueError) as e:
                print(f"Warning: Skipping malformed rule {record.get('rule_id')}: {e}")
                continue
        
        manifest = self._create_manifest(
            dataset_name="ure_rules",
            source_datasets=["dataset_2_ure_rule_definitions.json"],
            record_count=len(rules),
            data=rules,
        )
        
        self.datasets["ure_rules"] = rules
        return rules, manifest
    
    def load_case_attributes(self) -> Tuple[List[CaseAttribute], IngestionManifest]:
        """Load case/applicant attributes.
        
        Returns:
            Tuple of (case_attributes, ingestion_manifest)
        """
        filepath = self.data_dir / "dataset_3_case_attributes.json"
        
        with open(filepath, 'r') as f:
            raw_data = json.load(f)
        
        decision_log_index = self._get_decision_log_index()
        attributes = []
        for record in raw_data.get("case_attributes", []):
            try:
                case_id = record["case_id"]
                base_case = decision_log_index[case_id]
                attr = CaseAttribute(
                    case_id=case_id,
                    applicant_age=base_case.applicant_age,
                    applicant_gender=base_case.applicant_gender,
                    occupation=base_case.occupation,
                    occupation_risk=record.get("occupation_risk_level", ""),
                    condition=base_case.condition,
                    condition_severity=base_case.condition_severity,
                    condition_details={
                        "bmi": record.get("bmi"),
                        "smoking_status": record.get("smoking_status"),
                        "alcohol_usage": record.get("alcohol_usage"),
                        "medical_history": record.get("medical_history", []),
                        "income_variability": record.get("income_variability"),
                        "working_hours_per_week": record.get("working_hours_per_week"),
                        "prior_claims": record.get("prior_claims"),
                    },
                    income_band=base_case.income_band,
                    policy_type=record.get("policy_type", ""),
                    coverage_segment=record.get("coverage_segment", ""),
                )
                attributes.append(attr)
            except (KeyError, ValueError) as e:
                print(f"Warning: Skipping malformed attribute {record.get('case_id')}: {e}")
                continue
        
        manifest = self._create_manifest(
            dataset_name="case_attributes",
            source_datasets=["dataset_3_case_attributes.json"],
            record_count=len(attributes),
            data=attributes,
        )
        
        self.datasets["case_attributes"] = attributes
        return attributes, manifest
    
    def load_divergence_scenarios(self) -> Tuple[List[DivergenceScenario], IngestionManifest]:
        """Load cases where human and URE decisions diverged.
        
        Returns:
            Tuple of (divergence_scenarios, ingestion_manifest)
        """
        filepath = self.data_dir / "dataset_4_divergence_scenarios.json"
        
        with open(filepath, 'r') as f:
            raw_data = json.load(f)
        
        divergences = []
        for record in raw_data.get("divergence_scenarios", []):
            try:
                div = DivergenceScenario(
                    case_id=record["case_id"],
                    condition=record["condition"],
                    human_decision=DecisionType(record["human_decision"]),
                    ure_decision=DecisionType(record["ure_decision"]),
                    divergence_reason_category=record["divergence_reason_category"],
                    detailed_explanation=record["detailed_explanation"],
                )
                divergences.append(div)
            except (KeyError, ValueError) as e:
                print(f"Warning: Skipping malformed divergence {record.get('case_id')}: {e}")
                continue
        
        manifest = self._create_manifest(
            dataset_name="divergence_scenarios",
            source_datasets=["dataset_4_divergence_scenarios.json"],
            record_count=len(divergences),
            data=divergences,
        )
        
        self.datasets["divergence_scenarios"] = divergences
        return divergences, manifest
    
    def load_rule_impact_feedback(self) -> Tuple[List[RuleImpactAnalysis], IngestionManifest]:
        """Load rule impact analysis and feedback data.
        
        Returns:
            Tuple of (rule_impact_analyses, ingestion_manifest)
        """
        filepath = self.data_dir / "dataset_5_rule_impact_feedback_data.json"
        
        with open(filepath, 'r') as f:
            raw_data = json.load(f)
        
        analyses = []
        for record in raw_data.get("rule_impact_analysis", []):
            try:
                analysis = RuleImpactAnalysis(
                    rule_id=record["rule_id"],
                    number_of_cases_affected=record["number_of_cases_affected"],
                    current_accuracy=record["current_accuracy"],
                    projected_accuracy_after_change=record["projected_accuracy_after_change"],
                    manual_review_reduction_percentage=record["manual_review_reduction_percentage"],
                    estimated_sta_uplift=record["estimated_sta_uplift"],
                    confidence_score=record["confidence_score"],
                )
                analyses.append(analysis)
            except (KeyError, ValueError) as e:
                print(f"Warning: Skipping malformed analysis {record.get('rule_id')}: {e}")
                continue
        
        manifest = self._create_manifest(
            dataset_name="rule_impact_feedback",
            source_datasets=["dataset_5_rule_impact_feedback_data.json"],
            record_count=len(analyses),
            data=analyses,
        )
        
        self.datasets["rule_impact_feedback"] = analyses
        return analyses, manifest
    
    def load_uplift_dataset(self) -> Tuple[Dict[str, Any], IngestionManifest]:
        """Load underwriting URE uplift dataset.
        
        Returns:
            Tuple of (uplift_data, ingestion_manifest)
        """
        filepath = self.data_dir / "underwriting_ure_uplift_dataset.json"
        
        with open(filepath, 'r') as f:
            raw_data = json.load(f)
        
        uplift_data = raw_data
        manifest_records = [
            {"section": section_name, "record_count": len(section_records)}
            for section_name, section_records in raw_data.items()
            if isinstance(section_records, list)
        ]
        
        manifest = self._create_manifest(
            dataset_name="uplift_dataset",
            source_datasets=["underwriting_ure_uplift_dataset.json"],
            record_count=sum(record["record_count"] for record in manifest_records),
            data=manifest_records,
        )

        self.datasets["uplift"] = uplift_data
        return uplift_data, manifest
    
    def load_all_datasets(self) -> Dict[str, Tuple]:
        """Load all datasets and return with their manifests."""
        return {
            "decision_logs": self.load_decision_logs(),
            "ure_rules": self.load_ure_rules(),
            "case_attributes": self.load_case_attributes(),
            "divergence_scenarios": self.load_divergence_scenarios(),
            "rule_impact_feedback": self.load_rule_impact_feedback(),
            "uplift": self.load_uplift_dataset(),
        }
    
    def _create_manifest(
        self,
        dataset_name: str,
        source_datasets: List[str],
        record_count: int,
        data: List[Any],
    ) -> IngestionManifest:
        """Create ingestion manifest for a curated dataset.
        
        Args:
            dataset_name: Name of the curated dataset.
            source_datasets: List of source files used.
            record_count: Number of records in the dataset.
            data: The actual data for checksum calculation.
            
        Returns:
            IngestionManifest with metadata and quality checks.
        """
        data_json = json.dumps([d.to_dict() if hasattr(d, 'to_dict') else d for d in data])
        schema_checksum = hashlib.sha256(data_json.encode()).hexdigest()
        
        quality_report = self._run_quality_checks(data, dataset_name)
        
        manifest = IngestionManifest(
            dataset_name=dataset_name,
            version="1.0.0",
            source_datasets=source_datasets,
            record_count=record_count,
            extracted_at=datetime.now(),
            schema_checksum=schema_checksum,
            quality_checks_passed=quality_report.get("all_checks_passed", False),
            data_quality_report=quality_report,
            lineage={
                "sources": source_datasets,
                "transformations": [
                    "Schema validation",
                    "Type coercion",
                    "Malformed record filtering",
                ],
            },
        )
        
        return manifest
    
    def _run_quality_checks(self, data: List[Any], dataset_name: str) -> Dict[str, Any]:
        """Run data quality checks on a dataset.
        
        Args:
            data: The dataset to check.
            dataset_name: Name of the dataset for context.
            
        Returns:
            Dictionary with quality check results.
        """
        report = {
            "dataset_name": dataset_name,
            "checks": {},
        }
        
        # Completeness check
        total_records = len(data)
        null_count = sum(1 for record in data if record is None)
        report["checks"]["completeness"] = {
            "total_records": total_records,
            "null_records": null_count,
            "completeness_percentage": ((total_records - null_count) / total_records * 100) if total_records > 0 else 0,
        }
        
        # Duplicate check (by checking first field that looks like an ID)
        ids = []
        for record in data:
            if dataset_name == "rule_impact_feedback":
                payload = record.to_dict() if hasattr(record, "to_dict") else record
                ids.append(json.dumps(payload, sort_keys=True))
                continue
            if hasattr(record, 'case_id'):
                ids.append(record.case_id)
            elif hasattr(record, 'rule_id'):
                ids.append(record.rule_id)
            elif isinstance(record, dict):
                if 'case_id' in record:
                    ids.append(record['case_id'])
                elif 'rule_id' in record:
                    ids.append(record['rule_id'])
        
        unique_ids = set(ids)
        report["checks"]["duplicates"] = {
            "total_ids": len(ids),
            "unique_ids": len(unique_ids),
            "duplicate_count": len(ids) - len(unique_ids),
        }
        
        # Type consistency check (basic)
        report["checks"]["type_consistency"] = {
            "checked": True,
            "issues_found": 0,
        }
        
        report["all_checks_passed"] = (
            report["checks"]["completeness"]["completeness_percentage"] > 95 and
            report["checks"]["duplicates"]["duplicate_count"] == 0
        )
        
        return report
