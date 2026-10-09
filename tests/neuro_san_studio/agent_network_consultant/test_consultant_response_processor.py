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

"""Tests for Agent Network Consultant response control-directive processing."""

from unittest import TestCase
from unittest.mock import Mock

from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions
from neuro_san_studio.agent_network_consultant.consultant_response_processor import ConsultantResponseProcessor
from neuro_san_studio.agent_network_consultant.consultant_response_protocol import ConsultantResponseProtocol
from neuro_san_studio.agent_network_consultant.consultant_round_state import ConsultantRoundState
from neuro_san_studio.agent_network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.agent_network_consultant.consultant_workflow import ConsultantWorkflow


class TestConsultantResponseProcessor(TestCase):
    """Verify response directives retain their established behavior and precedence."""

    @staticmethod
    def _processor(
        response: str,
        ungrounded: str = "stop",
    ) -> tuple[ConsultantResponseProcessor, Mock, Mock]:
        """
        Build one response processor and its observable collaborators.

        :param response: The Agent Network Consultant response text.
        :param ungrounded: The selected ungrounded-criteria policy.
        :return: The processor, workflow mock, and round-state mock.
        """
        context = Mock(spec=ConsultantRunContext)
        context.options.return_value = ConsultantOptions(ungrounded=ungrounded)
        round_state = Mock(spec=ConsultantRoundState)
        context.round_state.return_value = round_state
        workflow = Mock(spec=ConsultantWorkflow)
        protocol = ConsultantResponseProtocol(response)
        return ConsultantResponseProcessor(context, workflow, protocol), workflow, round_state

    def test_structural_review_stops_before_other_directives(self) -> None:
        """Stop immediately when a structural change needs explicit Designer review."""
        processor, workflow, round_state = self._processor(
            "STRUCTURAL_CHANGE_REQUIRED: add a coded tool\nTOOL_ISSUE: ignored\nCONFIDENT_FIX: ignored.hocon"
        )

        should_stop = processor.process()

        self.assertTrue(should_stop)
        workflow.write_tool_issues.assert_not_called()
        round_state.remember_success_ratio_overrides.assert_not_called()

    def test_tool_issues_are_redacted_reported_once_and_stop_the_run(self) -> None:
        """Redact and persist all coded-tool issues while emitting one actionable warning."""
        secret = "customer-secret-123"
        processor, workflow, _ = self._processor(f"TOOL_ISSUE: api_key={secret}\nTOOL_ISSUE: service unavailable")

        with self.assertLogs(ConsultantResponseProcessor.__module__, level="WARNING") as captured:
            should_stop = processor.process()

        self.assertTrue(should_stop)
        persisted_issues = workflow.write_tool_issues.call_args.args[0]
        self.assertNotIn(secret, str(persisted_issues))
        self.assertNotIn(secret, "\n".join(captured.output))
        self.assertIn("[REDACTED]", str(persisted_issues))
        self.assertEqual("service unavailable", persisted_issues[1])
        self.assertEqual(1, len(captured.output))

    def test_ungrounded_policy_controls_whether_the_run_stops(self) -> None:
        """Persist redacted ungrounded criteria and stop only under the selected stop policy."""
        secret = "customer-secret-123"
        response = f"UNGROUNDED: employee_policy: api_key={secret}"
        stop_processor, stop_workflow, _ = self._processor(response)
        continue_processor, continue_workflow, _ = self._processor(response, "continue")

        with self.assertLogs(ConsultantResponseProcessor.__module__, level="INFO") as captured:
            stop_result = stop_processor.process()
            continue_result = continue_processor.process()

        self.assertTrue(stop_result)
        self.assertFalse(continue_result)
        self.assertNotIn(secret, str(stop_workflow.write_ungrounded.call_args))
        self.assertNotIn(secret, str(continue_workflow.write_ungrounded.call_args))
        self.assertNotIn(secret, "\n".join(captured.output))

    def test_confident_fixes_register_in_memory_ratio_overrides(self) -> None:
        """Apply stricter ratios while redacting model-derived fixture names in logs."""
        secret_fixture = "api_key=customer-secret-123"
        processor, _, round_state = self._processor(f"CONFIDENT_FIX: {secret_fixture}")

        with self.assertLogs(ConsultantResponseProcessor.__module__, level="INFO") as captured:
            should_stop = processor.process()

        self.assertFalse(should_stop)
        round_state.remember_success_ratio_overrides.assert_called_once_with([secret_fixture], "3/3")
        self.assertNotIn("customer-secret-123", "\n".join(captured.output))
        self.assertIn("[REDACTED]", "\n".join(captured.output))
