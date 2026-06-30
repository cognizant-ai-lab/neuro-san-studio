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

import logging
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.progress_handler import ProgressHandler

MIDDLEWARE_KEY: str = "middleware"


class RemoveMiddleware(CodedTool):
    """
    CodedTool implementation which removes a middleware entry from a specified agent
    in the agent network definition stored in sly_data.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "agent_name": the name of the agent from which middleware will be removed.
                    "class": the fully qualified class name of the middleware to remove.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    "agent_network_definition": an outline of an agent network

        :raises ValueError: when the input is malformed, the target agent doesn't exist, or
                the requested middleware is not present on the agent. The framework's
                `error_formatter` / `error_fragments` config catches this and surfaces it
                back to the calling LLM as an actionable error message.
        :return: On success, a text string confirming the middleware was removed.
        """
        network_def: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        if not network_def:
            raise ValueError("No agent network definition found in sly data.")

        agent_name: str = args.get("agent_name", "")
        if not agent_name:
            raise ValueError("No agent_name provided.")
        if agent_name not in network_def:
            raise ValueError(f"Agent '{agent_name}' not found in the agent network definition.")

        middleware_class: str = args.get("class", "")
        if not middleware_class:
            raise ValueError("No middleware class provided.")

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>Remove Middleware>>>>>>>>>>>>>>>>>>")
        logger.info("Agent Name: %s", agent_name)
        logger.info("Middleware Class: %s", middleware_class)

        agent_def: dict[str, Any] = network_def[agent_name]
        existing_middleware: list[dict[str, Any]] = agent_def.get(MIDDLEWARE_KEY, [])

        updated_middleware = [entry for entry in existing_middleware if entry.get("class") != middleware_class]

        if len(updated_middleware) == len(existing_middleware):
            raise ValueError(f"Middleware '{middleware_class}' is not present on agent '{agent_name}'.")

        agent_def[MIDDLEWARE_KEY] = updated_middleware
        network_def[agent_name] = agent_def
        sly_data[AGENT_NETWORK_DEFINITION] = network_def

        await ProgressHandler.report_progress(args, network_def)

        logger.debug(">>>>>>>>>>>>>>>>>>> DONE %s !!!>>>>>>>>>>>>>>>>>>", self.__class__.__name__)
        return f"Successfully removed middleware '{middleware_class}' from agent '{agent_name}'."
