
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

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware import AgentState
from langchain.agents.middleware import hook_config
from langchain.messages import HumanMessage

from langgraph.runtime import Runtime

from neuro_san.internals.validation.network.keyword_network_validator import KeywordNetworkValidator

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION


# pylint: disable=too-few-public-methods
class AgentNetworkInstructionsValidationMiddleware(AgentMiddleware):
    """
    Middleware that validates agent instructions after each agent turn.

    Runs keyword validation against the current network definition stored
    in sly_data to detect missing or incomplete agent instructions.
    If validation errors are found, an AI message containing the errors
    is injected and control jumps back to the model so it can self-correct.
    """

    def __init__(
            self,
            sly_data: dict[str, Any]
    ) -> None:
        """
        Initialize agent network validation middleware.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    "agent_network_definition": an outline of an agent network
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sly_data = sly_data

    @hook_config(can_jump_to=["model"])
    async def aafter_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """
        Validate agent instructions in the network definition after each agent turn.

        Runs keyword validation to detect missing or incomplete instructions.
        If any errors are found, returns an AI message with the errors and
        jumps back to the model.

        :param state: Current agent state
        :param runtime: Runtime context
        :return: Dict with error message and jump directive, or None if valid
        """
        network_def: dict[str, Any] = self.sly_data.get(AGENT_NETWORK_DEFINITION)
        if not network_def:
            content: str = (
                "Error: No agent network found. Cannot edit or create instructions."
            )
            return {
                # Use human message to ensure that the model follows the instructions
                "messages": [HumanMessage(content)],
                "jump_to": "model"
            }

        self.logger.info(">>>>>>>>>>>>>>>>>>>Validate Agent Network Instructions>>>>>>>>>>>>>>>>>>")

        validator = KeywordNetworkValidator()
        error_list: list[str] = validator.validate(network_def)

        if error_list:
            content: str = f"Error: {error_list}"
            self.logger.error(content)
            return {
                # Use human message to ensure that the model follows the instructions
                "messages": [HumanMessage(content)],
                "jump_to": "model"
            }

        self.logger.info("No missing instructions in the agent network.")
        return None
