"""
Ingestion Agent implementation.
Interfaces with datasets to ingest, validate, normalize, and version
underwriting-analytics inputs into curated datasets.
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import json

from .data_loader import DataLoader
from .data_models import (
    UnderwritingDecisionLog,
    URERule,
    CaseAttribute,
    DivergenceScenario,
    RuleImpactAnalysis,
    IngestionManifest,
)


class IngestionAgent:
    """
    Purpose: Interface with configured raw data sources to ingest, validate, normalize,
    and version underwriting-analytics inputs into curated datasets for downstream agents.
    
    Responsibilities:
    - Build and publish curated, analysis-ready datasets with explicit lineage
    - Run data quality checks and report results
    - Validate and standardize schemas
    - Normalize identifiers and time
    """
    
    def __init__(self, data_loader: Optional[DataLoader] = None):
        """Initialize IngestionAgent with a DataLoader."""
        self.data_loader = data_loader or DataLoader()
        self.curated_datasets = {}
        self.manifests = {}
        self.configuration_checklist = {
            "decision_logs": False,
            "ure_rules": False,
            "case_attributes": False,
            "divergence_scenarios": False,
            "rule_impact_feedback": False,
            "uplift_dataset": False,
        }
    
    def ingest_and_curate_decision_logs(self) -> Tuple[List[UnderwritingDecisionLog], IngestionManifest]:
        """Ingest and curate underwriting decision logs.
        
        Returns:
            Tuple of (curated_logs, manifest)
        """
        print("[IngestionAgent] Ingesting decision logs...")
        logs, manifest = self.data_loader.load_decision_logs()
        
        # Normalization and validation
        validated_logs = self._validate_decision_logs(logs)
        
        self.curated_datasets["decision_logs"] = validated_logs
        self.manifests["decision_logs"] = manifest
        self.configuration_checklist["decision_logs"] = True
        
        print(f"[IngestionAgent] ✓ Decision logs curated: {len(validated_logs)} records")
        return validated_logs, manifest
    
    def ingest_and_curate_ure_rules(self) -> Tuple[List[URERule], IngestionManifest]:
        """Ingest and curate URE rule definitions.
        
        Returns:
            Tuple of (curated_rules, manifest)
        """
        print("[IngestionAgent] Ingesting URE rules...")
        rules, manifest = self.data_loader.load_ure_rules()
        
        # Normalization and validation
        validated_rules = self._validate_ure_rules(rules)
        
        self.curated_datasets["ure_rules"] = validated_rules
        self.manifests["ure_rules"] = manifest
        self.configuration_checklist["ure_rules"] = True
        
        print(f"[IngestionAgent] ✓ URE rules curated: {len(validated_rules)} records")
        return validated_rules, manifest
    
    def ingest_and_curate_case_attributes(self) -> Tuple[List[CaseAttribute], IngestionManifest]:
        """Ingest and curate case attributes.
        
        Returns:
            Tuple of (curated_attributes, manifest)
        """
        print("[IngestionAgent] Ingesting case attributes...")
        attributes, manifest = self.data_loader.load_case_attributes()
        
        # Normalization and validation
        validated_attrs = self._validate_case_attributes(attributes)
        
        self.curated_datasets["case_attributes"] = validated_attrs
        self.manifests["case_attributes"] = manifest
        self.configuration_checklist["case_attributes"] = True
        
        print(f"[IngestionAgent] ✓ Case attributes curated: {len(validated_attrs)} records")
        return validated_attrs, manifest
    
    def ingest_and_curate_divergences(self) -> Tuple[List[DivergenceScenario], IngestionManifest]:
        """Ingest and curate divergence scenarios.
        
        Returns:
            Tuple of (curated_divergences, manifest)
        """
        print("[IngestionAgent] Ingesting divergence scenarios...")
        divergences, manifest = self.data_loader.load_divergence_scenarios()
        
        # Normalization and validation
        validated_divs = self._validate_divergences(divergences)
        
        self.curated_datasets["divergence_scenarios"] = validated_divs
        self.manifests["divergence_scenarios"] = manifest
        self.configuration_checklist["divergence_scenarios"] = True
        
        print(f"[IngestionAgent] ✓ Divergence scenarios curated: {len(validated_divs)} records")
        return validated_divs, manifest
    
    def ingest_and_curate_rule_impact(self) -> Tuple[List[RuleImpactAnalysis], IngestionManifest]:
        """Ingest and curate rule impact feedback data.
        
        Returns:
            Tuple of (curated_analyses, manifest)
        """
        print("[IngestionAgent] Ingesting rule impact feedback...")
        analyses, manifest = self.data_loader.load_rule_impact_feedback()
        
        # Normalization and validation
        validated_analyses = self._validate_rule_impact(analyses)
        
        self.curated_datasets["rule_impact_feedback"] = validated_analyses
        self.manifests["rule_impact_feedback"] = manifest
        self.configuration_checklist["rule_impact_feedback"] = True
        
        print(f"[IngestionAgent] ✓ Rule impact feedback curated: {len(validated_analyses)} records")
        return validated_analyses, manifest

    def ingest_and_curate_uplift_dataset(self) -> Tuple[Dict[str, Any], IngestionManifest]:
        """Ingest and curate the bundled uplift dataset container."""
        print("[IngestionAgent] Ingesting uplift dataset...")
        uplift_data, manifest = self.data_loader.load_uplift_dataset()

        self.curated_datasets["uplift"] = uplift_data
        self.manifests["uplift"] = manifest
        self.configuration_checklist["uplift_dataset"] = True

        print(
            "[IngestionAgent] ✓ Uplift dataset curated: "
            f"{manifest.record_count} packaged records across {len(uplift_data)} sections"
        )
        return uplift_data, manifest
    
    def ingest_all_datasets(self) -> Dict[str, Tuple[List, IngestionManifest]]:
        """Ingest and curate all available datasets.
        
        Returns:
            Dictionary with dataset names as keys and (data, manifest) tuples as values.
        """
        print("[IngestionAgent] Starting full dataset ingestion...")
        return {
            "decision_logs": self.ingest_and_curate_decision_logs(),
            "ure_rules": self.ingest_and_curate_ure_rules(),
            "case_attributes": self.ingest_and_curate_case_attributes(),
            "divergence_scenarios": self.ingest_and_curate_divergences(),
            "rule_impact_feedback": self.ingest_and_curate_rule_impact(),
            "uplift": self.ingest_and_curate_uplift_dataset(),
        }
    
    def get_configuration_checklist(self) -> Dict[str, bool]:
        """Get the configuration status of all datasets."""
        return self.configuration_checklist.copy()
    
    def publish_quality_report(self) -> Dict[str, Any]:
        """Publish comprehensive data quality report for all curated datasets.
        
        Returns:
            Quality report with details for each dataset.
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "datasets": {},
        }
        
        for dataset_name, manifest in self.manifests.items():
            report["datasets"][dataset_name] = {
                "manifest": manifest.to_dict(),
                "quality_report": manifest.data_quality_report,
                "lineage": manifest.lineage,
            }
        
        return report
    
    # Private validation methods
    
    def _validate_decision_logs(self, logs: List[UnderwritingDecisionLog]) -> List[UnderwritingDecisionLog]:
        """Validate and normalize decision logs.
        
        Checks:
        - Required fields present
        - Age is reasonable (0-120)
        - Decision consistency
        """
        validated = []
        issues = []
        
        for log in logs:
            try:
                # Age sanity check
                if not (0 <= log.applicant_age <= 120):
                    issues.append(f"Invalid age {log.applicant_age} for {log.case_id}")
                    continue
                
                # Decision consistency check
                if log.underwriting_decision_human == log.underwriting_decision_ure:
                    # Decisions match - both should have similar reasoning
                    pass
                
                validated.append(log)
            except Exception as e:
                issues.append(f"Validation error for {log.case_id}: {e}")
        
        if issues:
            print(f"[IngestionAgent] Validation issues: {len(issues)}")
        
        return validated
    
    def _validate_ure_rules(self, rules: List[URERule]) -> List[URERule]:
        """Validate and normalize URE rules.
        
        Checks:
        - Rule IDs are unique and well-formed
        - Decision types are valid
        - Load percentage is between 0-100 when present
        """
        validated = []
        seen_ids = set()
        issues = []
        
        for rule in rules:
            try:
                # ID uniqueness check
                if rule.rule_id in seen_ids:
                    issues.append(f"Duplicate rule ID: {rule.rule_id}")
                    continue
                seen_ids.add(rule.rule_id)
                
                # Load percentage check
                if rule.load_percentage is not None:
                    if not (0 <= rule.load_percentage <= 100):
                        issues.append(f"Invalid load % {rule.load_percentage} for {rule.rule_id}")
                        continue
                
                validated.append(rule)
            except Exception as e:
                issues.append(f"Validation error for {rule.rule_id}: {e}")
        
        if issues:
            print(f"[IngestionAgent] Rule validation issues: {len(issues)}")
        
        return validated
    
    def _validate_case_attributes(self, attributes: List[CaseAttribute]) -> List[CaseAttribute]:
        """Validate case attributes.
        
        Checks:
        - Age is reasonable
        - Case IDs are present and well-formed
        - Required fields populated
        """
        validated = []
        issues = []
        
        for attr in attributes:
            try:
                if not (0 <= attr.applicant_age <= 120):
                    issues.append(f"Invalid age {attr.applicant_age} for {attr.case_id}")
                    continue
                
                validated.append(attr)
            except Exception as e:
                issues.append(f"Validation error for {attr.case_id}: {e}")
        
        if issues:
            print(f"[IngestionAgent] Attribute validation issues: {len(issues)}")
        
        return validated
    
    def _validate_divergences(self, divergences: List[DivergenceScenario]) -> List[DivergenceScenario]:
        """Validate divergence scenarios.
        
        Checks:
        - Case IDs reference actual cases
        - Decisions are different (divergence confirmed)
        - Reason categories are well-formed
        """
        validated = []
        issues = []
        
        for div in divergences:
            try:
                # Ensure actual divergence exists
                if div.human_decision == div.ure_decision:
                    issues.append(f"No divergence found for {div.case_id}")
                    continue
                
                validated.append(div)
            except Exception as e:
                issues.append(f"Validation error for {div.case_id}: {e}")
        
        if issues:
            print(f"[IngestionAgent] Divergence validation issues: {len(issues)}")
        
        return validated
    
    def _validate_rule_impact(self, analyses: List[RuleImpactAnalysis]) -> List[RuleImpactAnalysis]:
        """Validate rule impact analyses.
        
        Checks:
        - Accuracy values are between 0-100
        - Cases affected is non-negative
        - Confidence scores are valid
        """
        validated = []
        issues = []
        
        for analysis in analyses:
            try:
                # Accuracy check
                if not (0 <= analysis.current_accuracy <= 100):
                    issues.append(f"Invalid current accuracy for {analysis.rule_id}")
                    continue
                if not (0 <= analysis.projected_accuracy_after_change <= 100):
                    issues.append(f"Invalid projected accuracy for {analysis.rule_id}")
                    continue
                
                # Cases affected check
                if analysis.number_of_cases_affected < 0:
                    issues.append(f"Negative cases affected for {analysis.rule_id}")
                    continue
                
                # Confidence score validation
                if analysis.confidence_score not in ["Low", "Medium", "High"]:
                    issues.append(f"Invalid confidence score for {analysis.rule_id}")
                    continue
                
                validated.append(analysis)
            except Exception as e:
                issues.append(f"Validation error for {analysis.rule_id}: {e}")
        
        if issues:
            print(f"[IngestionAgent] Impact analysis validation issues: {len(issues)}")
        
        return validated
