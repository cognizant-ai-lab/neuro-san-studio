"""
Experiment Design Agent implementation.
Designs A/B, shadow, canary, and phased rollout experiments for URE changes.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from .data_models import (
    KPIResult,
    ExperimentBrief,
)


class ExperimentDesignAgent:
    """
    Purpose: Design statistically sound experiments and safe rollout plans to improve
    Underwriting Rules Engine (URE) performance.
    
    Responsibilities:
    - Translate business objectives into experiment proposals
    - Recommend appropriate launch mechanisms
    - Define assignment strategy and sample size guidance
    - Specify measurement and analysis plan
    - Identify risks and safeguards
    """
    
    def __init__(self):
        """Initialize Experiment Design Agent."""
        self.experiments = []
    
    def design_rule_change_experiment(
        self,
        rule_id: str,
        proposed_change: str,
        baseline_approval_rate: float,
        baseline_decline_rate: float,
        expected_approval_uplift: float,
        weekly_volume: int,
        test_duration_days: int = 14,
    ) -> ExperimentBrief:
        """Design an experiment for testing a proposed rule change.
        
        Args:
            rule_id: ID of the rule being changed
            proposed_change: Description of the change
            baseline_approval_rate: Current approval rate %
            baseline_decline_rate: Current decline rate %
            expected_approval_uplift: Expected uplift in approval rate %
            weekly_volume: Expected weekly volume
            test_duration_days: Duration of the test
            
        Returns:
            ExperimentBrief with experiment design.
        """
        print(f"[ExperimentDesignAgent] Designing experiment for {rule_id}...")
        
        # Calculate sample size (simplified)
        test_weeks = test_duration_days / 7
        expected_weekly_test_volume = (weekly_volume / 2) * test_weeks  # 50/50 split
        
        brief = ExperimentBrief(
            hypothesis=f"Changing {rule_id} ({proposed_change}) will increase approval rate by {expected_approval_uplift}%",
            primary_kpis=["approval_rate", "decline_rate"],
            secondary_kpis=["manual_review_rate", "human_ure_alignment"],
            guardrails=[
                {
                    "metric": "decline_rate",
                    "threshold": baseline_decline_rate + 5,
                    "direction": "above",
                    "action": "STOP_TEST",
                },
                {
                    "metric": "approval_rate",
                    "threshold": baseline_approval_rate - 5,
                    "direction": "below",
                    "action": "STOP_TEST",
                },
            ],
            target_population=f"All cases evaluated by {rule_id}",
            unit_of_randomization="application_id",
            experiment_type="A/B",
            expected_sample_size=int(expected_weekly_test_volume),
            test_duration_days=test_duration_days,
            rollout_schedule=f"Week 1-2: 50/50 split | Week 3+: Gradual rollout if positive",
            analysis_plan=(
                "Intent-to-treat analysis. "
                "Measure approval/decline rates daily. "
                "Perform segment-level analysis by age, condition, income_band. "
                "Conduct t-test for primary metrics. "
                "Calculate confidence intervals (95%)."
            ),
            rollback_criteria=[
                "Decline rate increases >3% with p<0.05",
                "Approval rate drops >3% with p<0.05",
                "Any adverse fairness impact detected",
                "Unexpected system errors or data quality issues",
            ],
        )
        
        self.experiments.append(brief)
        print(f"[ExperimentDesignAgent] ✓ Experiment designed for {rule_id}")
        return brief
    
    def design_shadow_mode_experiment(
        self,
        rule_id: str,
        proposed_change: str,
        duration_days: int = 7,
    ) -> ExperimentBrief:
        """Design a shadow mode experiment (observe without impacting production).
        
        Args:
            rule_id: ID of the rule being tested
            proposed_change: Description of the change
            duration_days: Duration of observation
            
        Returns:
            ExperimentBrief with shadow mode design.
        """
        print(f"[ExperimentDesignAgent] Designing shadow mode experiment for {rule_id}...")
        
        brief = ExperimentBrief(
            hypothesis=f"Proposed {rule_id} change ({proposed_change}) will improve decisions without production impact",
            primary_kpis=["decision_divergence", "alignment_improvement"],
            secondary_kpis=["approval_rate", "decline_rate"],
            guardrails=[
                {
                    "metric": "accuracy_improvement",
                    "threshold": -5,
                    "direction": "below",
                    "action": "INVESTIGATE",
                },
            ],
            target_population=f"100% of cases (shadowed only)",
            unit_of_randomization="application_id",
            experiment_type="Shadow",
            expected_sample_size=0,  # Shadow mode doesn't split traffic
            test_duration_days=duration_days,
            rollout_schedule=f"Shadow mode: {duration_days} days observation | Decision at completion",
            analysis_plan=(
                "Compare proposed decision vs actual URE decision. "
                "Analyze divergence patterns. "
                "Calculate accuracy improvements. "
                "Validate business logic against expected outcomes."
            ),
            rollback_criteria=[
                "Accuracy drops significantly",
                "Unexpected divergence patterns detected",
            ],
        )
        
        self.experiments.append(brief)
        print(f"[ExperimentDesignAgent] ✓ Shadow mode experiment designed for {rule_id}")
        return brief
    
    def design_canary_rollout(
        self,
        rule_id: str,
        proposed_change: str,
        stages: List[Dict[str, Any]],
    ) -> ExperimentBrief:
        """Design a canary rollout experiment (gradual traffic ramp).
        
        Args:
            rule_id: ID of the rule being rolled out
            proposed_change: Description of the change
            stages: List of rollout stages (e.g., [{"percentage": 10, "duration_days": 2}])
            
        Returns:
            ExperimentBrief with canary design.
        """
        print(f"[ExperimentDesignAgent] Designing canary rollout for {rule_id}...")
        
        # Format rollout schedule
        schedule_parts = []
        for i, stage in enumerate(stages, 1):
            pct = stage.get("percentage", 0)
            days = stage.get("duration_days", 1)
            schedule_parts.append(f"Stage {i}: {pct}% for {days} days")
        rollout_schedule = " → ".join(schedule_parts) + " → 100%"
        
        total_duration = sum(s.get("duration_days", 1) for s in stages)
        
        brief = ExperimentBrief(
            hypothesis=f"Canary rollout of {rule_id} ({proposed_change}) will minimize risk while validating impact",
            primary_kpis=["approval_rate", "decline_rate"],
            secondary_kpis=["accuracy", "manual_review_rate"],
            guardrails=[
                {
                    "metric": "system_health",
                    "threshold": 99.5,
                    "direction": "below",
                    "action": "PAUSE_AND_INVESTIGATE",
                },
                {
                    "metric": "decline_rate",
                    "threshold": 5,  # Alert threshold
                    "direction": "above",
                    "action": "PAUSE_AND_REVIEW",
                },
            ],
            target_population=f"Staged rollout starting at low percentage",
            unit_of_randomization="application_id",
            experiment_type="Canary",
            expected_sample_size=0,  # Progressive
            test_duration_days=total_duration,
            rollout_schedule=rollout_schedule,
            analysis_plan=(
                "Daily health checks of primary metrics. "
                "Per-stage analysis before advancing. "
                "Automatic pause on guardrail breach. "
                "Segment-level monitoring for fairness."
            ),
            rollback_criteria=[
                "Any guardrail breach",
                "System degradation",
                "Unexpected business logic errors",
                "User complaints or fraud signals",
            ],
        )
        
        self.experiments.append(brief)
        print(f"[ExperimentDesignAgent] ✓ Canary rollout designed for {rule_id}")
        return brief
    
    def estimate_sample_size(
        self,
        baseline_rate: float,
        expected_effect: float,
        significance_level: float = 0.05,
        power: float = 0.80,
        weekly_volume: int = 10000,
    ) -> Dict[str, Any]:
        """Estimate required sample size for an experiment.
        
        Args:
            baseline_rate: Baseline metric rate (as proportion)
            expected_effect: Expected effect size (as proportion)
            significance_level: Type I error rate (default 0.05)
            power: Statistical power (default 0.80)
            weekly_volume: Expected weekly volume for volume calculations
            
        Returns:
            Dictionary with sample size calculations.
        """
        # Simplified sample size calculation (two-proportion z-test)
        import math
        
        p1 = baseline_rate / 100
        p2 = (baseline_rate + expected_effect) / 100
        
        # Z-scores
        z_alpha = 1.96  # For alpha=0.05, two-tailed
        z_beta = 0.84   # For power=0.80
        
        # Pooled proportion
        p_pool = (p1 + p2) / 2
        
        # Sample size per arm
        n = ((z_alpha + z_beta) ** 2 * (2 * p_pool * (1 - p_pool))) / ((p2 - p1) ** 2)
        
        weeks_needed = (n * 2) / weekly_volume  # For both control and treatment
        
        return {
            "sample_size_per_arm": int(math.ceil(n)),
            "total_sample_size": int(math.ceil(n * 2)),
            "control_group_size": int(math.ceil(n)),
            "treatment_group_size": int(math.ceil(n)),
            "weeks_to_collect": max(1, math.ceil(weeks_needed)),
            "assumptions": {
                "baseline_rate": baseline_rate,
                "expected_effect": expected_effect,
                "significance_level": significance_level,
                "power": power,
                "weekly_volume": weekly_volume,
            },
        }
    
    def generate_experiment_brief(
        self,
        experiment_type: str,
        rule_id: str,
        objective: str,
        baseline_metrics: Dict[str, float],
    ) -> ExperimentBrief:
        """Generate a generic experiment brief based on specifications.
        
        Args:
            experiment_type: Type of experiment (A/B, Shadow, Canary, Phased)
            rule_id: ID of the rule being tested
            objective: Business objective
            baseline_metrics: Dictionary of baseline metric values
            
        Returns:
            ExperimentBrief with specifications.
        """
        print(f"[ExperimentDesignAgent] Generating {experiment_type} experiment brief...")
        
        brief = ExperimentBrief(
            hypothesis=f"{experiment_type} test of {rule_id}: {objective}",
            primary_kpis=["approval_rate", "decline_rate"],
            secondary_kpis=["referral_rate", "load_rate"],
            guardrails=[],
            target_population="All eligible applicants",
            unit_of_randomization="application_id",
            experiment_type=experiment_type,
            expected_sample_size=10000,
            test_duration_days=14,
            rollout_schedule="TBD based on results",
            analysis_plan="Standard intent-to-treat analysis with segment breakdown",
            rollback_criteria=["Metric deterioration > 3%"],
        )
        
        print(f"[ExperimentDesignAgent] ✓ Brief generated")
        return brief
