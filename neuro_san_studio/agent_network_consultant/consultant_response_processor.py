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

"""Process control directives returned by the Network Consultant agent."""

import logging

from neuro_san_studio.agent_network_consultant.consultant_cleanup import ConsultantCleanup
from neuro_san_studio.agent_network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.agent_network_consultant.consultant_scoring import ConsultantScoring
from neuro_san_studio.agent_network_consultant.consultant_workflow import ConsultantWorkflow
from neuro_san_studio.agent_network_consultant.fixture_ratio_manager import FixtureRatioManager
from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner

logger = logging.getLogger("network_consultant")


class ConsultantResponseProcessor:
    """Apply terminal directives and confidence metadata from a Consultant response."""

    @staticmethod
    def process(context: ConsultantRunContext, response: str) -> bool:
        """
        Process response directives in their established precedence order.

        :param context: The active Consultant run context.
        :param response: The Consultant response text.
        :return: Whether the current run must stop.
        """
        if ConsultantResponseProcessor.requires_structural_review(response):
            return True
        if ConsultantResponseProcessor.process_tool_issues(response):
            return True
        if ConsultantResponseProcessor.process_ungrounded(context, response):
            return True
        ConsultantResponseProcessor.apply_confident_fixes(context, response)
        return False

    @staticmethod
    def requires_structural_review(response: str) -> bool:
        """
        Return whether the Consultant requested an out-of-scope structural change.

        :param response: The Consultant response text.
        :return: Whether explicit Designer review is required.
        """
        required = False
        for line in response.splitlines():
            if line.strip().startswith(ConsultantWorkflow.structural_change_prefix()):
                required = True
                break
        if required:
            logger.warning("A structural change requires explicit Designer review. Stopping safely.")
        return required

    @staticmethod
    def process_tool_issues(response: str) -> bool:
        """
        Report coded-tool failures that require human intervention.

        :param response: The Consultant response text.
        :return: Whether a reported tool issue requires the run to stop.
        """
        tool_issues = ConsultantScoring.extract_prefixed(response, ConsultantWorkflow.tool_issue_prefix())
        if not tool_issues:
            return False
        logger.warning(
            "A required coded tool is broken -- this needs a human code fix, not "
            "an instructions/fixture change. Stopping so you can fix it and re-run:"
        )
        for issue in tool_issues:
            logger.warning("  ! %s", issue)
        logger.warning("Tool issue(s) reported; stopping for a human fix: %s", tool_issues)
        ConsultantWorkflow.write_tool_issues(tool_issues)
        return True

    @staticmethod
    def process_ungrounded(context: ConsultantRunContext, response: str) -> bool:
        """
        Report criteria that cannot be satisfied from the network's available data.

        :param context: The active Consultant run context.
        :param response: The Consultant response text.
        :return: Whether the selected ungrounded policy requires the run to stop.
        """
        ungrounded = ConsultantScoring.extract_prefixed(response, ConsultantWorkflow.ungrounded_prefix())
        if not ungrounded:
            return False
        logger.warning("Some criteria ask for facts no tool in this network can supply:")
        for entry in ungrounded:
            logger.warning("  ? %s", entry)
        logger.warning("Ungrounded criteria reported: %s", ungrounded)
        ConsultantWorkflow.write_ungrounded(ungrounded)
        if not context.options().stops_for_ungrounded():
            return False
        logger.warning(
            "Stopping -- wire up the data source, or re-run with "
            "--ungrounded continue to drop those criteria and keep improving the rest."
        )
        return True

    @staticmethod
    def apply_confident_fixes(context: ConsultantRunContext, response: str) -> None:
        """
        Temporarily raise verification ratios for fixes the Consultant considers stable.

        :param context: The active Consultant run context.
        :param response: The Consultant response text.
        """
        confident_fixtures = ConsultantScoring.extract_prefixed(response, ConsultantWorkflow.confident_fix_prefix())
        if not confident_fixtures:
            return
        originals = FixtureRatioManager.set_for_fixtures(
            FixtureRunner.fixture_paths(context.target().network_name()),
            confident_fixtures,
            context.options().selected_success_ratio(),
        )
        context.resources().remember_original_ratios(originals)
        ConsultantCleanup.remember_ratios(originals)
        logger.info(
            "consultant is confident in %d fix(es); bumped to %s for next round: %s",
            len(confident_fixtures),
            context.options().selected_success_ratio(),
            confident_fixtures,
        )
