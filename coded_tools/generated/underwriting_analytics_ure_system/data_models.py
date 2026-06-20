"""
Data models and schemas for underwriting analytics datasets.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DecisionType(str, Enum):
    """Underwriting decision types."""
    ACCEPT = "Accept"
    LOAD = "Load"
    REFER = "Refer"
    EXCLUSION = "Exclusion"


class ConditionSeverity(str, Enum):
    """Condition severity levels."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass
class UnderwritingDecisionLog:
    """Curated underwriting decision log record."""
    case_id: str
    applicant_age: int
    applicant_gender: str
    occupation: str
    condition: str
    condition_severity: ConditionSeverity
    income_band: str
    underwriting_decision_human: DecisionType
    underwriting_decision_ure: DecisionType
    decision_reason_human: str
    decision_reason_ure: str
    decision_date: str
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['condition_severity'] = self.condition_severity.value
        data['underwriting_decision_human'] = self.underwriting_decision_human.value
        data['underwriting_decision_ure'] = self.underwriting_decision_ure.value
        return data


@dataclass
class URERule:
    """URE Rule definition."""
    rule_id: str
    rule_name: str
    condition: str
    criteria: str
    decision: DecisionType
    load_percentage: Optional[float] = None
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['decision'] = self.decision.value
        return data


@dataclass
class CaseAttribute:
    """Case/Applicant attributes."""
    case_id: str
    applicant_age: int
    applicant_gender: str
    occupation: str
    occupation_risk: str
    condition: str
    condition_severity: ConditionSeverity
    condition_details: Dict[str, Any] = field(default_factory=dict)
    income_band: str = ""
    policy_type: str = ""
    coverage_segment: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['condition_severity'] = self.condition_severity.value
        return data


@dataclass
class DivergenceScenario:
    """Cases where human and URE decisions diverged."""
    case_id: str
    condition: str
    human_decision: DecisionType
    ure_decision: DecisionType
    divergence_reason_category: str
    detailed_explanation: str
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['human_decision'] = self.human_decision.value
        data['ure_decision'] = self.ure_decision.value
        return data


@dataclass
class RuleImpactAnalysis:
    """Rule impact feedback and analysis."""
    rule_id: str
    number_of_cases_affected: int
    current_accuracy: float
    projected_accuracy_after_change: float
    manual_review_reduction_percentage: float
    estimated_sta_uplift: float
    confidence_score: str  # "Low", "Medium", "High"
    
    @property
    def accuracy_improvement(self) -> float:
        """Calculate accuracy improvement percentage."""
        return self.projected_accuracy_after_change - self.current_accuracy
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IngestionManifest:
    """Metadata manifest for curated datasets."""
    dataset_name: str
    version: str
    source_datasets: List[str]
    record_count: int
    extracted_at: datetime
    schema_checksum: str
    quality_checks_passed: bool
    data_quality_report: Dict[str, Any] = field(default_factory=dict)
    lineage: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['extracted_at'] = self.extracted_at.isoformat()
        return data


@dataclass
class KPIResult:
    """KPI computation result."""
    kpi_name: str
    value: float
    numerator: int
    denominator: int
    segment_dimensions: Dict[str, str] = field(default_factory=dict)
    confidence_interval: Optional[tuple] = None  # (lower, upper)
    sample_size: int = 0
    calculation_method: str = ""
    data_version: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuleOptimizationCandidate:
    """Proposed rule optimization from diagnostics."""
    rule_id: str
    rule_name: str
    current_impact: float
    proposed_change: str
    expected_kpi_movement: Dict[str, float]
    risk_tradeoffs: str
    implementation_notes: str
    evidence_strength: str  # "Strong", "Moderate", "Weak"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentBrief:
    """Experiment design brief."""
    hypothesis: str
    primary_kpis: List[str]
    secondary_kpis: List[str]
    guardrails: List[Dict[str, Any]]
    target_population: str
    unit_of_randomization: str
    experiment_type: str  # "A/B", "Shadow", "Canary", "Phased"
    expected_sample_size: int
    test_duration_days: int
    rollout_schedule: str
    analysis_plan: str
    rollback_criteria: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MonitoringSpec:
    """Monitoring and alerting specification."""
    metric_name: str
    metric_definition: str
    calculation_method: str
    alert_threshold: float
    alert_direction: str  # "above", "below", "deviation"
    detection_window_hours: int
    segment_dimensions: List[str] = field(default_factory=list)
    runbook_link: str = ""
    owner_team: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GovernanceApproval:
    """Governance review approval decision."""
    request_id: str
    analysis_type: str
    approval_status: str  # "Approved", "Conditional", "Rejected"
    allowed_fields: List[str]
    minimum_aggregation_threshold: int
    retention_days: int
    audit_requirements: List[str]
    remediation_notes: str = ""
    approved_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['approved_at'] = self.approved_at.isoformat()
        return data
