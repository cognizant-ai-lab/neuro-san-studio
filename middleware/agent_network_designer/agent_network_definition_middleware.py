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

import json
import logging
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import override

from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import ContextT
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ResponseT
from langchain_core.messages import BaseMessage
from langchain_core.messages import SystemMessage

from coded_tools.agent_network_editor.connectivity_dictionary_converter import ConnectivityDictionaryConverter
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION


class AgentNetworkDefinitionMiddleware(AgentMiddleware):
    """
    Middleware that reads the agent network definition from sly_data and injects it
    into the system prompt before each model call.

    This allows the LLM to reason about the current agent network structure without
    requiring it to be passed explicitly through the chat stream.
    """

    def __init__(self, sly_data: dict[str, Any]) -> None:
        """
        Initialize agent network definition middleware.

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
        self.sly_data = sly_data
        self.logger = logging.getLogger(self.__class__.__name__)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """
        Inject the agent network definition from sly_data into the system prompt
        before each model call.

        :param request: Model request containing messages and state
        :param handler: Handler to execute the model call
        :return: Model response from handler
        """
        network_def: dict[str, Any] | list[dict[str, Any]] | None = self.sly_data.get(AGENT_NETWORK_DEFINITION)

        if network_def:
            if isinstance(network_def, list):
                connectivity_dict_converter = ConnectivityDictionaryConverter()
                network_def = connectivity_dict_converter.to_dict(network_def)

            self.logger.debug(
                ">>>>>>>>>>>>>>>>>>>Injecting Agent Network Definition into System Prompt>>>>>>>>>>>>>>>>>>>"
            )
            definition_prompt: str = self.format_definition_prompt(network_def)

            system_message: BaseMessage | None = request.system_message
            if system_message is not None:
                original_content: str = system_message.content if isinstance(system_message.content, str) else ""
                system_message = SystemMessage(content=f"{original_content}\n\n{definition_prompt}")
            else:
                system_message = SystemMessage(content=definition_prompt)

            return await handler(request.override(system_message=system_message))

        return await handler(request)

    def format_definition_prompt(self, network_def: dict[str, Any]) -> str:
        """
        Format the agent network definition as a system prompt section.

        :param network_def: The agent network definition dictionary
        :return: Formatted prompt string
        """
        definition_str: str = json.dumps(network_def, indent=2)
        return f"## Current Agent Network Definition\n\n```json\n{definition_str}\n```"
