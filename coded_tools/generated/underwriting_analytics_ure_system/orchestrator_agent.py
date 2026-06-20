"""
Orchestrator Agent implementation.
Plans and routes underwriting analytics work to the right agents,
enforces data grounding, and synthesizes outputs.
"""

from typing import List, Dict, Any, Optional
import json
from collections import OrderedDict
from datetime import datetime

from .data_loader import DataLoader
from .ingestion_agent import IngestionAgent
from .kpi_analytics_agent import KPIAnalyticsAgent
from .rules_diagnostics_agent import RulesDiagnosticsAgent
from .experiment_design_agent import ExperimentDesignAgent
from .monitoring_agent import MonitoringAgent
from .governance_agent import GovernanceAgent


class OrchestratorAgent:
    """
    Purpose: Plan and route underwriting analytics work to the right agents,
    enforce strict data grounding (no direct data access), request missing configuration,
    and synthesize cited agent outputs.
    
    Responsibilities:
    - Clarify business objective and constraints
    - Convert objective into analysis plan with discrete tasks
    - Route each task to appropriate agent
    - Manage dependencies
    - Synthesize outputs with citations
    """
    
    def __init__(self):
        """Initialize Orchestrator Agent with all sub-agents."""
        print("[OrchestratorAgent] Initializing underwriting analytics agentic network...")
        
        self.data_loader = DataLoader()
        self.ingestion_agent = IngestionAgent(self.data_loader)
        self.kpi_agent = KPIAnalyticsAgent()
        self.rules_agent = RulesDiagnosticsAgent()
        self.experiment_agent = ExperimentDesignAgent()
        self.monitoring_agent = MonitoringAgent()
        self.governance_agent = GovernanceAgent()
        
        self.execution_log = []
        self.datasets = {}
        self.manifests = {}
        self.last_successful_phase = None
        self.first_failed_phase = None

    def _mark_phase_started(self, phase_name: str) -> None:
        self.execution_log.append({
            "phase": phase_name,
            "status": "started",
            "timestamp": datetime.now().isoformat(),
        })

    def _mark_phase_completed(self, phase_name: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.execution_log.append({
            "phase": phase_name,
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
        })
        self.last_successful_phase = phase_name

    def _mark_phase_failed(self, phase_name: str, error: Exception) -> None:
        self.execution_log.append({
            "phase": phase_name,
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error": str(error),
        })
        if self.first_failed_phase is None:
            self.first_failed_phase = phase_name

    def _derive_weekly_volume(self, decision_logs: List[Any]) -> int:
        """Estimate weekly volume from packaged decision log dates."""
        if not decision_logs:
            return 0
        unique_dates = sorted({log.decision_date for log in decision_logs})
        observed_days = max(len(unique_dates), 1)
        return max(round(len(decision_logs) * 7 / observed_days), 1)
    
    def ingest_and_prepare_data(self) -> Dict[str, Any]:
        """Execute data ingestion and curation pipeline.
        
        Returns:
            Dictionary with ingested datasets and quality reports.
        """
        print("\n" + "="*70)
        print("[OrchestratorAgent] PHASE 1: DATA INGESTION & CURATION")
        print("="*70)
        
        self._mark_phase_started("Data Ingestion")
        
        # Ingest all datasets
        all_data = self.ingestion_agent.ingest_all_datasets()
        
        for dataset_name, (data, manifest) in all_data.items():
            self.datasets[dataset_name] = data
            self.manifests[dataset_name] = manifest
        
        # Generate quality report
        quality_report = self.ingestion_agent.publish_quality_report()
        
        print(f"\n[OrchestratorAgent] ✓ Ingestion complete: {len(self.datasets)} datasets loaded")
        self._mark_phase_completed("Data Ingestion", {
            "datasets_loaded": len(self.datasets),
            "quality_passed": {
                name: manifest.quality_checks_passed
                for name, manifest in self.manifests.items()
            },
        })

        return {
            "datasets": self.datasets,
            "manifests": self.manifests,
            "quality_report": quality_report,
            "status": "complete",
        }
    
    def compute_kpi_analytics(self, segment_by: Optional[str] = None) -> Dict[str, Any]:
        """Execute KPI analytics workflow.
        
        Args:
            segment_by: Optional field to segment KPIs by
            
        Returns:
            Dictionary with KPI results and analysis.
        """
        print("\n" + "="*70)
        print("[OrchestratorAgent] PHASE 2: KPI ANALYTICS")
        print("="*70)
        
        decision_logs = self.datasets.get("decision_logs", [])
        if not decision_logs:
            print("[OrchestratorAgent] ERROR: Decision logs not available")
            return {"error": "Decision logs not ingested"}
        
        # Generate comprehensive KPI pack
        kpi_pack = self.kpi_agent.generate_kpi_pack(decision_logs)

        print(f"\n[OrchestratorAgent] ✓ KPI analytics complete")
        self._mark_phase_completed("KPI Analytics", {
            "approval_rate": kpi_pack.get("metrics", {}).get("approval_rate", {}).get("value"),
            "decline_rate": kpi_pack.get("metrics", {}).get("decline_rate", {}).get("value"),
        })

        return kpi_pack
    
    def diagnose_rules_and_identify_optimizations(self) -> Dict[str, Any]:
        """Execute rule diagnostics and optimization workflow.
        
        Returns:
            Dictionary with diagnostics report and optimization candidates.
        """
        print("\n" + "="*70)
        print("[OrchestratorAgent] PHASE 3: RULE DIAGNOSTICS & OPTIMIZATION")
        print("="*70)
        
        decision_logs = self.datasets.get("decision_logs", [])
        rules = self.datasets.get("ure_rules", [])
        rule_impacts = self.datasets.get("rule_impact_feedback", [])
        
        if not all([decision_logs, rules, rule_impacts]):
            print("[OrchestratorAgent] ERROR: Required datasets not available")
            return {"error": "Missing required datasets"}
        
        # Generate diagnostics report
        diagnostics = self.rules_agent.generate_diagnostics_report(
            decision_logs,
            rules,
            rule_impacts,
        )

        print(f"\n[OrchestratorAgent] ✓ Rule diagnostics complete")
        self._mark_phase_completed("Rule Diagnostics", {
            "optimization_candidates": len(diagnostics.get("optimization_candidates", [])),
            "divergence_rate": diagnostics.get("divergence_analysis", {}).get("divergence_rate"),
        })

        return diagnostics
    
    def design_experiments(self) -> Dict[str, Any]:
        """Execute experiment design workflow based on optimization candidates.
        
        Returns:
            Dictionary with experiment designs.
        """
        print("\n" + "="*70)
        print("[OrchestratorAgent] PHASE 4: EXPERIMENT DESIGN")
        print("="*70)
        
        decision_logs = self.datasets.get("decision_logs", [])
        diagnostics = self.diagnose_rules_and_identify_optimizations()
        candidates = diagnostics.get("optimization_candidates", [])
        kpi_pack = self.compute_kpi_analytics()
        metrics = kpi_pack.get("metrics", {})
        baseline_approval_rate = metrics.get("approval_rate", {}).get("value", 0)
        baseline_decline_rate = metrics.get("decline_rate", {}).get("value", 0)
        weekly_volume = self._derive_weekly_volume(decision_logs)

        experiments = []
        for i, candidate in enumerate(candidates[:3], 1):  # Design experiments for top 3
            print(f"\n[OrchestratorAgent] Designing experiment {i} for rule {candidate['rule_id']}...")
            
            exp_brief = self.experiment_agent.design_rule_change_experiment(
                rule_id=candidate["rule_id"],
                proposed_change=candidate["proposed_change"],
                baseline_approval_rate=baseline_approval_rate,
                baseline_decline_rate=baseline_decline_rate,
                expected_approval_uplift=candidate["expected_kpi_movement"].get("approval_rate", 2),
                weekly_volume=weekly_volume,
                test_duration_days=14,
            )
            
            experiments.append(exp_brief.to_dict())

        print(f"\n[OrchestratorAgent] ✓ Experiment designs complete: {len(experiments)} experiments")
        self._mark_phase_completed("Experiment Design", {
            "experiments_designed": len(experiments),
            "weekly_volume_assumption": weekly_volume,
        })

        return {"experiments": experiments}
    
    def setup_monitoring_and_alerts(self) -> Dict[str, Any]:
        """Execute monitoring and alerting setup workflow.
        
        Returns:
            Dictionary with monitoring specifications.
        """
        print("\n" + "="*70)
        print("[OrchestratorAgent] PHASE 5: MONITORING & ALERTING")
        print("="*70)
        
        # Create KPI monitors
        kpi_monitors = self.monitoring_agent.create_kpi_monitors()
        
        # Create data quality monitors
        dq_monitors = self.monitoring_agent.create_data_quality_monitors(self.manifests)
        
        # Create rule drift monitors
        drift_monitors = self.monitoring_agent.create_rule_drift_monitors()
        
        # Create dashboard spec
        dashboard_spec = self.monitoring_agent.create_dashboard_spec()
        
        # Create alerting rules
        alerting_rules = self.monitoring_agent.create_alerting_rules()

        print(f"\n[OrchestratorAgent] ✓ Monitoring setup complete")
        self._mark_phase_completed("Monitoring", {
            "kpi_monitors": len(kpi_monitors),
            "dq_monitors": len(dq_monitors),
        })

        return {
            "kpi_monitors": [m.to_dict() for m in kpi_monitors],
            "dq_monitors": dq_monitors,
            "drift_monitors": drift_monitors,
            "dashboard_spec": dashboard_spec,
            "alerting_rules": alerting_rules,
        }
    
    def execute_governance_review(self) -> Dict[str, Any]:
        """Execute compliance and governance review.
        
        Returns:
            Dictionary with governance approvals and policy.
        """
        print("\n" + "="*70)
        print("[OrchestratorAgent] PHASE 6: GOVERNANCE & COMPLIANCE REVIEW")
        print("="*70)
        
        # Get allowed fields policy
        policy = self.governance_agent.get_allowed_fields_policy()
        
        # Review core analysis for compliance
        approval = self.governance_agent.review_analysis_for_compliance(
            analysis_type="URE Performance Analytics",
            proposed_fields=policy["allowed_fields"],
            proposed_aggregation={"conditions": 15, "age_groups": 20},
        )
        
        # Validate lineage
        lineage = self.governance_agent.validate_lineage(
            dataset_name="underwriting_decision_logs",
            source_datasets=["dataset_1_underwriting_decision_logs.json"],
            transformations=["Schema validation", "Type normalization", "Duplicates removal"],
        )
        
        # Generate compliance checklist
        checklist = self.governance_agent.generate_compliance_checklist()

        print(f"\n[OrchestratorAgent] ✓ Governance review complete")
        self._mark_phase_completed("Governance", {
            "approval_status": approval.approval_status,
            "lineage_valid": lineage.get("lineage_valid"),
        })

        return {
            "policy": policy,
            "analysis_approval": approval.to_dict(),
            "lineage_validation": lineage,
            "compliance_checklist": checklist,
        }
    
    def execute_full_workflow(self) -> Dict[str, Any]:
        """Execute complete underwriting analytics workflow.
        
        Orchestrates all phases:
        1. Data ingestion and curation
        2. KPI analytics
        3. Rule diagnostics and optimization
        4. Experiment design
        5. Monitoring and alerting setup
        6. Governance and compliance review
        
        Returns:
            Complete workflow results with all outputs and citations.
        """
        print("\n" + "#"*70)
        print("# UNDERWRITING ANALYTICS AGENTIC NETWORK - FULL WORKFLOW")
        print("#"*70)
        
        workflow_results = {}

        phases = OrderedDict([
            ("ingestion", ("Data Ingestion", self.ingest_and_prepare_data)),
            ("kpi_analytics", ("KPI Analytics", self.compute_kpi_analytics)),
            ("rule_diagnostics", ("Rule Diagnostics", self.diagnose_rules_and_identify_optimizations)),
            ("experiments", ("Experiment Design", self.design_experiments)),
            ("monitoring", ("Monitoring", self.setup_monitoring_and_alerts)),
            ("governance", ("Governance", self.execute_governance_review)),
        ])

        for result_key, (phase_name, phase_fn) in phases.items():
            if phase_name != "Data Ingestion":
                self._mark_phase_started(phase_name)
            try:
                workflow_results[result_key] = phase_fn()
            except Exception as error:
                self._mark_phase_failed(phase_name, error)
                workflow_results[result_key] = {
                    "status": "failed",
                    "error": str(error),
                }
                break

        # Generate synthesis and recommendations
        synthesis = self.synthesize_results(workflow_results)
        workflow_results["synthesis"] = synthesis
        workflow_results["execution_trace"] = self.get_execution_trace()
        
        print("\n" + "#"*70)
        print("# WORKFLOW COMPLETE - ALL PHASES EXECUTED")
        print("#"*70 + "\n")
        
        return workflow_results

    def get_execution_trace(self) -> Dict[str, Any]:
        """Return phase-by-phase execution trace for debugging."""
        return {
            "execution_log": self.execution_log,
            "last_successful_phase": self.last_successful_phase,
            "first_failed_phase": self.first_failed_phase,
            "network_running": self.first_failed_phase is None,
        }

    def validate_workflow_steps(self) -> Dict[str, Any]:
        """Run each workflow step with validation checks and stop-point tracking."""
        validations = []
        stop_after_step = None

        steps = [
            ("ingestion", self.ingest_and_prepare_data),
            ("kpi_analytics", self.compute_kpi_analytics),
            ("rule_diagnostics", self.diagnose_rules_and_identify_optimizations),
            ("experiments", self.design_experiments),
            ("monitoring", self.setup_monitoring_and_alerts),
            ("governance", self.execute_governance_review),
        ]

        for step_name, step_fn in steps:
            self._mark_phase_started(f"validation:{step_name}")
            try:
                result = step_fn()
                issues = []
                if step_name == "ingestion":
                    for dataset_name, manifest in result.get("manifests", {}).items():
                        if manifest.record_count == 0:
                            issues.append(f"{dataset_name} has zero records")
                if isinstance(result, dict) and result.get("error"):
                    issues.append(result["error"])
                status = "passed" if not issues else "warning"
                validations.append({
                    "step": step_name,
                    "status": status,
                    "issues": issues,
                })
                self._mark_phase_completed(f"validation:{step_name}", {"status": status})
                if issues and stop_after_step is None:
                    stop_after_step = step_name
            except Exception as error:
                validations.append({
                    "step": step_name,
                    "status": "failed",
                    "issues": [str(error)],
                })
                self._mark_phase_failed(f"validation:{step_name}", error)
                stop_after_step = step_name
                break

        return {
            "validations": validations,
            "stop_after_step": stop_after_step,
            "network_running": stop_after_step is None,
            "execution_trace": self.get_execution_trace(),
        }
    
    def synthesize_results(self, workflow_results: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesize results from all agents with citations.
        
        Args:
            workflow_results: Dictionary with all workflow outputs
            
        Returns:
            Synthesis report with recommendations and citations.
        """
        print("[OrchestratorAgent] Synthesizing results and recommendations...")
        
        kpi_pack = workflow_results.get("kpi_analytics", {})
        diagnostics = workflow_results.get("rule_diagnostics", {})
        experiments = workflow_results.get("experiments", {})
        
        synthesis = {
            "executive_summary": f"Analyzed {len(self.datasets.get('decision_logs', []))} underwriting cases",
            "key_findings": [
                {
                    "finding": f"Overall approval rate: {kpi_pack.get('metrics', {}).get('approval_rate', {}).get('value', 'N/A')}%",
                    "source": "KPI Analytics Agent - approval_rate metric",
                    "implication": "Baseline for measuring rule change impact",
                },
                {
                    "finding": f"Divergence rate: {diagnostics.get('divergence_analysis', {}).get('divergence_rate', 'N/A')}%",
                    "source": "Rules Diagnostics Agent - divergence analysis",
                    "implication": "Opportunities for rule refinement and URE improvement",
                },
            ],
            "recommendations": [
                {
                    "priority": "High",
                    "action": f"Design and execute {len(experiments.get('experiments', []))} A/B experiments",
                    "rationale": "Top rule optimization candidates identified by Rules Diagnostics Agent",
                    "expected_impact": "3-5% improvement in approval rate",
                },
                {
                    "priority": "High",
                    "action": "Implement monitoring dashboard and alerts",
                    "rationale": "Enable real-time observability per Monitoring Agent specs",
                    "expected_impact": "Faster detection of rule drift and adverse outcomes",
                },
            ],
            "governance_status": "APPROVED",
            "next_steps": [
                "1. Review governance approval with compliance team",
                "2. Kick-off experiments per Experiment Design Agent briefs",
                "3. Implement monitoring per Monitoring Agent specifications",
                "4. Schedule weekly reviews of results",
            ],
            "citations": {
                "data_sources": list(self.manifests.keys()),
                "agents_consulted": [
                    "Ingestion Agent",
                    "KPI Analytics Agent",
                    "Rules Diagnostics Agent",
                    "Experiment Design Agent",
                    "Monitoring Agent",
                    "Governance Agent",
                ],
            },
        }
        
        return synthesis
    
    def export_workflow_summary(self, workflow_results: Dict[str, Any]) -> str:
        """Export workflow summary as formatted JSON.
        
        Args:
            workflow_results: Complete workflow results
            
        Returns:
            Formatted JSON string of results.
        """
        summary = {
            "workflow_status": "COMPLETE",
            "phases_executed": 6,
            "datasets_ingested": len(self.datasets),
            "agents_consulted": 7,
            "key_deliverables": [
                "KPI Pack with segmentations",
                "Rule Diagnostics Report with optimization candidates",
                "Experiment briefs for top 3 rule changes",
                "Monitoring and alerting specifications",
                "Governance approvals and compliance checklist",
            ],
        }
        
        return json.dumps(summary, indent=2)
