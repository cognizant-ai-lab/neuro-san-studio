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

"""Consultant-only validation and source-preserving persistence."""

import asyncio
from os import environ
from typing import Any

from langchain.agents.middleware import AgentState
from langchain.agents.middleware import hook_config
from langgraph.runtime import Runtime
from neuro_san.interfaces.reservationist import Reservationist
from neuro_san.internals.validation.network.structure_network_validator import StructureNetworkValidator
from neuro_san.internals.validation.network.toolbox_network_validator import ToolboxNetworkValidator
from neuro_san.internals.validation.network.url_network_validator import UrlNetworkValidator

from coded_tools.agent_network_editor.connectivity_dictionary_converter import ConnectivityDictionaryConverter
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_HOCON_TEXT
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_editor.get_toolbox import GetToolbox
from coded_tools.agent_network_query_generator.set_sample_queries import AGENT_NETWORK_QUERIES
from middleware.agent_network_designer.persistence.agent_network_persistence_middleware import (
    AgentNetworkPersistenceMiddleware,
)
from middleware.agent_network_designer.validation.agent_network_instructions_validation_middleware import (
    AgentNetworkInstructionsValidationMiddleware,
)
from neuro_san_studio.coded_tools.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.middleware.agent_network_consultant.consultant_instruction_changes import (
    ConsultantInstructionChanges,
)
from neuro_san_studio.middleware.agent_network_consultant.source_preserving_hocon_editor import (
    SourcePreservingHoconEditor,
)


class ConsultantPersistenceMiddleware(AgentNetworkPersistenceMiddleware):
    """Validate and patch only the consultant's changed instruction fields."""

    def __init__(
        self,
        reservationist: Reservationist,
        sly_data: dict[str, Any],
        persist_only_when_modified: bool = False,
        preserve_source_hocon: bool = False,
    ) -> None:
        """Configure consultant-only persistence behavior."""
        super().__init__(reservationist, sly_data)
        self.persist_only_when_modified = persist_only_when_modified
        self.preserve_source_hocon = preserve_source_hocon

    @hook_config(can_jump_to=["model"])
    async def aafter_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """Validate and persist source changes after a consultant agent completes."""
        del state, runtime
        network_def: dict[str, Any] = self.sly_data.get(AGENT_NETWORK_DEFINITION)
        agent_network_name: str = self.sly_data.get(AGENT_NETWORK_NAME)
        original_fields: dict[str, dict[str, str]] = self.sly_data.get(
            ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS, {}
        )
        changes: dict[str, dict[str, str]] = ConsultantInstructionChanges.between(original_fields, network_def or {})
        self.sly_data.update({ConsultantState.AGENT_NETWORK_CHANGES: changes})
        if self.persist_only_when_modified and not changes:
            return None
        if not network_def or not isinstance(agent_network_name, str) or not agent_network_name:
            return None

        structure_errors, instructions_errors = await self._validate_network(network_def)
        if structure_errors or instructions_errors:
            self.logger.warning("Validation errors: %s", structure_errors + instructions_errors)
            if self._validation_attempts >= self.max_validation_attempts:
                self.logger.warning(
                    "Reached max validation attempts (%d); ending without persisting.",
                    self.max_validation_attempts,
                )
                return None
            self._validation_attempts += 1
            return self._error_response(self._validation_message(structure_errors, instructions_errors))

        self._validation_attempts = 0
        sample_queries: list[str] = self.sly_data.get(AGENT_NETWORK_QUERIES, [])
        await self._assemble_and_persist(network_def, agent_network_name, sample_queries)

        progress_style = environ.get("AGENT_NETWORK_DESIGNER_PROGRESS_STYLE", "internal")
        if progress_style == "connectivity":
            await ConnectivityDictionaryConverter.get_shared_toolbox_factory()
        self._determine_exported_network_definition(self.sly_data, progress_style)
        self.logger.debug(">>>>>>>>>>>>>>>>>>> DONE %s !!!>>>>>>>>>>>>>>>>>>", self.__class__.__name__)
        return None

    def _validation_message(self, structure_errors: list[str], instructions_errors: list[str]) -> str:
        """Build actionable feedback for network validation failures."""
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

    async def _validate_network(self, network_def: dict[str, Any]) -> tuple[list[str], list[str]]:
        """Return structural and instruction validation failures separately."""
        subnetwork_names = await GetSubnetwork.get_subnetwork_names()
        mcp_servers = await GetMcpTool.get_mcp_servers()
        for url in GetMcpTool.sly_data_http_header_urls(self.sly_data):
            if url not in mcp_servers:
                mcp_servers.append(url)

        toolbox_tools = await GetToolbox.get_toolbox_info()
        diagnostic_context = self.sly_data.get(ConsultantState.AGENT_NETWORK_DIAGNOSTIC_CONTEXT, {})
        coded_tool_names = {
            agent.get("name")
            for agent in diagnostic_context.get("tools", [])
            if isinstance(agent, dict) and agent.get("class") and agent.get("name")
        }
        toolbox_tools = {**toolbox_tools, **{name: {} for name in coded_tool_names}}
        structure_errors = (
            StructureNetworkValidator().validate(network_def)
            + ToolboxNetworkValidator(toolbox_tools).validate(network_def)
            + UrlNetworkValidator(subnetwork_names, mcp_servers).validate(network_def)
        )
        instruction_errors = await AgentNetworkInstructionsValidationMiddleware(self.sly_data).validate(network_def)
        return structure_errors, instruction_errors

    async def _assemble_and_persist(
        self,
        network_def: dict[str, Any],
        agent_network_name: str,
        sample_queries: list[str],
    ) -> str | None:
        """Apply recorded fields to the original HOCON without rebuilding it."""
        del network_def, agent_network_name, sample_queries
        if not self.preserve_source_hocon:
            raise ValueError("Consultant persistence requires preserve_source_hocon=true.")
        source_file: str = self.sly_data.get(ConsultantState.AGENT_NETWORK_SOURCE_FILE, "")
        if not source_file:
            raise ValueError("Cannot preserve source HOCON: no agent_network_source_file is available.")
        changes = self.sly_data.get(ConsultantState.AGENT_NETWORK_CHANGES, {})
        updated_text = await asyncio.to_thread(SourcePreservingHoconEditor.update_file, source_file, changes)
        self.sly_data.update(
            {
                AGENT_NETWORK_HOCON_TEXT: updated_text,
                ConsultantState.AGENT_NETWORK_CHANGES: {},
                ConsultantState.AGENT_NETWORK_EDITABLE_FIELDS: ConsultantInstructionChanges.snapshot(
                    self.sly_data.get(AGENT_NETWORK_DEFINITION, {})
                ),
            }
        )
        self.logger.info("Persisted surgical agent-network changes to %s", source_file)
        return None
