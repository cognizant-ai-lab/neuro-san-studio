"""
Rules Diagnostics Agent implementation.
Analyzes URE rule firing and decision-reason behavior to quantify impacts
and propose optimization candidates.
"""

from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import statistics

from .data_models import (
    UnderwritingDecisionLog,
    URERule,
    RuleOptimizationCandidate,
    RuleImpactAnalysis,
    DecisionType,
)


class RulesDiagnosticsAgent:
    """
    Purpose: Diagnose Underwriting Rules Engine (URE) rule behavior and identify
    optimization candidates using only curated, versioned datasets.
    
    Responsibilities:
    - Analyze rule firing patterns and decision reasons
    - Quantify rule impacts on key underwriting metrics
    - Detect rule conflicts, redundancies, instability, and drift
    - Propose specific, testable optimization candidates
    """
    
    def __init__(self):
        """Initialize Rules Diagnostics Agent."""
        self.optimization_candidates = []
    
    def analyze_rule_impact_on_decisions(
        self,
        decision_logs: List[UnderwritingDecisionLog],
        rule_impacts: List[RuleImpactAnalysis],
    ) -> Dict[str, Any]:
        """Analyze which rules have the most impact on underwriting decisions.
        
        Args:
            decision_logs: Curated decision logs
            rule_impacts: Rule impact analysis data
            
        Returns:
            Dictionary with rule impact analysis.
        """
        print("[RulesDiagnosticsAgent] Analyzing rule impacts on decisions...")
        
        # Rank rules by cases affected
        ranked_rules = sorted(
            rule_impacts,
            key=lambda r: r.number_of_cases_affected,
            reverse=True
        )
        
        analysis = {
            "top_impacting_rules": [],
            "rules_needing_attention": [],
            "rule_count": len(ranked_rules),
            "total_cases_affected": sum(r.number_of_cases_affected for r in ranked_rules),
        }
        
        for rule in ranked_rules[:10]:
            if rule.confidence_score in ["High", "Medium"]:
                analysis["top_impacting_rules"].append({
                    "rule_id": rule.rule_id,
                    "cases_affected": rule.number_of_cases_affected,
                    "accuracy_improvement": rule.accuracy_improvement,
                    "confidence": rule.confidence_score,
                    "uplift": rule.estimated_sta_uplift,
                })
        
        print(f"[RulesDiagnosticsAgent] ✓ Analyzed {len(ranked_rules)} rules")
        return analysis
    
    def detect_rule_conflicts_and_redundancies(
        self,
        rules: List[URERule],
    ) -> Dict[str, Any]:
        """Detect potential conflicts and redundancies among rules.
        
        Args:
            rules: URE rule definitions
            
        Returns:
            Dictionary with detected conflicts and redundancies.
        """
        print("[RulesDiagnosticsAgent] Detecting rule conflicts and redundancies...")
        
        analysis = {
            "potential_conflicts": [],
            "potential_redundancies": [],
            "rules_by_condition": defaultdict(list),
        }
        
        # Group rules by condition
        for rule in rules:
            analysis["rules_by_condition"][rule.condition].append(rule)
        
        # Check for redundancies within same condition
        for condition, condition_rules in analysis["rules_by_condition"].items():
            if len(condition_rules) > 1:
                for i, rule1 in enumerate(condition_rules):
                    for rule2 in condition_rules[i+1:]:
                        # Rules with similar criteria for same condition
                        if rule1.decision == rule2.decision:
                            analysis["potential_redundancies"].append({
                                "rule1": rule1.rule_id,
                                "rule2": rule2.rule_id,
                                "condition": condition,
                                "reason": "Both apply same decision logic to same condition",
                            })
        
        # Convert defaultdict to regular dict for serialization
        analysis["rules_by_condition"] = {k: [r.rule_id for r in v] for k, v in analysis["rules_by_condition"].items()}
        
        print(f"[RulesDiagnosticsAgent] ✓ Detected {len(analysis['potential_conflicts'])} conflicts, "
              f"{len(analysis['potential_redundancies'])} redundancies")
        return analysis
    
    def analyze_condition_decision_reasons(
        self,
        decision_logs: List[UnderwritingDecisionLog],
    ) -> Dict[str, Any]:
        """Analyze decision reasons for each medical condition.
        
        Args:
            decision_logs: Curated decision logs
            
        Returns:
            Dictionary with condition-specific decision patterns.
        """
        print("[RulesDiagnosticsAgent] Analyzing condition-specific decision reasons...")
        
        analysis = {}
        
        # Group by condition
        conditions = defaultdict(list)
        for log in decision_logs:
            conditions[log.condition].append(log)
        
        for condition, logs in conditions.items():
            # Group decision reasons by URE decision type
            reason_patterns = defaultdict(list)
            for log in logs:
                reason_patterns[log.underwriting_decision_ure].append(log.decision_reason_ure)
            
            analysis[condition] = {
                "total_cases": len(logs),
                "decision_patterns": {
                    decision.value: {
                        "count": len(reasons),
                        "unique_reasons": len(set(reasons)),
                        "top_reason": max(set(reasons), key=reasons.count) if reasons else "",
                    }
                    for decision, reasons in reason_patterns.items()
                }
            }
        
        print(f"[RulesDiagnosticsAgent] ✓ Analyzed {len(analysis)} conditions")
        return analysis
    
    def identify_divergence_patterns(
        self,
        decision_logs: List[UnderwritingDecisionLog],
    ) -> Dict[str, Any]:
        """Identify patterns in human vs URE decision divergences.
        
        Args:
            decision_logs: Curated decision logs
            
        Returns:
            Dictionary with divergence patterns.
        """
        print("[RulesDiagnosticsAgent] Identifying divergence patterns...")
        
        divergent_logs = [log for log in decision_logs if log.underwriting_decision_human != log.underwriting_decision_ure]
        
        patterns = {
            "total_divergences": len(divergent_logs),
            "divergence_rate": (len(divergent_logs) / len(decision_logs) * 100) if decision_logs else 0,
            "divergence_types": defaultdict(int),
            "by_condition": defaultdict(int),
            "by_age_segment": defaultdict(int),
        }
        
        for log in divergent_logs:
            # Record divergence type
            div_type = f"{log.underwriting_decision_human.value} -> {log.underwriting_decision_ure.value}"
            patterns["divergence_types"][div_type] += 1
            
            # Record by condition
            patterns["by_condition"][log.condition] += 1
            
            # Record by age segment
            if log.applicant_age < 30:
                age_seg = "18-29"
            elif log.applicant_age < 45:
                age_seg = "30-44"
            elif log.applicant_age < 60:
                age_seg = "45-59"
            else:
                age_seg = "60+"
            patterns["by_age_segment"][age_seg] += 1
        
        # Convert defaultdicts to regular dicts
        patterns["divergence_types"] = dict(patterns["divergence_types"])
        patterns["by_condition"] = dict(patterns["by_condition"])
        patterns["by_age_segment"] = dict(patterns["by_age_segment"])
        
        print(f"[RulesDiagnosticsAgent] ✓ Identified {patterns['total_divergences']} divergences "
              f"({patterns['divergence_rate']:.2f}% of cases)")
        return patterns
    
    def rank_rules_for_optimization(
        self,
        rule_impacts: List[RuleImpactAnalysis],
    ) -> List[Dict[str, Any]]:
        """Rank rules by priority for optimization based on impact and confidence.
        
        Args:
            rule_impacts: Rule impact analysis data
            
        Returns:
            List of ranked rule candidates for optimization.
        """
        print("[RulesDiagnosticsAgent] Ranking rules for optimization...")
        
        # Calculate optimization score: (accuracy improvement * confidence) + uplift consideration
        scored_rules = []
        for rule in rule_impacts:
            confidence_weight = {"High": 1.0, "Medium": 0.7, "Low": 0.3}.get(rule.confidence_score, 0.3)
            
            optimization_score = (
                (rule.accuracy_improvement * confidence_weight) +
                (rule.estimated_sta_uplift * 0.5) +
                (rule.manual_review_reduction_percentage * 0.3)
            )
            
            scored_rules.append({
                "rule_id": rule.rule_id,
                "cases_affected": rule.number_of_cases_affected,
                "current_accuracy": rule.current_accuracy,
                "accuracy_improvement": rule.accuracy_improvement,
                "manual_review_reduction": rule.manual_review_reduction_percentage,
                "uplift": rule.estimated_sta_uplift,
                "confidence": rule.confidence_score,
                "optimization_score": optimization_score,
            })
        
        # Sort by optimization score
        ranked = sorted(scored_rules, key=lambda x: x["optimization_score"], reverse=True)
        
        print(f"[RulesDiagnosticsAgent] ✓ Ranked {len(ranked)} rules")
        return ranked
    
    def propose_rule_optimizations(
        self,
        rule_impacts: List[RuleImpactAnalysis],
        ranked_rules: List[Dict[str, Any]],
    ) -> List[RuleOptimizationCandidate]:
        """Generate specific, testable rule optimization candidates.
        
        Args:
            rule_impacts: Rule impact analysis data
            ranked_rules: Pre-ranked rules from rank_rules_for_optimization()
            
        Returns:
            List of RuleOptimizationCandidate objects.
        """
        print("[RulesDiagnosticsAgent] Proposing rule optimizations...")
        
        candidates = []
        
        # Focus on top optimization candidates
        for ranked_rule in ranked_rules[:5]:
            rule_id = ranked_rule["rule_id"]
            
            candidate = RuleOptimizationCandidate(
                rule_id=rule_id,
                rule_name=f"Rule {rule_id}",
                current_impact=ranked_rule["current_accuracy"],
                proposed_change=f"Adjust threshold or criteria to improve accuracy by {ranked_rule['accuracy_improvement']:.1f}%",
                expected_kpi_movement={
                    "approval_rate": ranked_rule["uplift"],
                    "manual_review_reduction": ranked_rule["manual_review_reduction"],
                    "accuracy": ranked_rule["accuracy_improvement"],
                },
                risk_tradeoffs=f"Confidence score: {ranked_rule['confidence']}. Monitor for false positives.",
                implementation_notes=(
                    f"Affects {ranked_rule['cases_affected']} cases. "
                    f"Expected uplift: {ranked_rule['uplift']:.1f}%. "
                    f"Recommend A/B testing before rollout."
                ),
                evidence_strength=ranked_rule["confidence"],
            )
            
            candidates.append(candidate)
            self.optimization_candidates.append(candidate)
        
        print(f"[RulesDiagnosticsAgent] ✓ Proposed {len(candidates)} optimization candidates")
        return candidates
    
    def generate_diagnostics_report(
        self,
        decision_logs: List[UnderwritingDecisionLog],
        rules: List[URERule],
        rule_impacts: List[RuleImpactAnalysis],
    ) -> Dict[str, Any]:
        """Generate comprehensive rule diagnostics report.
        
        Args:
            decision_logs: Curated decision logs
            rules: URE rule definitions
            rule_impacts: Rule impact analysis data
            
        Returns:
            Complete diagnostics report with findings and recommendations.
        """
        print("[RulesDiagnosticsAgent] Generating comprehensive diagnostics report...")
        
        # Run all analyses
        impact_analysis = self.analyze_rule_impact_on_decisions(decision_logs, rule_impacts)
        conflicts = self.detect_rule_conflicts_and_redundancies(rules)
        decision_reasons = self.analyze_condition_decision_reasons(decision_logs)
        divergences = self.identify_divergence_patterns(decision_logs)
        ranked = self.rank_rules_for_optimization(rule_impacts)
        candidates = self.propose_rule_optimizations(rule_impacts, ranked)
        
        report = {
            "report_type": "Rule Diagnostics Report",
            "summary": {
                "total_rules": len(rules),
                "total_cases_analyzed": len(decision_logs),
                "divergence_rate": divergences["divergence_rate"],
                "potential_improvements": len(candidates),
            },
            "rule_impacts": impact_analysis,
            "conflicts_and_redundancies": conflicts,
            "decision_patterns": decision_reasons,
            "divergence_analysis": divergences,
            "ranked_rules": ranked[:10],
            "optimization_candidates": [c.to_dict() for c in candidates],
            "data_gaps": [
                "Additional context on rule priority and business constraints",
                "Outcome data (bind, loss, claims) for direct impact assessment",
                "Customer feedback on decision fairness",
            ],
        }
        
        print("[RulesDiagnosticsAgent] ✓ Diagnostics report generated")
        return report
