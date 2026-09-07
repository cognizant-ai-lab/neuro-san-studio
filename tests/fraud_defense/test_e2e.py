"""Deterministic end-to-end Fraud War Room test."""

import json
import tempfile
import unittest
from pathlib import Path

from coded_tools.fraud_defense.orchestration import FraudDefenseEngine


class FraudDefenseE2ETest(unittest.TestCase):
    """Exercise alert through learning without external APIs."""

    def test_flagship_closed_loop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = FraudDefenseEngine(case_count=24, artifact_dir=temp_dir)
            investigation = engine.investigate("CASE-0001")
            self.assertEqual(investigation["risk_level"], "CRITICAL")
            self.assertEqual(len(investigation["defense_candidates"]), 3)
            self.assertTrue(investigation["attacker_analysis"]["rounds"])
            self.assertTrue(investigation["governance"]["human_approval_required"])
            payload = json.dumps(investigation)
            self.assertNotIn('"ground_truth"', payload)
            approved = engine.approve("CASE-0001", True)
            self.assertEqual(approved["deployment"]["lifecycle"], "SHADOW")
            self.assertTrue(approved["learning"].get("prediction_error"))
            observed = engine.advance_shadow("CASE-0001")
            self.assertEqual(observed["deployment"]["variant_status"], "BYPASS_DETECTED")
            self.assertIn("velocity_30m>=2", observed["deployment"]["revised_defense"]["conditions"])
            self.assertGreaterEqual(len(observed["decision_passport"]["audit_events"]), 10)
            self.assertTrue(Path(temp_dir, "fraud_learning.sqlite3").exists())

    def test_investigator_can_request_more_evidence(self):
        engine = FraudDefenseEngine(case_count=12)
        result = engine.request_more_investigation("CASE-0001")
        self.assertEqual(result["decision"], "request_more_investigation")
        self.assertTrue(result["governance"]["human_approval_required"])
        self.assertTrue(result["decision_passport"]["missing_evidence"])
        self.assertEqual(result["deployment"]["lifecycle"], "RECOMMEND")


if __name__ == "__main__":
    unittest.main()
