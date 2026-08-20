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

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import MIDDLEWARE_KEY
from coded_tools.agent_network_editor.progress_handler import ProgressHandler
from coded_tools.middleware_manager.middleware_request_guard import MiddlewareRequestGuard


class AddMiddleware(CodedTool):
    """
    CodedTool implementation which adds a middleware entry to a specified agent
    in the agent network definition stored in sly_data.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "agent_name": the name of the agent to which middleware will be added.
                    "middleware_class": the fully qualified class name of the middleware. Named this
                        way instead of `class` because `class` is a Python reserved word and breaks
                        pydantic tool-arg validation upstream of this method.
                    "args" (optional): key-value arguments to pass to the middleware constructor.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                Keys expected for this implementation are:
                    "agent_network_definition": an outline of an agent network

        :raises ValueError: when the input is malformed, the target agent doesn't exist or
                is a function/toolbox node, or the requested middleware is already present.
                The framework's `error_formatter` / `error_fragments` config catches this and
                surfaces it back to the calling LLM as an actionable error message.
        :return: On success, a text string confirming the middleware was added.
        """
        network_def, agent_name, middleware_class = MiddlewareRequestGuard.validated_target(args, sly_data)

        # Middleware wraps the agent's model call, so it only makes sense on LLM agents
        # (those with an `instructions` field). Function / toolbox nodes have no model call
        # to wrap and the HOCON assembler's toolbox template has no slot for a middleware
        # array — attaching middleware to them would silently disappear on persist.
        agent_def: dict[str, Any] = network_def[agent_name]
        if "instructions" not in agent_def:
            raise ValueError(
                f"Agent '{agent_name}' is a function/toolbox node (no `instructions`) and cannot have middleware."
            )

        middleware_args: dict[str, Any] | None = args.get("args")

        logger = AndLogger(logging.getLogger(self.__class__.__name__))
        logger.info(">>>>>>>>>>>>>>>>>>>Add Middleware>>>>>>>>>>>>>>>>>>")
        logger.info("Agent Name: %s", agent_name)
        logger.info("Middleware Class: %s", middleware_class)

        existing_middleware: list[dict[str, Any]] = agent_def.get(MIDDLEWARE_KEY, [])

        # Check for duplicate
        for entry in existing_middleware:
            if entry.get("class") == middleware_class:
                raise ValueError(f"Middleware '{middleware_class}' is already present on agent '{agent_name}'.")

        new_entry: dict[str, Any] = {"class": middleware_class}
        if middleware_args:
            new_entry["args"] = middleware_args

        existing_middleware.append(new_entry)
        agent_def[MIDDLEWARE_KEY] = existing_middleware
        network_def[agent_name] = agent_def
        sly_data[AGENT_NETWORK_DEFINITION] = network_def

        await ProgressHandler.report_progress(args, sly_data, network_def)

        logger.debug(">>>>>>>>>>>>>>>>>>> DONE %s !!!>>>>>>>>>>>>>>>>>>", self.__class__.__name__)
        return f"Successfully added middleware '{middleware_class}' to agent '{agent_name}'."
