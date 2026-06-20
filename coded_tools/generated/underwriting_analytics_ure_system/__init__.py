"""
Grounded implementation of underwriting analytics agentic network.
This module provides Python classes that ground the HOCON-defined agentic network
in the actual JSON datasets available in this folder.
"""

from .data_loader import DataLoader
from .ingestion_agent import IngestionAgent
from .kpi_analytics_agent import KPIAnalyticsAgent
from .rules_diagnostics_agent import RulesDiagnosticsAgent
from .experiment_design_agent import ExperimentDesignAgent
from .monitoring_agent import MonitoringAgent
from .governance_agent import GovernanceAgent
from .orchestrator_agent import OrchestratorAgent

__version__ = "0.1.0"
__all__ = [
    "DataLoader",
    "IngestionAgent",
    "KPIAnalyticsAgent",
    "RulesDiagnosticsAgent",
    "ExperimentDesignAgent",
    "MonitoringAgent",
    "GovernanceAgent",
    "OrchestratorAgent",
]
