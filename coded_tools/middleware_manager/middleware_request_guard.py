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
from coded_tools.agent_network_editor.constants import MIDDLEWARE_KEY


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
        :raises ValueError: when the network definition is missing from sly_data
                or not a dictionary, the agent name is missing, non-string, or
                unknown, the agent's own definition is not a dictionary, or
                middleware_class is missing or non-string.
        """
        # Type checks before use: a non-string agent_name would raise TypeError
        # on the `in` membership test below (lists are unhashable), escaping the
        # ValueError contract the error_formatter relies on.
        network_def: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        if not isinstance(network_def, dict) or not network_def:
            raise ValueError("No agent network definition found in sly data.")

        agent_name: Any = args.get("agent_name", "")
        if not isinstance(agent_name, str):
            raise ValueError(f"Error: agent_name must be a string, got {type(agent_name).__name__}.")
        if not agent_name:
            raise ValueError("No agent_name provided.")
        if agent_name not in network_def:
            raise ValueError(f"Agent '{agent_name}' not found in the agent network definition.")
        if not isinstance(network_def[agent_name], dict):
            raise ValueError(
                f"Error: the definition of agent '{agent_name}' must be a dictionary, "
                f"got {type(network_def[agent_name]).__name__}."
            )

        middleware_class: Any = args.get("middleware_class", "")
        if not isinstance(middleware_class, str):
            raise ValueError(f"Error: middleware_class must be a string, got {type(middleware_class).__name__}.")
        # strip(): the persistence layer refuses to preserve a whitespace-only
        # class, so the tool must not create an entry a round trip would drop.
        if not middleware_class.strip():
            raise ValueError("No middleware_class provided.")

        return network_def, agent_name, middleware_class

    @staticmethod
    def validated_middleware_list(agent_def: dict[str, Any], agent_name: str) -> list[dict[str, Any]]:
        """
        Validate and return an agent's existing middleware list.

        Both tools iterate the list calling entry.get("class"), so a malformed
        block (a string, a dict, or non-dict entries) would raise TypeError /
        AttributeError there and escape the ValueError contract.

        :param agent_def: The agent's own definition (network_def[agent_name]).
        :param agent_name: The agent's name, for the error message.
        :return: The agent's middleware list ([] when absent or None).
        :raises ValueError: when a middleware block is present but is not a
                list of dictionaries.
        """
        # Explicit None check, not `or []`: a present-but-falsy block ({} or "")
        # is malformed and must raise below, not be silently treated as empty.
        existing_middleware: Any = agent_def.get(MIDDLEWARE_KEY)
        if existing_middleware is None:
            existing_middleware = []
        if not isinstance(existing_middleware, list) or not all(
            isinstance(entry, dict) for entry in existing_middleware
        ):
            raise ValueError(
                f"Error: agent '{agent_name}' has a malformed middleware block — expected a list of dictionaries."
            )
        return existing_middleware
