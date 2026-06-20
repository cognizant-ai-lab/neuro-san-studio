from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class UnderwritingRule:
    rule_id: str
    rule_name: str
    condition: str
    criteria: str
    decision: str
    load_percentage: Optional[int]
    exclusion_terms: Optional[List[str]]
    description: str


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    attributes: Dict[str, Any]


@dataclass(frozen=True)
class HistoricalDecision:
    case_id: str
    underwriting_decision_human: str
    decision_reason_human: str
    applied_rule_ids: List[str]


@dataclass(frozen=True)
class RuleMapping:
    case_id: str
    applicable_rule_ids: List[str]
    matched_criteria: List[str]
    unmatched_criteria: List[str]


@dataclass(frozen=True)
class ExpectedDecision:
    case_id: str
    ai_decision: str
    rules_used: List[str]
    reasoning_steps: List[str]
    confidence_score: str


@dataclass(frozen=True)
class ExplainabilityLog:
    case_id: str
    input_attributes: Dict[str, Any]
    rules_triggered: List[str]
    decision_path: List[str]
    final_decision: str
    explanation_summary: str
