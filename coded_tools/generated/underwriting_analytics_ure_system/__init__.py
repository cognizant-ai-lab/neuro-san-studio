"""
Grounded implementation of the underwriting_analytics_ure_system network for
Experiment 1 (URE Uplift Agents).

The package reads ONLY the three real source files present in this folder:
  - all_flowcharts.json
  - desicion_question.json
  - question_wording.json

It exposes the Experiment 1 pipeline as NeuroSan CodedTools plus the underlying
pure-Python functions used by run_experiment1.py.
"""

from .data_access import DataAccessTool
from .data_access import FlowMatcher
from .data_access import canonicalize_line_name
from .divergence_miner import DivergenceMinerTool
from .divergence_miner import mine_divergence
from .kpi_metrics import KpiMetricsTool
from .kpi_metrics import compute_kpis
from .pattern_analyser import PatternAnalyserTool
from .pattern_analyser import analyse_patterns
from .rule_engine import RuleEngineTool
from .rule_engine import build_graphs
from .rule_engine import simulate
from .rule_recommender import RuleRecommenderTool
from .rule_recommender import recommend_rules

__version__ = "1.0.0"
__all__ = [
    "DataAccessTool",
    "FlowMatcher",
    "canonicalize_line_name",
    "RuleEngineTool",
    "build_graphs",
    "simulate",
    "DivergenceMinerTool",
    "mine_divergence",
    "PatternAnalyserTool",
    "analyse_patterns",
    "RuleRecommenderTool",
    "recommend_rules",
    "KpiMetricsTool",
    "compute_kpis",
]
