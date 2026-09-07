"""Unit tests for deterministic Fraud War Room capabilities."""

import os
import unittest
from unittest.mock import patch

from coded_tools.fraud_defense.analytics import FraudGraph
from coded_tools.fraud_defense.analytics import TransactionAnalytics
from coded_tools.fraud_defense.generator import generate_environment
from coded_tools.fraud_defense.models import RiskLevel
from coded_tools.fraud_defense.passport import PASSPORT_KEYS
from coded_tools.fraud_defense.passport import build_passport
from coded_tools.fraud_defense.policy import governance_check
from coded_tools.fraud_defense.risk import investigation_plan
from coded_tools.fraud_defense.risk import risk_level
from coded_tools.fraud_defense.router import ModelRouter
from coded_tools.fraud_defense.simulation import DefenseSimulator
from coded_tools.fraud_defense.simulation import default_defenses


class FraudDefenseCoreTest(unittest.TestCase):
    """Verify exact local computation and safety boundaries."""

    @classmethod
    def setUpClass(cls):
        cls.environment = generate_environment(seed=17, case_count=24)
        cls.analytics = TransactionAnalytics(cls.environment)
        cls.graph = FraudGraph(cls.environment)
        cls.simulator = DefenseSimulator(cls.environment, cls.analytics)

    def test_generation_is_reproducible_and_contains_ambiguous_cases(self):
        other = generate_environment(seed=17, case_count=24)
        self.assertEqual(self.environment.cases, other.cases)
        self.assertEqual(self.environment.transactions, other.transactions)
        self.assertTrue(any(not case["ground_truth"]["fraud"] for case in self.environment.cases))
        self.assertTrue(any(case["ground_truth"]["fraud"] for case in self.environment.cases))
        self.assertIn("ground_truth", self.environment.cases[0])
        self.assertNotIn("ground_truth", self.environment.public_case("CASE-0001"))

    def test_transaction_signals_and_flagship_graph(self):
        signals = self.analytics.signals("CASE-0001")
        findings = self.graph.findings("CASE-0001")
        self.assertGreaterEqual(signals["risk_score"], 0.75)
        self.assertTrue(signals["new_beneficiary"])
        self.assertTrue(signals["new_device"])
        self.assertTrue(signals["has_test_then_transfer"])
        self.assertTrue(findings["campaign_signal"])
        self.assertGreaterEqual(len(findings["linked_accounts"]), 2)
        self.assertTrue(any(item.startswith("BEN-MULE") for item in findings["beneficiaries"]))

    def test_risk_tiers_have_distinct_investigation_depth(self):
        self.assertEqual(risk_level(0.1), RiskLevel.LOW)
        self.assertEqual(risk_level(0.4), RiskLevel.MEDIUM)
        self.assertEqual(risk_level(0.6), RiskLevel.HIGH)
        self.assertEqual(risk_level(0.9), RiskLevel.CRITICAL)
        self.assertFalse(investigation_plan(RiskLevel.LOW)["simulation_required"])
        self.assertTrue(investigation_plan(RiskLevel.HIGH)["approval_required"])
        self.assertFalse(investigation_plan(RiskLevel.CRITICAL)["autonomous_execution"])

    def test_simulation_compares_controls_and_runs_bounded_adversarial_loop(self):
        comparisons = self.simulator.compare(default_defenses())
        self.assertEqual(len(comparisons), 3)
        self.assertTrue(all("false_positive_rate" in result and "attack_variants" in result for result in comparisons))
        loop = self.simulator.adversarial_loop(default_defenses()[1], max_iterations=3)
        self.assertLessEqual(loop["iterations_executed"], 3)
        self.assertTrue(loop["rounds"])
        self.assertIn("simulation_after", loop["rounds"][0])

    def test_router_uses_independent_offline_opinions_for_high_risk(self):
        clean_environment = {key: value for key, value in os.environ.items() if not key.startswith("FRAUD_") and key not in {"NVIDIA_API_KEY", "CEREBRAS_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "SARVAM_API_KEY"}}
        with patch.dict(os.environ, clean_environment, clear=True):
            router = ModelRouter(disagreement_threshold=0.01)
            decision = router.assess(self.analytics.signals("CASE-0001"), self.graph.findings("CASE-0001"), RiskLevel.CRITICAL)
        self.assertEqual(len(decision.assessments), 3)
        self.assertEqual(decision.disagreement["independent_opinions"], 3)
        self.assertTrue(decision.disagreement["triggered"])
        self.assertTrue(all(item["source"] == "offline" for item in decision.assessments))

    def test_governance_requires_approval_and_simulation(self):
        result = governance_check(RiskLevel.CRITICAL, [{"control_id": "CTRL-A"}], {"triggered": False}, 5)
        self.assertTrue(result["all_passed"])
        self.assertTrue(result["human_approval_required"])
        self.assertFalse(result["autonomous_execution_allowed"])
        failed = governance_check(RiskLevel.HIGH, [], {"triggered": False}, 2)
        self.assertFalse(failed["all_passed"])

    def test_passport_schema_contains_audit_fields(self):
        passport = build_passport(
            "CASE-0001", RiskLevel.HIGH, {"alert_id": "ALT-1"}, [], {"supporting": [], "counter": [], "missing": []}, {}, {}, {}, {}, [], [], {}, {}, "hold_and_escalate", 0.8, ["sequence"], [], "RECOMMEND", "2026-01-15T14:00:00Z"
        )
        self.assertEqual(set(passport), PASSPORT_KEYS)
        self.assertNotIn("chain_of_thought", passport)
        self.assertEqual(passport["decision_id"], "DEC-0001-001")


if __name__ == "__main__":
    unittest.main()
