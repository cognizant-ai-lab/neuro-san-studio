# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

"""Tests for direct Agent Network Consultant sessions."""

import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession


class TestConsultantSession(TestCase):
    """Verify that Agent Network Consultant sessions always run in the current process."""

    @patch.dict(os.environ, {"USER": "consultant-user"})
    @patch("neuro_san_studio.agent_network_consultant.consultant_session.AgentSessionFactory")
    def test_constructor_uses_direct_connection(self, agent_session_factory: Mock) -> None:
        """
        Create the requested agent session in-process, including external agents.

        :param agent_session_factory: The patched Neuro SAN session factory class.
        """
        expected_session = object()
        factory = agent_session_factory.return_value
        factory.create_session.return_value = expected_session

        session = ConsultantSession("agent_network_consultant")

        self.assertIsNotNone(session)
        self.assertTrue(session.run_identifier())
        factory.create_session.assert_called_once_with(
            session_type="direct",
            agent_name="agent_network_consultant",
            use_direct=True,
            metadata={"user_id": "consultant-user"},
        )

    @patch.dict(os.environ, {}, clear=True)
    @patch("neuro_san_studio.agent_network_consultant.consultant_session.AgentSessionFactory")
    def test_constructor_uses_agent_network_consultant_as_the_fallback_user(
        self,
        agent_session_factory: Mock,
    ) -> None:
        """
        Identify a direct session consistently when the operating-system user is unavailable.

        :param agent_session_factory: The patched Neuro SAN session factory class.
        """
        agent_session_factory.return_value.create_session.return_value = object()

        ConsultantSession("agent_network_consultant")

        agent_session_factory.return_value.create_session.assert_called_once_with(
            session_type="direct",
            agent_name="agent_network_consultant",
            use_direct=True,
            metadata={"user_id": "agent_network_consultant"},
        )

    @patch("neuro_san_studio.agent_network_consultant.consultant_session.StreamingInputProcessor")
    @patch("neuro_san_studio.agent_network_consultant.consultant_session.AgentSessionFactory")
    def test_chat_reports_a_redacted_framework_error_without_exposing_details(
        self,
        agent_session_factory: Mock,
        streaming_input_processor: Mock,
    ) -> None:
        """
        Report actionable framework context while redacting credentials and omitting private details.

        :param agent_session_factory: The patched Neuro SAN session factory class.
        :param streaming_input_processor: The patched streaming processor class.
        """
        agent_session_factory.return_value.create_session.return_value = object()
        secret_error = "api_key=customer-secret-123"
        secret_tool = "token=tool-secret-456"
        secret_details = "Authorization: Bearer customer-private-token"
        streaming_input_processor.return_value.process_once.return_value = {
            "last_chat_response": (
                f'```json\n{{"error": "{secret_error}", "tool": "{secret_tool}", "details": "{secret_details}"}}\n```'
            ),
            "sly_data": {},
        }
        session = ConsultantSession("agent_network_consultant")

        with (
            self.assertLogs(
                "neuro_san_studio.agent_network_consultant.consultant_session",
                level="ERROR",
            ) as captured,
            self.assertRaises(RuntimeError) as raised,
        ):
            session.chat("Fix the network")

        public_output = f"{raised.exception}\n{' '.join(captured.output)}"
        self.assertIn("Neuro SAN returned an error response", public_output)
        self.assertIn("tool=token=[REDACTED]", public_output)
        self.assertIn("error=api_key=[REDACTED]", public_output)
        self.assertNotIn(secret_error, public_output)
        self.assertNotIn(secret_tool, public_output)
        self.assertNotIn(secret_details, public_output)

    @patch("neuro_san_studio.agent_network_consultant.consultant_session.StreamingInputProcessor")
    @patch("neuro_san_studio.agent_network_consultant.consultant_session.AgentSessionFactory")
    def test_chat_preserves_diagnostic_prose_that_quotes_an_error_object(
        self,
        agent_session_factory: Mock,
        streaming_input_processor: Mock,
    ) -> None:
        """
        Treat an embedded example as ordinary diagnostic text rather than a framework failure envelope.

        :param agent_session_factory: The patched Neuro SAN session factory class.
        :param streaming_input_processor: The patched streaming processor class.
        """
        agent_session_factory.return_value.create_session.return_value = object()
        diagnostic_response = 'The tool returned this payload: {"error": "bad input", "tool": "lookup"}.'
        streaming_input_processor.return_value.process_once.return_value = {
            "last_chat_response": diagnostic_response,
            "sly_data": {},
        }
        session = ConsultantSession("agent_network_consultant")

        self.assertEqual(diagnostic_response, session.chat("Diagnose the failure"))

    @patch("neuro_san_studio.agent_network_consultant.consultant_session.StreamingInputProcessor")
    @patch("neuro_san_studio.agent_network_consultant.consultant_session.AgentSessionFactory")
    def test_chat_rejects_a_non_text_response(
        self,
        agent_session_factory: Mock,
        streaming_input_processor: Mock,
    ) -> None:
        """
        Fail clearly when the session violates its text-response contract.

        :param agent_session_factory: The patched Neuro SAN session factory class.
        :param streaming_input_processor: The patched streaming processor class.
        """
        agent_session_factory.return_value.create_session.return_value = object()
        streaming_input_processor.return_value.process_once.return_value = {
            "last_chat_response": None,
            "sly_data": {},
        }
        session = ConsultantSession("agent_network_consultant")

        with self.assertRaisesRegex(TypeError, "non-text response"):
            session.chat("Fix the network")

    @patch("neuro_san_studio.agent_network_consultant.consultant_session.StreamingInputProcessor")
    @patch("neuro_san_studio.agent_network_consultant.consultant_session.AgentSessionFactory")
    def test_chat_retains_updated_thread(
        self,
        agent_session_factory: Mock,
        streaming_input_processor: Mock,
    ) -> None:
        """
        Keep the updated conversation thread inside the session for subsequent turns.

        :param agent_session_factory: The patched Neuro SAN session factory class.
        :param streaming_input_processor: The patched streaming processor class.
        """
        agent_session_factory.return_value.create_session.return_value = object()
        streaming_input_processor.return_value.process_once.return_value = {
            "last_chat_response": "created",
            "sly_data": {"agent_network_name": "generated_network"},
        }
        with tempfile.TemporaryDirectory() as thinking_directory:
            session = ConsultantSession("agent_network_designer", thinking_directory)

            response = session.chat("Create a network")

            expected_session_directory = Path(thinking_directory) / "agent_network_designer"
            streaming_input_processor.assert_called_once_with(
                "DEFAULT",
                str(expected_session_directory / "thinking.txt"),
                agent_session_factory.return_value.create_session.return_value,
                str(expected_session_directory / "agents"),
            )
            self.assertTrue((expected_session_directory / "agents").is_dir())

        self.assertEqual(response, "created")
        self.assertEqual(session.sly_data_value("agent_network_name"), "generated_network")
        self.assertTrue(session.run_identifier())
        self.assertFalse(Path(thinking_directory).exists())
