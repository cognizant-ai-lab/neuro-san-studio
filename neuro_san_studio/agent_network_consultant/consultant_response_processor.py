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

"""Process control directives returned by one Agent Network Consultant response."""

import logging

from neuro_san_studio.agent_network_consultant.consultant_response_protocol import ConsultantResponseProtocol
from neuro_san_studio.agent_network_consultant.consultant_run_context import ConsultantRunContext
from neuro_san_studio.agent_network_consultant.consultant_workflow import ConsultantWorkflow
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor

logger = logging.getLogger(__name__)


class ConsultantResponseProcessor:
    """Apply one response's directives to the active Agent Network Consultant run."""

    def __init__(
        self,
        context: ConsultantRunContext,
        workflow: ConsultantWorkflow,
        protocol: ConsultantResponseProtocol,
    ) -> None:
        """
        Store the run collaborators and parsed response.

        :param context: The active Agent Network Consultant run context.
        :param workflow: The workflow that reports issues to nsflow when available.
        :param protocol: The control directives parsed from the response.
        """
        self._context = context
        self._workflow = workflow
        self._protocol = protocol

    def process(self) -> bool:
        """
        Process response directives in their established precedence order.

        :return: Whether the current run must stop.
        """
        if self.requires_structural_review():
            return True
        if self._process_tool_issues():
            return True
        if self._process_ungrounded():
            return True
        self._apply_confident_fixes()
        return False

    def requires_structural_review(self) -> bool:
        """
        Return whether Agent Network Consultant requested an out-of-scope structural change.

        :return: Whether explicit Designer review is required.
        """
        required = self._protocol.contains(ConsultantResponseProtocol.STRUCTURAL_CHANGE_PREFIX)
        if required:
            logger.warning("A structural change requires explicit Designer review. Stopping safely.")
        return required

    def _process_tool_issues(self) -> bool:
        """
        Report coded-tool failures that require human intervention.

        :return: Whether a reported tool issue requires the run to stop.
        """
        tool_issues = self._protocol.values(ConsultantResponseProtocol.TOOL_ISSUE_PREFIX)
        if not tool_issues:
            return False
        safe_tool_issues = self._redact(tool_issues)
        logger.warning(
            "A required coded tool needs a human code fix; stopping the Agent Network Consultant run: %s",
            safe_tool_issues,
        )
        self._workflow.write_tool_issues(safe_tool_issues)
        return True

    def _process_ungrounded(self) -> bool:
        """
        Report criteria that cannot be satisfied from the network's available data.

        :return: Whether the selected ungrounded policy requires the run to stop.
        """
        ungrounded = self._protocol.values(ConsultantResponseProtocol.UNGROUNDED_PREFIX)
        if not ungrounded:
            return False
        safe_ungrounded = self._redact(ungrounded)
        self._workflow.write_ungrounded(safe_ungrounded)
        if self._context.options().ungrounded == "continue":
            logger.info("Ungrounded criteria were reported; continuing under the selected policy: %s", safe_ungrounded)
            return False
        logger.warning(
            "Some criteria require unavailable data; stopping so the data source can be connected: %s",
            safe_ungrounded,
        )
        return True

    def _apply_confident_fixes(self) -> None:
        """Temporarily raise verification ratios for fixes Agent Network Consultant considers stable."""
        confident_fixtures = self._protocol.values(ConsultantResponseProtocol.CONFIDENT_FIX_PREFIX)
        if not confident_fixtures:
            return
        ratio = self._context.options().success_ratio
        self._context.round_state().remember_success_ratio_overrides(confident_fixtures, ratio)
        safe_fixture_names = self._redact(confident_fixtures)
        logger.info(
            "Agent Network Consultant is confident in %d fix(es); verifying at %s next round: %s",
            len(confident_fixtures),
            ratio,
            safe_fixture_names,
        )

    @staticmethod
    def _redact(values: list[str]) -> list[str]:
        """
        Redact sensitive data from model-provided directive values.

        :param values: The directive values to redact.
        :return: Redacted copies in their original order.
        """
        safe_values: list[str] = []
        for value in values:
            safe_values.append(SensitiveDataRedactor.redact_text(value))
        return safe_values
