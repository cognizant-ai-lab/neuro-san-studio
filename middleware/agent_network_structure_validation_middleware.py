
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

from neuro_san.internals.validation.network.structure_network_validator import StructureNetworkValidator
from neuro_san.internals.validation.network.toolbox_network_validator import ToolboxNetworkValidator
from neuro_san.internals.validation.network.url_network_validator import UrlNetworkValidator

from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_editor.get_toolbox import GetToolbox

from middleware.agent_network_validation_middleware import AgentNetworkValidationMiddleware


# pylint: disable=too-few-public-methods
class AgentNetworkStructureValidationMiddleware(AgentNetworkValidationMiddleware):
    """
    Middleware that validates an agent network definition after each agent turn.

    Runs structural, toolbox, and URL validators against the current network
    definition stored in sly_data. If validation errors are found, a human
    message containing the errors is injected and control jumps back to the
    model so it can self-correct.
    """

    def _no_network_error_message(self) -> str:
        return (
            "Error: No agent network found. "
            "Please create a new agent network using `create_new_network` tool"
        )

    def _validation_label(self) -> str:
        return "Structure"

    async def _validate(self, network_def: dict[str, Any]) -> list[str]:
        # Get a dict of tools or error message if no toolbox found
        tools: dict[str, Any] | str = await GetToolbox().async_invoke(None, self.sly_data)

        # Collect subnetwork names and MCP server URLs for URL validation
        subnetwork_result: dict[str, Any] | str = await GetSubnetwork().async_invoke(None, self.sly_data)
        subnetwork_names: list[str] = []
        if isinstance(subnetwork_result, dict):
            subnetwork_names = list(subnetwork_result.keys())
        mcp_servers: list[str] = await GetMcpTool().get_mcp_servers(self.sly_data)

        return (
            StructureNetworkValidator().validate(network_def)
            + ToolboxNetworkValidator(tools).validate(network_def)
            + UrlNetworkValidator(subnetwork_names, mcp_servers).validate(network_def)
        )

    def _format_error(self, error_list: list[str]) -> str:
        formatted_errors = "\n".join(f"- {msg}" for msg in error_list)
        return f"Errors detected:\n{formatted_errors}\n\nUse your tools to fix the errors."
