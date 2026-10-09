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

"""Agent Network Consultant validation and source-preserving persistence."""

import asyncio
from collections.abc import Mapping
from numbers import Integral
from os import environ
from typing import Any
from typing import override

from langchain.agents.middleware import AgentState
from langchain.agents.middleware import hook_config
from langgraph.runtime import Runtime
from neuro_san.internals.validation.network.structure_network_validator import StructureNetworkValidator
from neuro_san.internals.validation.network.toolbox_network_validator import ToolboxNetworkValidator
from neuro_san.internals.validation.network.url_network_validator import UrlNetworkValidator
from pyhocon.exceptions import ConfigException
from pyparsing import ParseBaseException

from coded_tools.agent_network_editor.connectivity_dictionary_converter import ConnectivityDictionaryConverter
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_HOCON_TEXT
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_editor.get_toolbox import GetToolbox
from middleware.agent_network_consultant.consultant_instruction_changes import ConsultantInstructionChanges
from middleware.agent_network_consultant.source_preserving_hocon_editor import SourcePreservingHoconEditor
from middleware.agent_network_designer.persistence import agent_network_persistence_middleware
from middleware.agent_network_designer.validation import agent_network_instructions_validation_middleware
from neuro_san_studio.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.agent_network_consultant.consultant_text import ConsultantText


class ConsultantPersistenceMiddleware(agent_network_persistence_middleware.AgentNetworkPersistenceMiddleware):
    """Validate and patch only Agent Network Consultant's changed instruction fields."""

    @override
    @hook_config(can_jump_to=["model"])
    async def aafter_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """
        Validate and persist the Consultant's instruction changes after its turn.

        :param state: The current agent state supplied by the middleware framework.
        :param runtime: The current middleware runtime.
        :return: Model retry feedback when validation fails, otherwise `None`.
        """
        del state, runtime
        persistence_candidate = self._persistence_candidate()
        if persistence_candidate is None:
            return None
        network_definition, network_name, changes = persistence_candidate
        if not changes:
            return None

        structure_errors, instructions_errors = await self._validate_network(network_definition)
        if structure_errors or instructions_errors:
            return self._validation_failure_response(structure_errors, instructions_errors)

        self._validation_attempts = 0
        deploy_error = await self._assemble_and_persist(network_definition, network_name, [])
        await self._export_network_definition()
        if deploy_error is not None:
            return self._deploy_error_response(deploy_error)
        return None

    def _persistence_candidate(
        self,
    ) -> tuple[dict[str, Any], str, dict[str, dict[str, str]]] | None:
        """
        Normalize the required middleware state and calculate editable-field changes.

        :return: The definition, network name, and changes, or `None` when required state is unavailable.
        """
        network_definition_value: Any = self.sly_data.get(AGENT_NETWORK_DEFINITION)
        network_definition: dict[str, Any] = {}
        if isinstance(network_definition_value, Mapping):
            network_definition.update(network_definition_value)
        network_name: str | None = ConsultantText.text_value(self.sly_data.get(AGENT_NETWORK_NAME))
        original_fields: Any = self.sly_data.get(ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS)
        changes: dict[str, dict[str, str]] = {}
        if isinstance(original_fields, Mapping):
            changes = ConsultantInstructionChanges.between(original_fields, network_definition)
        self.sly_data.update({ConsultantState.AGENT_NETWORK_CHANGES: changes})

        missing_state: list[str] = []
        if not network_definition:
            missing_state.append(AGENT_NETWORK_DEFINITION)
        if not network_name:
            missing_state.append(AGENT_NETWORK_NAME)
        if not isinstance(original_fields, Mapping):
            missing_state.append(ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS)
        if missing_state:
            self.logger.error(
                "Cannot persist Agent Network Consultant changes because required middleware state is missing "
                "or invalid: %s",
                ", ".join(missing_state),
            )
            return None
        return network_definition, network_name, changes

    def _validation_failure_response(
        self,
        structure_errors: list[str],
        instructions_errors: list[str],
    ) -> dict[str, Any] | None:
        """
        Return Consultant-specific retry feedback or stop after the retry limit.

        :param structure_errors: The structural validation errors.
        :param instructions_errors: The instruction validation errors.
        :return: Model retry feedback, or `None` when the retry limit has been reached.
        """
        errors: list[str] = structure_errors + instructions_errors
        if self._validation_attempts >= self.max_validation_attempts:
            self.logger.error(
                "Reached max validation attempts (%d); ending without persisting. Errors: %s",
                self.max_validation_attempts,
                errors,
            )
            return None

        self._validation_attempts += 1
        self.logger.info(
            "Validation failed; requesting an Agent Network Consultant repair (attempt %d/%d): %s",
            self._validation_attempts,
            self.max_validation_attempts,
            errors,
        )
        return self._error_response(self._validation_message(structure_errors, instructions_errors))

    def _validation_message(self, structure_errors: list[str], instructions_errors: list[str]) -> str:
        """
        Build actionable feedback for network validation failures.

        :param structure_errors: The structural validation errors.
        :param instructions_errors: The instruction validation errors.
        :return: The resulting text.
        """
        parts: list[str] = []
        if structure_errors:
            parts.append(
                f"The agent network definition has structural issues: {structure_errors}. Do not rewrite "
                "the source automatically; report `STRUCTURAL_CHANGE_REQUIRED` with the reason."
            )
        if instructions_errors:
            parts.append(
                f"The agent network definition has instructions-related issues: {instructions_errors}. "
                "Call `write_all_instructions` to fix these instructions problems."
            )
        if structure_errors and instructions_errors:
            parts.append(
                "Do not persist a partial repair while structural issues remain; report the structural "
                "handoff instead."
            )
        return " ".join(parts)

    @override
    async def _validate_network(self, network_def: dict[str, Any]) -> tuple[list[str], list[str]]:
        """
        Validate the edited network while accepting its existing coded tools.

        :param network_def: The edited agent-network definition.
        :return: Structural and instruction validation errors.
        """
        subnetwork_names: list[str] = await GetSubnetwork.get_subnetwork_names()
        mcp_servers: list[str] = await GetMcpTool.get_mcp_servers()
        for url in GetMcpTool.sly_data_http_header_urls(self.sly_data):
            if url not in mcp_servers:
                mcp_servers.append(url)
        toolbox_tools: dict[str, Any] = await GetToolbox.get_toolbox_info()
        toolbox_tools.update(self._coded_tool_definitions())

        structure_errors: list[str] = (
            StructureNetworkValidator().validate(network_def)
            + ToolboxNetworkValidator(toolbox_tools).validate(network_def)
            + UrlNetworkValidator(subnetwork_names, mcp_servers).validate(network_def)
        )
        instructions_validator = (
            agent_network_instructions_validation_middleware.AgentNetworkInstructionsValidationMiddleware(
                self.sly_data
            )
        )
        instructions_errors: list[str] = await instructions_validator.validate(network_def)
        return structure_errors, instructions_errors

    def _coded_tool_definitions(self) -> dict[str, Any]:
        """
        Return coded tools present in the loaded source as valid local toolbox tools.

        :return: Additional toolbox-tool definitions keyed by tool name.
        """
        diagnostic_context: Any = self.sly_data.get(ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT, {})
        if not isinstance(diagnostic_context, Mapping):
            return {}
        additional_tools: dict[str, Any] = {}
        for agent in diagnostic_context.get("tools", []):
            if not isinstance(agent, Mapping) or not agent.get("class"):
                continue
            agent_name = ConsultantText.text_value(agent.get("name"))
            if agent_name:
                additional_tools.update({agent_name: {}})
        return additional_tools

    async def _export_network_definition(self) -> None:
        """Export the validated definition using the existing client response style."""
        progress_style: str = environ.get("AGENT_NETWORK_DESIGNER_PROGRESS_STYLE", "internal")
        if progress_style == "connectivity":
            await ConnectivityDictionaryConverter.get_shared_toolbox_factory()
        self._determine_exported_network_definition(self.sly_data, progress_style)

    @override
    async def _assemble_and_persist(
        self,
        network_def: dict[str, Any],
        agent_network_name: str,
        sample_queries: list[str],
    ) -> str | None:
        """
        Apply recorded fields to the original HOCON without rebuilding it.

        :param network_def: The resolved agent-network definition.
        :param agent_network_name: The name of the target agent network.
        :param sample_queries: The sample queries accepted by the parent interface.
        :return: The resulting value, or `None` when unavailable.
        :raises ConfigException: If the staged HOCON configuration is invalid.
        :raises OSError: If the source file cannot be read, staged, or replaced.
        :raises ParseBaseException: If the staged HOCON syntax is invalid.
        :raises ValueError: If source-preserving editing cannot apply the requested change.
        """
        # Source-preserving persistence needs the validated definition for its next editable-field snapshot. The
        # Designer-specific name and sample-query inputs do not participate in this persistence strategy.
        del agent_network_name, sample_queries
        source_file: str = self.sly_data.get(ConsultantState.AGENT_NETWORK_SOURCE_FILE, "")
        if not source_file:
            raise ValueError("Cannot preserve source HOCON: no agent_network_source_file is available.")
        changes = self.sly_data.get(ConsultantState.AGENT_NETWORK_CHANGES, {})
        original_fields = self.sly_data.get(ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS)
        if not isinstance(original_fields, Mapping):
            raise ValueError("Cannot preserve source HOCON: no agent_network_editable_fields snapshot is available.")
        try:
            # HOCON parsing and atomic file replacement are blocking file-system operations.
            updated_text = await asyncio.to_thread(
                SourcePreservingHoconEditor.update_file,
                source_file,
                changes,
                original_fields,
            )
        except (ConfigException, ParseBaseException, ValueError) as exc:
            # Only unsupported or malformed HOCON counts as a stuck patch. File-system errors retain their normal
            # exception path and must not be mislabeled as a source-format limitation.
            failure_count_value: Any = self.sly_data.get(
                ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT,
                0,
            )
            # bool is an Integral in Python, but framework flags must never become numeric failure counts.
            if (
                failure_count_value is True
                or failure_count_value is False
                or not isinstance(
                    failure_count_value,
                    Integral,
                )
            ):
                raise TypeError("The persistence failure count must be an integer.") from exc
            failure_count = int(failure_count_value)
            self.sly_data.update({ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT: failure_count + 1})
            raise
        self.sly_data.update(
            {
                AGENT_NETWORK_HOCON_TEXT: updated_text,
                ConsultantState.AGENT_NETWORK_CHANGES: {},
                ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: ConsultantInstructionChanges.snapshot(network_def),
                ConsultantState.AGENT_NETWORK_PERSISTENCE_FAILURE_COUNT: 0,
            }
        )
        self.logger.info("Persisted surgical agent-network changes to %s", source_file)
        return None
