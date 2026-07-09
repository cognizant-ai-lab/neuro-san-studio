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

import re
from typing import Any

from neuro_san.internals.validation.network.tool_name_network_validator import ToolNameNetworkValidator
from neuro_san.internals.validation.network.url_network_validator import UrlNetworkValidator


# pylint: disable=too-few-public-methods
class AgentNameGuard:
    """
    Guard that validates an agent-node name (a key in the agent network definition).

    Two rules are enforced, both about the node *key* — not tool references, which
    legitimately may point at external agents inside a `tools` list:

    1. External agent/subnetwork/MCP references — names starting with "/", "http://",
       or "https://" — are only legal as tool references, never as top-level nodes
       (where they would carry the instructions/description/tools that an external
       agent/subnetwork cannot have). This case is reported with an actionable message.
    2. Any remaining name must match the same pattern the framework enforces on tool
       names (ToolNameNetworkValidator.TOOL_NAME_PATTERN — letters, digits, underscore,
       and hyphen only) so a node name can never become an illegal langchain tool name.

    This shared guard keeps the checks (and their messages) identical across the tools
    that create or edit node keys (create_network, add_agent, update_agent).
    """

    @staticmethod
    def agent_name_error(agent_name: Any) -> str | None:
        """
        Return an error message if `agent_name` is not a valid local agent-node name,
        or None if it is valid.

        :param agent_name: The candidate agent-node name (dict key) to check
        :return: An "Error: ..." string if the name is invalid, else None
        """
        if not isinstance(agent_name, str):
            return f"Error: agent name must be a string, got {type(agent_name).__name__}."

        # Check the more specific external-reference case first so the model gets an
        # actionable message rather than a generic "invalid characters" one.
        if UrlNetworkValidator.is_url_or_path(agent_name):
            return (
                f"Error: '{agent_name}' is an external agent/subnetwork/MCP reference and "
                "cannot be a node in the network. Reference it inside another agent's tools "
                "list instead. External agents/subnetworks cannot have instructions, "
                "description, or tools."
            )

        if not re.match(ToolNameNetworkValidator.TOOL_NAME_PATTERN, agent_name):
            return (
                f"Error: '{agent_name}' is not a valid agent name. Agent names may contain "
                "only letters, digits, underscores, and hyphens "
                f"(must match the regex '{ToolNameNetworkValidator.TOOL_NAME_PATTERN}')."
            )

        return None
