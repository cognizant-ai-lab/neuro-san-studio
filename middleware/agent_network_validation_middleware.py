
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

from abc import abstractmethod
import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware import AgentState
from langchain.agents.middleware import hook_config
from langchain.messages import HumanMessage

from langgraph.runtime import Runtime

from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION


# pylint: disable=too-few-public-methods
class AgentNetworkValidationMiddleware(AgentMiddleware):
    """
    Base middleware for validating an agent network definition after each agent turn.

    Subclasses implement _validate() to run their specific validators and
    provide custom error/log messages via _no_network_error_message(),
    _validation_label(), and _format_error().
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

    @abstractmethod
    def _no_network_error_message(self) -> str:
        """Return the error message when no agent network definition is found."""

    @abstractmethod
    def _validation_label(self) -> str:
        """Return a label for log messages (e.g. 'Structure', 'Instructions')."""

    @abstractmethod
    async def _validate(self, network_def: dict[str, Any]) -> list[str]:
        """
        Run validators against the network definition.

        :param network_def: The agent network definition to validate
        :return: A list of error strings (empty if valid)
        """

    @abstractmethod
    def _format_error(self, error_list: list[str]) -> str:
        """
        Format the list of validation errors into a message string.

        :param error_list: Non-empty list of error strings
        :return: Formatted error message
        """

    @hook_config(can_jump_to=["model"])
    async def aafter_agent(
        self,
        state: AgentState,
        runtime: Runtime
    ) -> dict[str, Any] | None:
        """
        Validate the agent network definition after each agent turn.

        :param state: Current agent state
        :param runtime: Runtime context
        :return: Dict with error message and jump directive, or None if valid
        """
        network_def: dict[str, Any] = self.sly_data.get(AGENT_NETWORK_DEFINITION)
        if not network_def:
            return {
                "messages": [HumanMessage(self._no_network_error_message())],
                "jump_to": "model"
            }

        label: str = self._validation_label()
        self.logger.info(">>>>>>>>>>>>>>>>>>>Validate Agent Network %s>>>>>>>>>>>>>>>>>>", label)

        error_list: list[str] = await self._validate(network_def)

        if error_list:
            content: str = self._format_error(error_list)
            self.logger.error(content)
            return {
                # Use human message to ensure that the model follows the instructions
                "messages": [HumanMessage(content)],
                "jump_to": "model"
            }

        self.logger.info("No %s errors found in the agent network.", label.lower())
        return None
