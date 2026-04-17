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
import re
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
from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer

from coded_tools.agent_network_editor.connectivity_dictionary_converter import ConnectivityDictionaryConverter
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock

AGENT_NETWORK_HOCON_FILE: str = "agent_network_hocon_file"


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

        # First, check to see if there is a generated agent network definition
        network_def: dict[str, Any] | list[dict[str, Any]] | None = self.sly_data.get(AGENT_NETWORK_DEFINITION)
        if network_def:
            self.logger.debug(">>>>>>>>>>>>>>>>>>>Getting Agent Network Definition from Sly Data>>>>>>>>>>>>>>>>>>>")

        # Next, check to see if the user provides HOCON file via sly data
        else:
            self.logger.debug(
                ">>>>>>>>>>>>>>>>>>>Reading & Parsing Agent Network HOCON File "
                "from Key 'agent_network_hocon_file' in Sly Data>>>>>>>>>>>>>>>>>>>"
            )
            network_def = await self._hocon_to_definition(self.sly_data.get(AGENT_NETWORK_HOCON_FILE), self.sly_data)

        # If we have a network definition from either source, inject it into the system prompt.
        if network_def:
            # The agent network definition can be provided in either:
            # - dict format (internal), used when creating or editing the network, or
            # - list format (connectivity), which is the native Neuro-San representation.
            # If the definition is in connectivity format, convert it to dict format before editing.
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

    async def _hocon_to_definition(
        self, network_hocon_file: str | None, sly_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Convert hocon file path into agent network definition
        :param network_hocon_file: Agent network hocon file path
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy

        :return: Agent network definition
        """

        # Converting hocon file to dict
        # Note we don't need to cache this because we only expect to read the file once.
        try:
            network_hocon_file = "registries/" + network_hocon_file
            hocon = AbstractAsyncConfigRestorer(file_purpose="get_agent_network_definition", must_exist=True)
            network_hocon = await hocon.async_restore(file_reference=network_hocon_file)
        except (FileNotFoundError, TypeError):
            return None

        agents: list[dict[str, Any]] | None = network_hocon.get("tools")
        if agents is None:
            self.logger.warning("WARNING: No field 'tools' found in %s.", network_hocon_file)
            return None
        if not isinstance(agents, list):
            self.logger.warning("WARNING: The 'tools' field in '%s' is not a list.", network_hocon_file)
            return None

        network_def: dict[str, Any] = {}
        for agent in agents:
            if not isinstance(agent, dict):
                self.logger.warning(
                    "WARNING: Skipping non-dict entry in 'tools' list in '%s': %r", network_hocon_file, agent
                )
                continue
            # Only extract agents info and only "instructions" and "tools" parts
            agent_name: str = agent.get("name")
            if not isinstance(agent_name, str) or not agent_name:
                self.logger.warning(
                    "WARNING: Skipping agent with missing/invalid 'name' in '%s': %r", network_hocon_file, agent
                )
                continue
            network_def[agent_name] = {}
            instructions: str = agent.get("instructions")
            if instructions:
                # Extract only the unique instructions (remove aaosa instructions, instructions prefix, and demo mode)
                custom_instructions: str = await self._extract_custom_instructions(instructions, sly_data)
                network_def[agent_name]["instructions"] = custom_instructions
            tools: list[str] = agent.get("tools")
            if tools:
                network_def[agent_name]["tools"] = tools

        return network_def

    async def _extract_custom_instructions(self, instructions: str, sly_data: dict[str, Any]) -> str:
        """
        Extract the custom part of instructions, excluding aaosa instructions, instructions prefix, and demo mode.
        :param instructions: The full instructions of an agent.
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy

        :return: The part of instructions that is unique to the agent.
        """

        # Pattern for instruction prefix (matches any agent name)
        prefix_pattern = (
            r"You are part of a \w+ of assistants\.\s*Only answer inquiries that are directly within "
            r"your area of expertise\.\s*Do not try to help for other matters\.\s*"
            r"Do not mention what you can NOT do\. Only mention what you can do\."
        )

        demo_mode = (
            "You are part of a demo system, so when queried, make up a realistic response as if "
            "you are actually grounded in real data or you are operating a real application API or microservice."
        )

        aaosa_instructions: str = await self._get_aaosa_instructions(sly_data)

        # Clean and normalize the input
        custom_part: str = instructions.strip()
        custom_part = re.sub(r"\s+", " ", custom_part)  # Normalize whitespace

        # Remove instruction prefix using regex
        custom_part = re.sub(prefix_pattern, "", custom_part).strip()

        # Remove aaosa text
        custom_part = custom_part.replace(aaosa_instructions.strip(), "").strip()

        # Remove demo mode text
        custom_part = custom_part.replace(demo_mode.strip(), "").strip()

        # Clean up any extra whitespace
        custom_part = " ".join(custom_part.split())

        return custom_part

    async def _get_aaosa_instructions(self, sly_data: dict[str, Any]) -> str:
        """
        Get aaosa instructions potentially from cache in sly_data
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy

        :return: aaosa instructions
        """
        aaosa_instructions: str = ""

        # Try to get aaosa_instructions from sly_data cache
        async with await SlyDataLock.get_lock(sly_data, "aaosa_instructions_lock"):
            aaosa_instructions = sly_data.get("aaosa_instructions")
            if aaosa_instructions is not None:
                # Return early with cached value
                return aaosa_instructions

            # Get from file
            try:
                use_file = "registries/aaosa.hocon"
                hocon = AbstractAsyncConfigRestorer(
                    file_purpose="get_agent_network_definition - custom instructions", must_exist=True
                )
                config: dict[str, Any] = await hocon.async_restore(file_reference=use_file)
                aaosa_instructions = config.get("aaosa_instructions", "")
            except FileNotFoundError:
                aaosa_instructions = ""

            # Cache the loaded value in sly_data for subsequent calls
            sly_data["aaosa_instructions"] = aaosa_instructions

        return aaosa_instructions
