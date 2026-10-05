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

"""Tests for Consultant response control-directive processing."""

from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.consultant_options import ConsultantOptions
from neuro_san_studio.agent_network_consultant.consultant_resources import ConsultantResources
from neuro_san_studio.agent_network_consultant.consultant_response_processor import ConsultantResponseProcessor
from neuro_san_studio.agent_network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.agent_network_consultant.consultant_target import ConsultantTarget
from neuro_san_studio.agent_network_consultant.consultant_workflow import ConsultantWorkflow


class TestConsultantResponseProcessor(TestCase):
    """Verify response directives retain their established behavior and precedence."""

    @staticmethod
    def _context(stops_for_ungrounded: bool = True) -> ConsultantRunContext:
        """
        Build the minimal run-context interface needed by response processing.

        :param stops_for_ungrounded: Whether the options should stop on ungrounded criteria.
        :return: The configured run-context mock.
        """
        context = Mock(spec=ConsultantRunContext)
        options = Mock(spec=ConsultantOptions)
        options.stops_for_ungrounded.return_value = stops_for_ungrounded
        options.selected_success_ratio.return_value = "3/3"
        target = Mock(spec=ConsultantTarget)
        target.network_name.return_value = "example"
        resources = Mock(spec=ConsultantResources)
        context.options.return_value = options
        context.target.return_value = target
        context.resources.return_value = resources
        return context

    def test_structural_review_stops_before_other_directives(self) -> None:
        """Stop immediately when a structural change needs explicit Designer review."""
        response = "STRUCTURAL_CHANGE_REQUIRED: add a coded tool\nTOOL_ISSUE: ignored"

        with patch.object(ConsultantResponseProcessor, "process_tool_issues") as process_tool_issues:
            should_stop = ConsultantResponseProcessor.process(self._context(), response)

        self.assertTrue(should_stop)
        process_tool_issues.assert_not_called()

    def test_tool_issues_are_reported_and_stop_the_run(self) -> None:
        """Persist every reported coded-tool issue and request a safe stop."""
        with patch.object(ConsultantWorkflow, "write_tool_issues") as write_tool_issues:
            should_stop = ConsultantResponseProcessor.process_tool_issues(
                "TOOL_ISSUE: lookup failed\nTOOL_ISSUE: service unavailable"
            )

        self.assertTrue(should_stop)
        write_tool_issues.assert_called_once_with(["lookup failed", "service unavailable"])

    def test_ungrounded_policy_controls_whether_the_run_stops(self) -> None:
        """Report ungrounded criteria under both policies and stop only when requested."""
        response = "UNGROUNDED: employee_policy: missing source"
        with patch.object(ConsultantWorkflow, "write_ungrounded") as write_ungrounded:
            stop_result = ConsultantResponseProcessor.process_ungrounded(self._context(True), response)
            continue_result = ConsultantResponseProcessor.process_ungrounded(self._context(False), response)

        self.assertTrue(stop_result)
        self.assertFalse(continue_result)
        self.assertEqual(2, write_ungrounded.call_count)

    def test_confident_fixes_register_in_memory_ratio_overrides(self) -> None:
        """Apply stricter ratios to subsequent runs without changing fixture files."""
        context = self._context()
        ConsultantResponseProcessor.apply_confident_fixes(context, "CONFIDENT_FIX: one.hocon")

        context.resources().remember_success_ratio_overrides.assert_called_once_with(["one.hocon"], "3/3")
