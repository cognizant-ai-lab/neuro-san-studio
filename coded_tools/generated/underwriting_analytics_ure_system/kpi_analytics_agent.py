"""
KPI Analytics Agent implementation.
Computes and segments underwriting KPIs using only curated, versioned datasets.
"""

from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import statistics

from .data_models import (
    UnderwritingDecisionLog,
    KPIResult,
    DecisionType,
    ConditionSeverity,
)


class KPIAnalyticsAgent:
    """
    Purpose: Compute and explain underwriting KPIs and segmentations to evaluate
    Underwriting Rules Engine (URE) performance, using only curated datasets.
    
    Responsibilities:
    - Define and compute core KPIs aligned to business objectives
    - Segment KPIs by relevant dimensions
    - Perform trend and change-point analysis
    - Quantify uncertainty with sample sizes and confidence intervals
    - Identify KPI anomalies and potential drivers
    """
    
    def __init__(self):
        """Initialize KPI Analytics Agent."""
        self.kpi_results = []
        self.data_version = "1.0.0"
    
    def compute_approval_rate(
        self,
        decision_logs: List[UnderwritingDecisionLog],
        segment_by: Optional[str] = None,
    ) -> List[KPIResult]:
        """Compute approval rate KPI.
        
        Args:
            decision_logs: Curated decision logs
            segment_by: Optional segmentation dimension (e.g., "condition", "state", "income_band")
            
        Returns:
            List of KPIResult objects, one per segment if segment_by is specified.
        """
        print("[KPIAnalyticsAgent] Computing approval rate...")
        
        if segment_by:
            return self._compute_segmented_kpi(
                decision_logs,
                kpi_name="approval_rate",
                segment_dimension=segment_by,
                filter_fn=lambda log: log.underwriting_decision_ure == DecisionType.ACCEPT,
            )
        else:
            total = len(decision_logs)
            approvals = sum(1 for log in decision_logs if log.underwriting_decision_ure == DecisionType.ACCEPT)
            
            result = KPIResult(
                kpi_name="approval_rate",
                value=(approvals / total * 100) if total > 0 else 0,
                numerator=approvals,
                denominator=total,
                sample_size=total,
                data_version=self.data_version,
                calculation_method="Count of Accept decisions / Total decisions * 100",
            )
            
            self.kpi_results.append(result)
            print(f"[KPIAnalyticsAgent] ✓ Approval rate: {result.value:.2f}% (n={total})")
            return [result]
    
    def compute_decline_rate(
        self,
        decision_logs: List[UnderwritingDecisionLog],
        segment_by: Optional[str] = None,
    ) -> List[KPIResult]:
        """Compute decline rate KPI.
        
        Args:
            decision_logs: Curated decision logs
            segment_by: Optional segmentation dimension
            
        Returns:
            List of KPIResult objects.
        """
        print("[KPIAnalyticsAgent] Computing decline rate...")
        
        if segment_by:
            return self._compute_segmented_kpi(
                decision_logs,
                kpi_name="decline_rate",
                segment_dimension=segment_by,
                filter_fn=lambda log: log.underwriting_decision_ure == DecisionType.EXCLUSION,
            )
        else:
            total = len(decision_logs)
            declines = sum(1 for log in decision_logs if log.underwriting_decision_ure == DecisionType.EXCLUSION)
            
            result = KPIResult(
                kpi_name="decline_rate",
                value=(declines / total * 100) if total > 0 else 0,
                numerator=declines,
                denominator=total,
                sample_size=total,
                data_version=self.data_version,
                calculation_method="Count of Exclusion decisions / Total decisions * 100",
            )
            
            self.kpi_results.append(result)
            print(f"[KPIAnalyticsAgent] ✓ Decline rate: {result.value:.2f}% (n={total})")
            return [result]
    
    def compute_referral_rate(
        self,
        decision_logs: List[UnderwritingDecisionLog],
        segment_by: Optional[str] = None,
    ) -> List[KPIResult]:
        """Compute referral/manual review rate KPI.
        
        Args:
            decision_logs: Curated decision logs
            segment_by: Optional segmentation dimension
            
        Returns:
            List of KPIResult objects.
        """
        print("[KPIAnalyticsAgent] Computing referral rate...")
        
        if segment_by:
            return self._compute_segmented_kpi(
                decision_logs,
                kpi_name="referral_rate",
                segment_dimension=segment_by,
                filter_fn=lambda log: log.underwriting_decision_ure == DecisionType.REFER,
            )
        else:
            total = len(decision_logs)
            referrals = sum(1 for log in decision_logs if log.underwriting_decision_ure == DecisionType.REFER)
            
            result = KPIResult(
                kpi_name="referral_rate",
                value=(referrals / total * 100) if total > 0 else 0,
                numerator=referrals,
                denominator=total,
                sample_size=total,
                data_version=self.data_version,
                calculation_method="Count of Refer decisions / Total decisions * 100",
            )
            
            self.kpi_results.append(result)
            print(f"[KPIAnalyticsAgent] ✓ Referral rate: {result.value:.2f}% (n={total})")
            return [result]
    
    def compute_load_rate(
        self,
        decision_logs: List[UnderwritingDecisionLog],
        segment_by: Optional[str] = None,
    ) -> List[KPIResult]:
        """Compute loading rate KPI.
        
        Args:
            decision_logs: Curated decision logs
            segment_by: Optional segmentation dimension
            
        Returns:
            List of KPIResult objects.
        """
        print("[KPIAnalyticsAgent] Computing load rate...")
        
        if segment_by:
            return self._compute_segmented_kpi(
                decision_logs,
                kpi_name="load_rate",
                segment_dimension=segment_by,
                filter_fn=lambda log: log.underwriting_decision_ure == DecisionType.LOAD,
            )
        else:
            total = len(decision_logs)
            loads = sum(1 for log in decision_logs if log.underwriting_decision_ure == DecisionType.LOAD)
            
            result = KPIResult(
                kpi_name="load_rate",
                value=(loads / total * 100) if total > 0 else 0,
                numerator=loads,
                denominator=total,
                sample_size=total,
                data_version=self.data_version,
                calculation_method="Count of Load decisions / Total decisions * 100",
            )
            
            self.kpi_results.append(result)
            print(f"[KPIAnalyticsAgent] ✓ Load rate: {result.value:.2f}% (n={total})")
            return [result]
    
    def compute_human_ure_alignment(
        self,
        decision_logs: List[UnderwritingDecisionLog],
        segment_by: Optional[str] = None,
    ) -> List[KPIResult]:
        """Compute alignment rate between human and URE decisions.
        
        Args:
            decision_logs: Curated decision logs
            segment_by: Optional segmentation dimension
            
        Returns:
            List of KPIResult objects.
        """
        print("[KPIAnalyticsAgent] Computing human-URE alignment...")
        
        if segment_by:
            return self._compute_segmented_kpi(
                decision_logs,
                kpi_name="human_ure_alignment",
                segment_dimension=segment_by,
                filter_fn=lambda log: log.underwriting_decision_human == log.underwriting_decision_ure,
            )
        else:
            total = len(decision_logs)
            aligned = sum(1 for log in decision_logs if log.underwriting_decision_human == log.underwriting_decision_ure)
            
            result = KPIResult(
                kpi_name="human_ure_alignment",
                value=(aligned / total * 100) if total > 0 else 0,
                numerator=aligned,
                denominator=total,
                sample_size=total,
                data_version=self.data_version,
                calculation_method="Count of matching decisions / Total decisions * 100",
            )
            
            self.kpi_results.append(result)
            print(f"[KPIAnalyticsAgent] ✓ Alignment rate: {result.value:.2f}% (n={total})")
            return [result]
    
    def compute_decision_distribution(
        self,
        decision_logs: List[UnderwritingDecisionLog],
    ) -> Dict[str, Any]:
        """Compute distribution of URE decisions across all types.
        
        Args:
            decision_logs: Curated decision logs
            
        Returns:
            Dictionary with decision distribution.
        """
        print("[KPIAnalyticsAgent] Computing decision distribution...")
        
        total = len(decision_logs)
        distribution = {
            "Accept": sum(1 for log in decision_logs if log.underwriting_decision_ure == DecisionType.ACCEPT),
            "Load": sum(1 for log in decision_logs if log.underwriting_decision_ure == DecisionType.LOAD),
            "Refer": sum(1 for log in decision_logs if log.underwriting_decision_ure == DecisionType.REFER),
            "Exclusion": sum(1 for log in decision_logs if log.underwriting_decision_ure == DecisionType.EXCLUSION),
        }
        
        result_dict = {
            "kpi_name": "decision_distribution",
            "total_cases": total,
            "distribution": distribution,
            "percentages": {k: (v / total * 100) if total > 0 else 0 for k, v in distribution.items()},
            "sample_size": total,
            "data_version": self.data_version,
        }
        
        print(f"[KPIAnalyticsAgent] ✓ Distribution computed")
        return result_dict
    
    def analyze_age_segments(
        self,
        decision_logs: List[UnderwritingDecisionLog],
    ) -> Dict[str, Any]:
        """Analyze KPIs across age segments.
        
        Args:
            decision_logs: Curated decision logs
            
        Returns:
            Dictionary with age-segmented analysis.
        """
        print("[KPIAnalyticsAgent] Analyzing age segments...")
        
        # Define age bands
        age_bands = {
            "18-30": (18, 30),
            "31-45": (31, 45),
            "46-60": (46, 60),
            "61+": (61, 150),
        }
        
        analysis = {}
        for band_name, (min_age, max_age) in age_bands.items():
            segment_logs = [log for log in decision_logs if min_age <= log.applicant_age <= max_age]
            if not segment_logs:
                continue
            
            total = len(segment_logs)
            approvals = sum(1 for log in segment_logs if log.underwriting_decision_ure == DecisionType.ACCEPT)
            
            analysis[band_name] = {
                "count": total,
                "approval_rate": (approvals / total * 100) if total > 0 else 0,
                "avg_age": statistics.mean([log.applicant_age for log in segment_logs]),
            }
        
        print(f"[KPIAnalyticsAgent] ✓ Age segmentation analyzed: {len(analysis)} bands")
        return {"age_segmentation": analysis, "data_version": self.data_version}
    
    def analyze_condition_segments(
        self,
        decision_logs: List[UnderwritingDecisionLog],
    ) -> Dict[str, Any]:
        """Analyze KPIs across medical condition segments.
        
        Args:
            decision_logs: Curated decision logs
            
        Returns:
            Dictionary with condition-segmented analysis.
        """
        print("[KPIAnalyticsAgent] Analyzing condition segments...")
        
        conditions = defaultdict(list)
        for log in decision_logs:
            conditions[log.condition].append(log)
        
        analysis = {}
        for condition, logs in conditions.items():
            total = len(logs)
            approvals = sum(1 for log in logs if log.underwriting_decision_ure == DecisionType.ACCEPT)
            declines = sum(1 for log in logs if log.underwriting_decision_ure == DecisionType.EXCLUSION)
            
            analysis[condition] = {
                "count": total,
                "approval_rate": (approvals / total * 100) if total > 0 else 0,
                "decline_rate": (declines / total * 100) if total > 0 else 0,
                "avg_age": statistics.mean([log.applicant_age for log in logs]),
            }
        
        print(f"[KPIAnalyticsAgent] ✓ Condition segmentation analyzed: {len(analysis)} conditions")
        return {"condition_segmentation": analysis, "data_version": self.data_version}
    
    def generate_kpi_pack(
        self,
        decision_logs: List[UnderwritingDecisionLog],
    ) -> Dict[str, Any]:
        """Generate comprehensive KPI pack for all metrics.
        
        Args:
            decision_logs: Curated decision logs
            
        Returns:
            Complete KPI pack with metrics, segmentations, and findings.
        """
        print("[KPIAnalyticsAgent] Generating comprehensive KPI pack...")
        
        kpi_pack = {
            "generated_at": "current_timestamp",
            "data_version": self.data_version,
            "dataset_size": len(decision_logs),
            "metrics": {
                "approval_rate": self.compute_approval_rate(decision_logs)[0].to_dict(),
                "decline_rate": self.compute_decline_rate(decision_logs)[0].to_dict(),
                "referral_rate": self.compute_referral_rate(decision_logs)[0].to_dict(),
                "load_rate": self.compute_load_rate(decision_logs)[0].to_dict(),
                "human_ure_alignment": self.compute_human_ure_alignment(decision_logs)[0].to_dict(),
            },
            "distributions": self.compute_decision_distribution(decision_logs),
            "segmentations": {
                "age": self.analyze_age_segments(decision_logs),
                "condition": self.analyze_condition_segments(decision_logs),
            },
        }
        
        print("[KPIAnalyticsAgent] ✓ KPI pack generated")
        return kpi_pack
    
    # Private helper methods
    
    def _compute_segmented_kpi(
        self,
        decision_logs: List[UnderwritingDecisionLog],
        kpi_name: str,
        segment_dimension: str,
        filter_fn,
    ) -> List[KPIResult]:
        """Compute a KPI segmented by a specified dimension.
        
        Args:
            decision_logs: Curated decision logs
            kpi_name: Name of the KPI
            segment_dimension: Field to segment by (e.g., "condition", "income_band")
            filter_fn: Function to filter records that match the KPI
            
        Returns:
            List of KPIResult objects, one per segment.
        """
        segments = defaultdict(list)
        
        # Group by segment dimension
        for log in decision_logs:
            segment_value = getattr(log, segment_dimension, None)
            if segment_value:
                segments[segment_value].append(log)
        
        results = []
        for segment_value, logs in segments.items():
            total = len(logs)
            matching = sum(1 for log in logs if filter_fn(log))
            
            result = KPIResult(
                kpi_name=kpi_name,
                value=(matching / total * 100) if total > 0 else 0,
                numerator=matching,
                denominator=total,
                segment_dimensions={segment_dimension: segment_value},
                sample_size=total,
                data_version=self.data_version,
                calculation_method=f"{kpi_name} for {segment_dimension}={segment_value}",
            )
            
            results.append(result)
        
        return results
