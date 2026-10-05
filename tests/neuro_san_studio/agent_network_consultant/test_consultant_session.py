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

"""Tests for direct Network Consultant sessions."""

import os
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.consultant_session import ConsultantSession


class TestConsultantSession(TestCase):
    """Verify that Consultant agents always run in the current process."""

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
        factory.create_session.assert_called_once_with(
            session_type="direct",
            agent_name="agent_network_consultant",
            use_direct=True,
            metadata={"user_id": "consultant-user"},
        )

    def test_unwrap_json_error_returns_text_from_the_error_envelope(self) -> None:
        """Return error-envelope content when the value exposes the text interface."""
        response = '{"error": "TOOL_ISSUE: retry", "tool": "consultant"}'

        unwrapped = ConsultantSession.unwrap_json_error(response)

        self.assertEqual(unwrapped, "TOOL_ISSUE: retry")

    def test_unwrap_json_error_preserves_an_envelope_with_a_non_text_error(self) -> None:
        """Preserve the original response when its error value is not textual."""
        response = '{"error": 42, "tool": "consultant"}'

        unwrapped = ConsultantSession.unwrap_json_error(response)

        self.assertEqual(unwrapped, response)

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
        session = ConsultantSession("agent_network_designer")

        response = session.chat("Create a network")

        self.assertEqual(response, "created")
        self.assertEqual(session.sly_data_value("agent_network_name"), "generated_network")
