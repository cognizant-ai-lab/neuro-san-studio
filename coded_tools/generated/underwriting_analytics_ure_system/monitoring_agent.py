"""
Monitoring Agent implementation.
Defines KPI, data-quality, drift, and operational monitoring plus alerting specs.
"""

from typing import List, Dict, Any

from .data_models import (
    MonitoringSpec,
    IngestionManifest,
)


class MonitoringAgent:
    """
    Purpose: Define implement-ready monitoring and alerting specifications for
    underwriting analytics and URE performance.
    
    Responsibilities:
    - Define KPI, quality, and operational monitoring requirements
    - Specify metrics precisely with thresholds
    - Design alerting and anomaly detection
    - Define data quality monitors
    - Provide dashboard specifications
    """
    
    def __init__(self):
        """Initialize Monitoring Agent."""
        self.monitoring_specs = []
    
    def create_kpi_monitors(self) -> List[MonitoringSpec]:
        """Create KPI monitoring specifications.
        
        Returns:
            List of MonitoringSpec for key KPIs.
        """
        print("[MonitoringAgent] Creating KPI monitoring specs...")
        
        kpi_specs = [
            MonitoringSpec(
                metric_name="approval_rate",
                metric_definition="Count of Accept decisions / Total decisions * 100",
                calculation_method="Daily aggregation across all decisions",
                alert_threshold=40,  # Alert if drops below 40%
                alert_direction="below",
                detection_window_hours=24,
                segment_dimensions=["condition", "income_band", "age_group"],
                owner_team="Underwriting Analytics",
            ),
            MonitoringSpec(
                metric_name="decline_rate",
                metric_definition="Count of Exclusion decisions / Total decisions * 100",
                calculation_method="Daily aggregation across all decisions",
                alert_threshold=35,  # Alert if exceeds 35%
                alert_direction="above",
                detection_window_hours=24,
                segment_dimensions=["condition", "income_band"],
                owner_team="Underwriting Analytics",
            ),
            MonitoringSpec(
                metric_name="referral_rate",
                metric_definition="Count of Refer decisions / Total decisions * 100",
                calculation_method="Daily aggregation across all decisions",
                alert_threshold=20,  # Alert if exceeds 20%
                alert_direction="above",
                detection_window_hours=24,
                segment_dimensions=["condition"],
                owner_team="Underwriting Operations",
            ),
            MonitoringSpec(
                metric_name="human_ure_alignment",
                metric_definition="Count of matching decisions / Total decisions * 100",
                calculation_method="Daily comparison of human vs URE decisions",
                alert_threshold=80,  # Alert if drops below 80%
                alert_direction="below",
                detection_window_hours=24,
                segment_dimensions=["condition"],
                owner_team="Underwriting Analytics",
            ),
        ]
        
        self.monitoring_specs.extend(kpi_specs)
        print(f"[MonitoringAgent] ✓ Created {len(kpi_specs)} KPI monitors")
        return kpi_specs
    
    def create_data_quality_monitors(
        self,
        manifests: Dict[str, IngestionManifest],
    ) -> List[Dict[str, Any]]:
        """Create data quality monitoring specifications.
        
        Args:
            manifests: Dictionary of IngestionManifests for each dataset
            
        Returns:
            List of data quality monitor specifications.
        """
        print("[MonitoringAgent] Creating data quality monitors...")
        
        dq_monitors = []
        
        for dataset_name, manifest in manifests.items():
            monitor = {
                "dataset_name": dataset_name,
                "checks": {
                    "freshness": {
                        "metric": "Time since last update",
                        "threshold_hours": 24,
                        "alert_if": "exceeds",
                    },
                    "completeness": {
                        "metric": "Non-null record percentage",
                        "threshold_percent": 95,
                        "alert_if": "drops_below",
                    },
                    "schema_drift": {
                        "metric": "Column list and types consistency",
                        "check_method": "Compare schema hash",
                        "alert_if": "changes",
                    },
                    "duplicate_rate": {
                        "metric": "Percentage of duplicate IDs",
                        "threshold_percent": 0.1,
                        "alert_if": "exceeds",
                    },
                },
                "frequency": "daily",
            }
            dq_monitors.append(monitor)
        
        print(f"[MonitoringAgent] ✓ Created {len(dq_monitors)} data quality monitors")
        return dq_monitors
    
    def create_rule_drift_monitors(self) -> List[Dict[str, Any]]:
        """Create rule drift and stability monitoring specifications.
        
        Returns:
            List of rule drift monitor specifications.
        """
        print("[MonitoringAgent] Creating rule drift monitors...")
        
        drift_monitors = [
            {
                "monitor_name": "rule_fire_rate_stability",
                "metric": "Daily fire rate per rule",
                "check_method": "Compare to 7-day moving average",
                "alert_threshold_deviation": 25,  # Alert if > 25% deviation
                "frequency": "daily",
            },
            {
                "monitor_name": "decision_reason_distribution",
                "metric": "Distribution of decision reasons per rule",
                "check_method": "Chi-square test against baseline",
                "alert_threshold_pvalue": 0.05,
                "frequency": "daily",
            },
            {
                "monitor_name": "condition_decision_patterns",
                "metric": "Decision mix by condition",
                "check_method": "Compare daily pattern to 14-day baseline",
                "alert_threshold_deviation": 15,
                "frequency": "daily",
            },
        ]
        
        print(f"[MonitoringAgent] ✓ Created {len(drift_monitors)} rule drift monitors")
        return drift_monitors
    
    def create_experiment_monitoring_plan(self, experiment_id: str) -> Dict[str, Any]:
        """Create monitoring plan for an active experiment.
        
        Args:
            experiment_id: ID of the experiment
            
        Returns:
            Monitoring plan specification.
        """
        print(f"[MonitoringAgent] Creating monitoring plan for experiment {experiment_id}...")
        
        plan = {
            "experiment_id": experiment_id,
            "monitoring_objectives": [
                "Track primary KPIs (approval, decline rates)",
                "Monitor guardrail metrics",
                "Detect early warning signals",
                "Support real-time decision to continue/pause/stop",
            ],
            "daily_checks": {
                "primary_metrics": {
                    "sample_size_check": "Min 100 cases per arm",
                    "metric_tracking": ["approval_rate", "decline_rate"],
                    "guardrail_status": "All guardrails within bounds",
                },
                "quality_checks": {
                    "data_integrity": "No schema drift or missing values",
                    "assignment_balance": "Control/Treatment split ~50/50",
                },
            },
            "escalation_criteria": [
                {
                    "condition": "Any guardrail exceeded",
                    "action": "Immediate pause and root cause analysis",
                },
                {
                    "condition": "Metric p-value < 0.05 in unexpected direction",
                    "action": "Alert engineering and analytics team",
                },
            ],
            "reporting": {
                "frequency": "Daily",
                "stakeholders": ["Underwriting leadership", "Data Science", "Engineering"],
                "metrics": ["Approval rate", "Decline rate", "Referral rate", "Alignment"],
                "segments": ["Overall", "By condition", "By age group"],
            },
        }
        
        print(f"[MonitoringAgent] ✓ Experiment monitoring plan created")
        return plan
    
    def create_dashboard_spec(self) -> Dict[str, Any]:
        """Create dashboard specification for URE monitoring.
        
        Returns:
            Dashboard specification.
        """
        print("[MonitoringAgent] Creating dashboard specification...")
        
        dashboard_spec = {
            "dashboard_name": "URE Performance & Analytics Dashboard",
            "refresh_cadence": "Hourly",
            "primary_panels": [
                {
                    "name": "KPI Summary",
                    "metrics": [
                        "Approval Rate",
                        "Decline Rate",
                        "Referral Rate",
                        "Load Rate",
                    ],
                    "time_range": "Last 7 days with comparison to prior week",
                },
                {
                    "name": "Decision Distribution",
                    "chart_type": "Pie chart",
                    "segments": ["Accept", "Load", "Refer", "Exclusion"],
                },
                {
                    "name": "Trend Analysis",
                    "chart_type": "Time series",
                    "metrics": ["Approval trend", "Decline trend", "Manual review % trend"],
                    "granularity": "Daily",
                },
                {
                    "name": "Segmentation Analysis",
                    "breakdown_by": ["Condition", "Age group", "Income band"],
                    "metrics": ["Approval rate", "Decline rate"],
                },
                {
                    "name": "Human-URE Alignment",
                    "metric": "% of matching decisions",
                    "segments": ["By condition", "By outcome"],
                },
                {
                    "name": "Data Quality Status",
                    "checks": ["Freshness", "Completeness", "Schema integrity"],
                },
            ],
            "access_control": {
                "view_roles": ["Underwriting", "Analytics", "Leadership"],
                "export_roles": ["Analytics", "Leadership"],
            },
        }
        
        print("[MonitoringAgent] ✓ Dashboard spec created")
        return dashboard_spec
    
    def create_alerting_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Create alerting rules for operational issues.
        
        Returns:
            Dictionary of alerting rule groups.
        """
        print("[MonitoringAgent] Creating alerting rules...")
        
        alerting_rules = {
            "critical": [
                {
                    "name": "Approval rate collapse",
                    "condition": "approval_rate < 30%",
                    "window": "Last 24 hours",
                    "severity": "CRITICAL",
                    "action": "Page on-call, pause new rule deployments",
                },
                {
                    "name": "Data ingestion failure",
                    "condition": "No data updates for > 24 hours",
                    "window": "Real-time check",
                    "severity": "CRITICAL",
                    "action": "Alert data platform team",
                },
            ],
            "high": [
                {
                    "name": "Decline rate spike",
                    "condition": "decline_rate > baseline + 5%",
                    "window": "Last 24 hours vs 7-day average",
                    "severity": "HIGH",
                    "action": "Alert underwriting team, review recent rule changes",
                },
                {
                    "name": "Alignment degradation",
                    "condition": "human_ure_alignment < 75%",
                    "window": "Last 24 hours",
                    "severity": "HIGH",
                    "action": "Review divergence patterns, check for rule drift",
                },
            ],
            "medium": [
                {
                    "name": "Data freshness",
                    "condition": "Last update > 12 hours ago",
                    "window": "Real-time",
                    "severity": "MEDIUM",
                    "action": "Notify analytics team",
                },
            ],
        }
        
        print("[MonitoringAgent] ✓ Alerting rules created")
        return alerting_rules
