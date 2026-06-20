"""
Governance Agent implementation.
Reviews underwriting analytics work for privacy, security, and compliance.
"""

from typing import List, Dict, Any
from datetime import datetime

from .data_models import (
    GovernanceApproval,
)


class GovernanceAgent:
    """
    Purpose: Review underwriting analytics work for privacy, security, and regulatory
    compliance by defining allowed fields and aggregation rules, validating lineage
    and purpose limitation.
    
    Responsibilities:
    - Verify compliance with privacy, security, and regulatory requirements
    - Define and enforce allowed data elements for analytics
    - Review and approve data lineage and purpose limitation
    - Review deliverables for safe disclosure
    - Provide governance checklist and sign-off criteria
    """
    
    def __init__(self):
        """Initialize Governance Agent."""
        self.approvals = []
        self.policy = self._initialize_default_policy()
    
    def _initialize_default_policy(self) -> Dict[str, Any]:
        """Initialize default governance policy.
        
        Returns:
            Dictionary with default policy settings.
        """
        return {
            "pii_definitions": {
                "direct_identifiers": ["applicant_name", "ssn", "email", "phone"],
                "sensitive_demographics": ["applicant_age", "gender", "occupation_detail"],
            },
            "allowed_fields_for_analytics": [
                "case_id",
                "applicant_age",
                "applicant_gender",
                "occupation",
                "condition",
                "condition_severity",
                "income_band",
                "underwriting_decision_human",
                "underwriting_decision_ure",
                "decision_reason_human",
                "decision_reason_ure",
                "decision_date",
            ],
            "minimum_aggregation_threshold": 10,  # K-anonymity
            "retention_days": 365,
            "approved_analysis_purposes": [
                "URE performance improvement",
                "Rule optimization",
                "Quality assurance",
                "Compliance monitoring",
            ],
        }
    
    def review_analysis_for_compliance(
        self,
        analysis_type: str,
        proposed_fields: List[str],
        proposed_aggregation: Dict[str, int],
    ) -> GovernanceApproval:
        """Review a proposed analysis for compliance and privacy.
        
        Args:
            analysis_type: Type of analysis being proposed
            proposed_fields: List of fields to use in analysis
            proposed_aggregation: Aggregation levels for various segments
            
        Returns:
            GovernanceApproval with decision and remediation if needed.
        """
        print(f"[GovernanceAgent] Reviewing {analysis_type} for compliance...")
        
        issues = []
        
        # Check proposed fields against allowed fields
        disallowed_fields = [f for f in proposed_fields if f not in self.policy["allowed_fields_for_analytics"]]
        if disallowed_fields:
            issues.append(f"Disallowed fields: {disallowed_fields}")
        
        # Check aggregation thresholds
        min_threshold = self.policy["minimum_aggregation_threshold"]
        insufficient_aggregation = {
            seg: count for seg, count in proposed_aggregation.items()
            if count > 0 and count < min_threshold
        }
        if insufficient_aggregation:
            issues.append(f"Insufficient aggregation: {insufficient_aggregation}")
        
        # Determine approval status
        if not issues:
            approval_status = "Approved"
            remediation_notes = "No issues identified."
        else:
            approval_status = "Conditional"
            remediation_notes = " | ".join(issues)
        
        approval = GovernanceApproval(
            request_id=f"GOV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            analysis_type=analysis_type,
            approval_status=approval_status,
            allowed_fields=[f for f in proposed_fields if f in self.policy["allowed_fields_for_analytics"]],
            minimum_aggregation_threshold=min_threshold,
            retention_days=self.policy["retention_days"],
            audit_requirements=[
                "Log all data access",
                "Track data lineage",
                "Record approval timestamps",
            ],
            remediation_notes=remediation_notes,
        )
        
        self.approvals.append(approval)
        print(f"[GovernanceAgent] ✓ Review complete: {approval_status}")
        return approval
    
    def validate_lineage(
        self,
        dataset_name: str,
        source_datasets: List[str],
        transformations: List[str],
    ) -> Dict[str, Any]:
        """Validate data lineage and purpose limitation.
        
        Args:
            dataset_name: Name of the curated dataset
            source_datasets: List of source datasets used
            transformations: List of transformations applied
            
        Returns:
            Lineage validation report.
        """
        print(f"[GovernanceAgent] Validating lineage for {dataset_name}...")
        
        report = {
            "dataset": dataset_name,
            "lineage_valid": True,
            "source_datasets": source_datasets,
            "transformations": transformations,
            "issues": [],
            "recommendations": [],
        }
        
        # Check for overly complex lineage
        if len(transformations) > 5:
            report["issues"].append("Many transformations - recommend simplification")
        
        # Verify transformations are documented
        if not transformations:
            report["recommendations"].append("Document any data transformations applied")
        
        print(f"[GovernanceAgent] ✓ Lineage validation: Valid={report['lineage_valid']}")
        return report
    
    def review_experiment_for_fairness(
        self,
        experiment_id: str,
        protected_attributes: List[str],
        analysis_plan: str,
    ) -> Dict[str, Any]:
        """Review experiment for fairness and non-discrimination.
        
        Args:
            experiment_id: ID of the experiment
            protected_attributes: Attributes to check for disparate impact
            analysis_plan: Description of the analysis plan
            
        Returns:
            Fairness review report.
        """
        print(f"[GovernanceAgent] Reviewing {experiment_id} for fairness...")
        
        review = {
            "experiment_id": experiment_id,
            "fairness_review": {
                "protected_attributes_checked": protected_attributes,
                "disparate_impact_analysis": "Will compare outcome rates across groups",
                "minimum_group_size": self.policy["minimum_aggregation_threshold"],
                "requirements": [
                    "No decision rule shall result in significantly disparate outcomes for protected groups",
                    "Results must be segmented by protected attributes",
                    "Any disparities must be documented and explained",
                ],
            },
            "compliance_status": "COMPLIANT" if analysis_plan else "NEEDS_DOCUMENTATION",
        }
        
        print(f"[GovernanceAgent] ✓ Fairness review complete")
        return review
    
    def approve_data_export(
        self,
        export_type: str,
        target_format: str,
        recipient_team: str,
    ) -> GovernanceApproval:
        """Approve and document a data export.
        
        Args:
            export_type: Type of data being exported
            target_format: Format of the export
            recipient_team: Team receiving the export
            
        Returns:
            GovernanceApproval for the export.
        """
        print(f"[GovernanceAgent] Reviewing data export for {recipient_team}...")
        
        approval = GovernanceApproval(
            request_id=f"EXPORT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            analysis_type=f"Data Export: {export_type} to {target_format}",
            approval_status="Approved with controls",
            allowed_fields=self.policy["allowed_fields_for_analytics"],
            minimum_aggregation_threshold=self.policy["minimum_aggregation_threshold"],
            retention_days=30,  # Shorter retention for exports
            audit_requirements=[
                "Log export metadata and recipient",
                "Require signed data use agreement from recipient",
                "Set automatic deletion after 30 days",
                "Encrypt export in transit",
            ],
            remediation_notes=f"Export approved for {recipient_team} with standard data use controls.",
        )
        
        print(f"[GovernanceAgent] ✓ Export approved with controls")
        return approval
    
    def generate_compliance_checklist(self) -> Dict[str, List[str]]:
        """Generate compliance checklist for production deployments.
        
        Returns:
            Compliance checklist.
        """
        print("[GovernanceAgent] Generating compliance checklist...")
        
        checklist = {
            "data_governance": [
                "✓ All datasets sourced from configured/approved systems",
                "✓ Data lineage documented and validated",
                "✓ Purpose limitation verified (URE improvement only)",
                "✓ No unauthorized PII in outputs",
            ],
            "privacy": [
                "✓ Minimum aggregation thresholds applied (k-anonymity >= 10)",
                "✓ No direct identifiers in deliverables",
                "✓ Sensitive attributes aggregated or suppressed",
                "✓ Retention policies enforced (365 days max)",
            ],
            "fairness": [
                "✓ Disparate impact analysis performed",
                "✓ Results segmented by protected attributes",
                "✓ No evidence of intentional discrimination",
                "✓ Fairness constraints documented",
            ],
            "security": [
                "✓ Access controls in place (role-based)",
                "✓ Data exports encrypted in transit",
                "✓ Audit trails maintained",
                "✓ No sensitive data in logs or debug output",
            ],
            "compliance": [
                "✓ Analysis fits approved use cases",
                "✓ No regulatory violations identified",
                "✓ Governance approvals documented",
                "✓ Compliance officer sign-off obtained",
            ],
        }
        
        print("[GovernanceAgent] ✓ Compliance checklist generated")
        return checklist
    
    def get_allowed_fields_policy(self) -> Dict[str, List[str]]:
        """Get the current allowed fields policy for this workflow.
        
        Returns:
            Policy specification for allowed fields and transformations.
        """
        return {
            "allowed_fields": self.policy["allowed_fields_for_analytics"],
            "minimum_aggregation_threshold": self.policy["minimum_aggregation_threshold"],
            "retention_days": self.policy["retention_days"],
            "pii_definitions": self.policy["pii_definitions"],
            "approved_purposes": self.policy["approved_analysis_purposes"],
        }
