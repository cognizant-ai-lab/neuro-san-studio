"""Fraud War Room domain package.

The package is deliberately dependency-light. Neuro SAN adapters live in
``neuro_tools`` while the synthetic environment and decision loop remain
usable in offline tests and the local command-center demo.
"""

from coded_tools.fraud_defense.generator import generate_environment
from coded_tools.fraud_defense.orchestration import FraudDefenseEngine

__all__ = ["FraudDefenseEngine", "generate_environment"]
