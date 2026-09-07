"""Opt-in live Neuro SAN integration checks for the Fraud War Room HOCON."""

import importlib.util
import os
import unittest


NEURO_SAN_AVAILABLE = importlib.util.find_spec("neuro_san") is not None
RUN_LIVE = os.getenv("FRAUD_RUN_NEURO_SAN_TEST", "false").lower() in {"1", "true", "yes"}


@unittest.skipUnless(NEURO_SAN_AVAILABLE and RUN_LIVE, "requires neuro-san and FRAUD_RUN_NEURO_SAN_TEST=true")
class NeuroSanIntegrationTest(unittest.TestCase):
    """Verify a direct Neuro SAN session can load the real network."""

    def test_direct_network_smoke(self):
        from neuro_san.client.direct_agent_session_factory import DirectAgentSessionFactory

        factory = DirectAgentSessionFactory()
        session = factory.create_session(agent_name="industry/fraud_defense", use_direct=True, metadata={})
        messages = list(session.streaming_chat({"user_message": {"text": "Investigate CASE-0001 and return the decision."}, "sly_data": {"fraud_case_id": "CASE-0001"}}))
        self.assertTrue(messages)
        self.assertIn("response", messages[-1])


if __name__ == "__main__":
    unittest.main()
