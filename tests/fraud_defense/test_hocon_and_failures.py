"""HOCON shape and graceful-failure tests."""

import asyncio
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from coded_tools.fraud_defense.neuro_tools import CycleGate
from coded_tools.fraud_defense.neuro_tools import AnalyzeGraph
from coded_tools.fraud_defense.neuro_tools import AnalyzeTransactions
from coded_tools.fraud_defense.neuro_tools import AssembleEvidence
from coded_tools.fraud_defense.neuro_tools import CheckGovernance
from coded_tools.fraud_defense.neuro_tools import CreateDecisionPassport
from coded_tools.fraud_defense.neuro_tools import GenerateHypotheses
from coded_tools.fraud_defense.neuro_tools import GetCaseContext
from coded_tools.fraud_defense.neuro_tools import ProposeDefenses
from coded_tools.fraud_defense.neuro_tools import RouteModels
from coded_tools.fraud_defense.neuro_tools import SimulateDefenses
from coded_tools.fraud_defense.models import RiskLevel
from coded_tools.fraud_defense.router import ModelRouter


class HoconAndFailureTest(unittest.TestCase):
    """Keep the actual HOCON network visible and failure-safe."""

    def test_hocon_declares_required_agents_and_cycle(self):
        path = Path("registries/industry/fraud_defense.hocon")
        text = path.read_text(encoding="utf-8")
        for name in ("fraud_commander", "transaction_analyst", "attacker_agent", "defender_agent", "counterfactual_simulator", "adversarial_challenger", "model_router", "decision_governor"):
            self.assertIn(f'"name": "{name}"', text)
        self.assertIn('"tools": ["cycle_gate", "attacker_challenge", "defender_agent"', text)
        self.assertIn('"class": "fraud_defense.neuro_tools.CycleGate"', text)
        self.assertIn('"class": "fraud_defense.neuro_tools.AssembleEvidence"', text)

    def test_cycle_gate_is_bounded(self):
        tool = CycleGate()
        sly_data = {}
        first = asyncio.run(tool.async_invoke({"max_iterations": 2}, sly_data))
        second = asyncio.run(tool.async_invoke({"max_iterations": 2}, sly_data))
        third = asyncio.run(tool.async_invoke({"max_iterations": 2}, sly_data))
        self.assertTrue(first["continue"])
        self.assertTrue(second["continue"])
        self.assertFalse(third["continue"])

    def test_missing_case_returns_recoverable_tool_error(self):
        result = asyncio.run(GetCaseContext().async_invoke({"case_id": "CASE-9999"}, {}))
        self.assertTrue(result["recoverable"])
        self.assertIn("Unknown synthetic case", result["error"])

    def test_coded_tools_share_sly_data_without_central_orchestrator(self):
        async def run_sequence():
            sly_data = {}
            tools = [
                GetCaseContext(), AnalyzeTransactions(), AnalyzeGraph(), AssembleEvidence(), GenerateHypotheses(),
                ProposeDefenses(), SimulateDefenses(), RouteModels(), CheckGovernance(), CreateDecisionPassport(),
            ]
            results = []
            for tool in tools:
                results.append(await tool.async_invoke({"case_id": "CASE-0001"}, sly_data))
            return results, sly_data

        results, sly_data = asyncio.run(run_sequence())
        self.assertTrue(all("error" not in result for result in results))
        self.assertIn("transaction_analysis", sly_data["fraud_war_room"])
        self.assertIn("model_routing", sly_data["fraud_war_room"])
        self.assertIn("decision_passport", sly_data)
        self.assertEqual(sly_data["decision_passport"]["case_id"], "CASE-0001")

    def test_provider_failure_falls_back_without_secret_in_result(self):
        with patch.dict(os.environ, {"FRAUD_NVIDIA_MODEL": "test-model", "FRAUD_NVIDIA_BASE_URL": "http://127.0.0.1:1", "NVIDIA_API_KEY": "test-key"}, clear=False):
            router = ModelRouter()
            decision = router.assess({"risk_score": 0.9, "sequence_score": 0.8}, {"component_size": 3, "campaign_signal": True}, RiskLevel.CRITICAL)
        self.assertTrue(decision.assessments)
        self.assertNotIn("test-key", json.dumps(decision.as_dict()))


if __name__ == "__main__":
    unittest.main()
