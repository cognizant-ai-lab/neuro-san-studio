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

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION


class MiddlewareRequestGuard:
    """
    The request-validation policy shared by the middleware_manager coded tools.

    AddMiddleware and RemoveMiddleware receive the same (args, sly_data) shape and
    must refuse the same malformed inputs in the same way, so the shared checks
    live here once. Guards raise ValueError because the framework's
    error_formatter / error_fragments config turns that into an actionable error
    message for the calling LLM.
    """

    @staticmethod
    def validated_target(args: dict[str, Any], sly_data: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
        """
        Validate the parts of an add/remove request that both tools require.

        :param args: The coded tool's args dictionary.
        :param sly_data: The coded tool's sly_data dictionary.
        :return: (network_def, agent_name, middleware_class) — the agent's own
                definition is network_def[agent_name], guaranteed present.
        :raises ValueError: when the network definition is missing from sly_data,
                the agent name is missing or unknown, or middleware_class is
                missing.
        """
        network_def: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        if not network_def:
            raise ValueError("No agent network definition found in sly data.")

        agent_name: str = args.get("agent_name", "")
        if not agent_name:
            raise ValueError("No agent_name provided.")
        if agent_name not in network_def:
            raise ValueError(f"Agent '{agent_name}' not found in the agent network definition.")

        middleware_class: str = args.get("middleware_class", "")
        if not middleware_class:
            raise ValueError("No middleware_class provided.")

        return network_def, agent_name, middleware_class
