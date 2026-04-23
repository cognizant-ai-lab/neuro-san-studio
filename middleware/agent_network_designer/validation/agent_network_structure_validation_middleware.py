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

from typing import Any

from neuro_san.internals.validation.network.keyword_network_validator import KeywordNetworkValidator
from neuro_san.internals.validation.network.structure_network_validator import StructureNetworkValidator
from neuro_san.internals.validation.network.toolbox_network_validator import ToolboxNetworkValidator
from neuro_san.internals.validation.network.url_network_validator import UrlNetworkValidator

from coded_tools.agent_network_editor.constants import MCP_SERVERS
from coded_tools.agent_network_editor.constants import TOOLBOX_INFO
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from middleware.agent_network_designer.validation.agent_network_validation_middleware import (
    AgentNetworkValidationMiddleware,
)


class AgentNetworkStructureValidationMiddleware(AgentNetworkValidationMiddleware):
    """
    Middleware that validates an agent network definition after each agent turn.

    Runs structural, toolbox, and URL validators against the current network
    definition stored in sly_data. If validation errors are found, a human
    message containing the errors is injected and control jumps back to the
    model so it can self-correct.
    """

    def no_network_error_message(self) -> str:
        """Return the error message when no agent network definition is found."""

        return "Error: No agent network found. Please create a new agent network using `create_new_network` tool"

    def validation_label(self) -> str:
        """Return a label for log messages (e.g. 'Structure', 'Instructions')."""
        return "Structure"

    async def validate(self, network_def: dict[str, Any]) -> list[str]:
        """
        Run validators against the network definition.

        :param network_def: The agent network definition to validate
        :return: A list of error strings (empty if valid)
        """

        # Get infos from sly_data. These should have been put there by the respective tools
        # from the agent network editor.
        subnetwork_names: list[str] = GetSubnetwork.get_subnetwork_names(self.sly_data)
        mcp_servers: list[str] = self.sly_data.get(MCP_SERVERS, [])
        toolbox_tools: dict[str, Any] = self.sly_data.get(TOOLBOX_INFO, {})

        return (
            StructureNetworkValidator().validate(network_def)
            + ToolboxNetworkValidator(toolbox_tools).validate(network_def)
            + UrlNetworkValidator(subnetwork_names, mcp_servers).validate(network_def)
            # Check that "tools" field is a list of str.
            # Note that keywords argument is for check specific keywords.
            # Available keywords are "description", "instructions", and "tools".
            # If keywords is not provided, all keywords will be checked.
            + KeywordNetworkValidator(keywords=["tools"]).validate(network_def)
        )

    def format_error(self, error_list: list[str]) -> str:
        """
        Format the list of validation errors into a message string.

        :param error_list: Non-empty list of error strings
        :return: Formatted error message
        """
        formatted_errors = "\n".join(f"- {msg}" for msg in error_list)
        return f"Errors detected:\n{formatted_errors}\n\nUse your tools to fix the errors."
