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

"""Tests for the Agent Network Consultant response protocol."""

from unittest import TestCase

from neuro_san_studio.agent_network_consultant.consultant_response_protocol import ConsultantResponseProtocol


class TestConsultantResponseProtocol(TestCase):
    """Verify control directives are selected from one response without cross-response state."""

    def test_values_returns_each_matching_directive_payload(self) -> None:
        """Return trimmed payloads while preserving their response order."""
        protocol = ConsultantResponseProtocol(
            "complete\nUNGROUNDED: first criterion\n  UNGROUNDED: second criterion  \n"
        )

        values = protocol.values(ConsultantResponseProtocol.UNGROUNDED_PREFIX)

        self.assertEqual(["first criterion", "second criterion"], values)

    def test_contains_reports_only_present_directives(self) -> None:
        """Distinguish present structural directives from absent tool issues."""
        protocol = ConsultantResponseProtocol("STRUCTURAL_CHANGE_REQUIRED: add a coded tool")

        self.assertTrue(protocol.contains(ConsultantResponseProtocol.STRUCTURAL_CHANGE_PREFIX))
        self.assertFalse(protocol.contains(ConsultantResponseProtocol.TOOL_ISSUE_PREFIX))
