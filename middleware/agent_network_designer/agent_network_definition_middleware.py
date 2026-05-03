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
import os
import re
from logging import Logger
from logging import getLogger
from pathlib import Path
from re import Match
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import override

from botocore.exceptions import ClientError
from langchain.agents.middleware.types import AgentMiddleware
from langchain.agents.middleware.types import AgentState
from langchain.agents.middleware.types import ContextT
from langchain.agents.middleware.types import ModelRequest
from langchain.agents.middleware.types import ModelResponse
from langchain.agents.middleware.types import ResponseT
from langchain.agents.middleware.types import hook_config
from langchain_core.messages import AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages import SystemMessage
from neuro_san.interfaces.agent_progress_reporter import AgentProgressReporter
from neuro_san.internals.persistence.abstract_async_config_restorer import AbstractAsyncConfigRestorer
from neuro_san.service.watcher.temp_networks.s3_reservations_storage import S3ReservationsStorage

from coded_tools.agent_network_editor.connectivity_dictionary_converter import ConnectivityDictionaryConverter
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from coded_tools.agent_network_editor.progress_handler import ProgressHandler
from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock

AGENT_NETWORK_HOCON_FILE: str = "agent_network_hocon_file"
AGENT_RESERVATIONS: str = "agent_reservations"


class AgentNetworkDefinitionMiddleware(AgentMiddleware):
    """
    Middleware that reads the agent network definition from sly_data and injects it
    into the system prompt before each model call.

    This allows the LLM to reason about the current agent network structure without
    requiring it to be passed explicitly through the chat stream.
    """

    def __init__(self, sly_data: dict[str, Any], progress_reporter: AgentProgressReporter | None = None) -> None:
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
        :param progress_reporter: An optional AgentProgressReporter instance for
                reporting agent_network_definition to the client.
        """
        self.progress_reporter: AgentProgressReporter | None = progress_reporter
        self.sly_data = sly_data

        self.logger: Logger = getLogger(self.__class__.__name__)
        # Initialize agent network definition
        self.network_def: dict[str, Any] | list[dict[str, Any]] | None = None
        # Initialize an error message to store issues encountered during loading from HOCON file or S3 reservation.
        self.error_message: str = ""

    @override
    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state: AgentState[Any], runtime: Any) -> dict[str, Any] | None:
        """
        Resolve agent network definition before the model call, if there was an error loading
        the agent network definition from HOCON file or S3 reservation, report that error back to the client.

        Note that this is done before model, not before agent, because the definition may change between
        each model call (e.g., when the agent calls a tool that updates the network definition).

        :param state: Current agent state
        :param runtime: Runtime context
        :return: Dict with error message and jump directive, or None if no error
        """
        self.network_def = await self._resolve_network_def()
        if self.error_message:
            # Loading errors (HOCON file or S3 reservation) only occur in the top-level agent_network_designer
            # network, not in its subnetworks, since loading is only triggered from the main network's sly_data.
            # Therefore, this jump will only fire in the agent_network_designer agent itself.
            return {
                "messages": [AIMessage(self.error_message)],
                "jump_to": "end",
            }
        return None

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """
        Normalize the agent network definition format, cache in sly data, and inject it into the system prompt
        before each model call.

        :param request: Model request containing messages and state
        :param handler: Handler to execute the model call
        :return: Model response from handler
        """
        if not self.network_def:
            return await handler(request)

        # Ensure that agent network definition is in dict (internal) format so that the designer agents know
        # how to modify it and cache in sly data.
        network_def = self._normalize_network_def(self.network_def)
        return await self._inject_into_request(network_def, request, handler)

    async def _resolve_network_def(self) -> dict[str, Any] | list[dict[str, Any]] | None:
        """
        Resolve the agent network definition from sly_data, HOCON file, or S3 reservation.

        :return: Agent network definition, or None if not found
        """
        network_def: dict[str, Any] | list[dict[str, Any]] | None = self.sly_data.get(AGENT_NETWORK_DEFINITION)
        hocon_file: str | None = self.sly_data.get(AGENT_NETWORK_HOCON_FILE)
        agent_reservations: list[dict[str, Any]] | None = self.sly_data.get(AGENT_RESERVATIONS)

        # First, check to see if there is a generated agent network definition in sly_data.
        if network_def:
            # This log level is set to debug since this gets called before every model call and can be quite verbose.
            self.logger.debug(">>>>>>>>>>>>>>>>>>>Getting Agent Network Definition from Sly Data>>>>>>>>>>>>>>>>>>>")
            return network_def

        # Next, check to see if the user provides HOCON file via sly data
        if hocon_file:
            self.logger.info(
                ">>>>>>>>>>>>>>>>>>>Reading & Parsing from Agent Network HOCON File '%s'>>>>>>>>>>>>>>>>>>>",
                hocon_file,
            )
            network_def = await self._hocon_to_definition(hocon_file, self.sly_data)
            # When loading from hocon, use the file name (without extension) as the agent network name.
            # This is because the agent network name is only created when using the CreateNetwork tool.
            if network_def:
                self.sly_data[AGENT_NETWORK_NAME] = Path(hocon_file).stem
            return network_def

        # Lastly, check the reservation ID in agent reservation field in sly data.
        return await self._resolve_network_def_from_s3(agent_reservations)

    async def _resolve_network_def_from_s3(self, agent_reservations: list[dict[str, Any]]) -> dict[str, Any] | None:
        """
        Resolve the agent network definition from an S3 reservation.

        :param agent_reservations: A list of reservation structures describing the temporary agent networks that were
                    created by interacting with this agent. By convention, the last one in the list is a top-level
                    handle which may reference any others listed.
        :return: Agent network definition, or None if no reservation ID is provided
                    or if there are issues retrieving/parsing the reservation
        """
        if not agent_reservations:
            return None
        if not isinstance(agent_reservations, list):
            self.logger.warning(
                "Warning: Invalid '%s' value: %s (expected a list)",
                AGENT_RESERVATIONS,
                type(agent_reservations).__name__,
            )
            return None

        last_reservation: dict[str, Any] = agent_reservations[-1]
        if "reservation_id" not in last_reservation:
            return None

        error_message: str = "Error: Failed to load agent network definition from S3 reservation for unknown reasons."
        reservation_id: str | None = last_reservation.get("reservation_id")
        if not isinstance(reservation_id, str) or not reservation_id:
            error_message = (
                f"Error: Invalid 'reservation_id' value: {type(reservation_id).__name__} "
                "(expected a non-empty string)."
            )
            self.logger.error(error_message)
            self.error_message = error_message
            return None

        config: dict[str, Any] | None = None
        try:
            # Setting up AWS credentials in environment variables is required for S3ReservationsStorage to work.
            # AWS_ACCESS_KEY_ID="your-access-key"
            # AWS_SECRET_ACCESS_KEY="your-secret-key"
            # AWS_DEFAULT_REGION="us-east-1" or your region
            # (Optional if your credentials file has the region specified)
            # Other options include:
            # AWS profile: AWS_PROFILE="your-profile" (reads from ~/.aws/credentials)
            # Session token (temporary creds): add AWS_SESSION_TOKEN="your-token"
            # IAM role: no env vars needed if running on EC2/ECS/Lambda with an attached role
            #
            # This env var must be set to the S3 Bucket that the network reservations is stored.
            # AGENT_RESERVATIONS_S3_BUCKET
            s3_storage = S3ReservationsStorage()
            s3_storage.start()
            try:
                _, agent_network = s3_storage.get_one_reservation(reservation_id)
                config = agent_network.get_config()
            except AttributeError as attribute_error:
                error_message = (
                    f"Error: Reservation '{reservation_id}' does not contain an agent network or config. "
                    f"{attribute_error}"
                )
                self.logger.error(error_message)
            except ClientError as client_error:
                error_message = f"Error: Failed to retrieve reservation '{reservation_id}' from S3. {client_error}"
                self.logger.error(error_message)
            finally:
                s3_storage.stop()
        except ValueError as value_error:
            error_message = f"Error: Failed to initialize S3 storage for reservation '{reservation_id}'. {value_error}"
            self.logger.error(error_message)

        if not config:
            self.error_message = error_message
            return None

        # When loading from s3, use extract the name from id and used as the agent network name.
        # This is because the agent network name is only created when using the CreateNetwork tool.
        self.sly_data[AGENT_NETWORK_NAME] = self._extract_name_from_reservation_id(reservation_id)
        self.logger.info(
            ">>>>>>>>>>>>>Reading & Parsing Agent Network Config from Reservation %s in %s S3 Bucket>>>>>>>>>>>>>>>>>",
            reservation_id,
            os.getenv("AGENT_RESERVATIONS_S3_BUCKET"),
        )
        return await self._config_to_network_def(config, reservation_id, self.sly_data)

    def _normalize_network_def(self, network_def: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        """
        Ensure the network definition is in dict format, converting from connectivity list if needed,
        and cache it in sly_data.

        :param network_def: Network definition in dict or connectivity list format
        :return: Network definition as a dict
        """
        # The agent network definition can be provided in either:
        # - dict format (internal), used when creating or editing the network, or
        # - list format (connectivity), which is the native Neuro-San representation.
        # If the definition is in connectivity format, convert it to dict format before editing.
        if isinstance(network_def, list):
            connectivity_dict_converter = ConnectivityDictionaryConverter()
            network_def = connectivity_dict_converter.to_dict(network_def)
        # Cache the agent network definition as dict in sly_data for subsequent calls within the same session.
        self.sly_data[AGENT_NETWORK_DEFINITION] = network_def
        return network_def

    async def _inject_into_request(
        self,
        network_def: dict[str, Any],
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """
        Inject the network definition into the system prompt and invoke the handler.

        :param network_def: Agent network definition dict
        :param request: Model request containing messages and state
        :param handler: Handler to execute the model call
        :return: Model response from handler
        """
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

        if self.progress_reporter is not None:
            await ProgressHandler.report_progress(
                {"progress_reporter": self.progress_reporter}, network_def, self.sly_data.get(AGENT_NETWORK_NAME)
            )

        return await handler(request.override(system_message=system_message))

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
        config: dict[str, Any] | None = await self._hocon_to_config(network_hocon_file)
        if config is None:
            return None
        return await self._config_to_network_def(config, network_hocon_file, sly_data)

    async def _hocon_to_config(self, network_hocon_file: str | None) -> dict[str, Any] | None:
        """
        Read and parse a HOCON file into a raw config dictionary.

        :param network_hocon_file: Agent network hocon file path
        :return: Parsed HOCON contents as a dict, or None if network_hocon_file is invalid or not found
        """
        if not isinstance(network_hocon_file, str) or not network_hocon_file:
            error_message: str = (
                f"Error: Invalid network_hocon_file value: {type(network_hocon_file).__name__} "
                "(expected non-empty string)."
            )
            self.logger.error(error_message)
            self.error_message = error_message
            return None

        # Note we don't need to cache this because we only expect to read the file once.
        try:
            hocon = AbstractAsyncConfigRestorer(file_purpose="get_agent_network_definition", must_exist=True)
            return await hocon.async_restore(file_reference="registries/" + network_hocon_file)
        except FileNotFoundError:
            error_message = f"Error: Agent network HOCON file not found: registries/{network_hocon_file}"
            self.logger.error(error_message)
            self.error_message = error_message
            return None

    async def _config_to_network_def(
        self, config: dict[str, Any], source: str, sly_data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Convert a parsed HOCON config dictionary into an agent network definition.

        :param config: Parsed HOCON config
        :param source: Identifier for the config source (hocon file path or reservation ID), used for error messages
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy
        :return: Agent network definition, or None on failure
        """
        agents: list[dict[str, Any]] | None = config.get("tools")
        if not isinstance(agents, list):
            msg: str = "No field 'tools' found" if agents is None else "The 'tools' field is not a list"
            error_message: str = f"Error: {msg} in config from {source}."
            self.logger.error(error_message)
            self.error_message = error_message
            return None

        network_def: dict[str, Any] = {}
        for agent in agents:
            name, agent_def = await self._parse_agent(agent, source, sly_data)
            if name is not None:
                network_def[name] = agent_def

        return network_def

    async def _parse_agent(
        self, agent: Any, source: str, sly_data: dict[str, Any]
    ) -> tuple[str | None, dict[str, Any]]:
        """
        Parse a single agent entry from the hocon 'tools' list.

        :param agent: A single entry from the 'tools' list in the hocon file
        :param source: Identifier for the config source (hocon file path or reservation ID), used for warning messages
        :param sly_data: A dictionary whose keys are defined by the agent hierarchy

        :return: (agent_name, agent_def) where agent_name is None if the entry should be skipped
        """
        if not isinstance(agent, dict):
            self.logger.warning("WARNING: Skipping non-dict entry in 'tools' list in '%s': %r", source, agent)
            return None, {}

        agent_name: str | None = agent.get("name")
        if not isinstance(agent_name, str) or not agent_name:
            self.logger.warning("WARNING: Skipping agent with missing/invalid 'name' in '%s': %r", source, agent)
            return None, {}

        # Only extract agents info and only "instructions" and "tools" parts
        agent_def: dict[str, Any] = {}

        instructions: str | None = agent.get("instructions")
        if instructions is not None:
            if not isinstance(instructions, str):
                self.logger.warning(
                    "WARNING: Skipping agent %s due to non-string 'instructions' in '%s'",
                    agent_name,
                    source,
                )
                return None, {}
            if instructions.strip():
                # Extract only the unique instructions
                # (remove aaosa instructions, instructions prefix, and demo mode)
                agent_def["instructions"] = await self._extract_custom_instructions(instructions.strip(), sly_data)

            # Initialize description for non-function agents so the description setter
            # can distinguish them from function/toolbox agents (which have no description key).
            agent_def["description"] = ""

        function: dict[str, Any] = agent.get("function", {})
        description: str | None = function.get("description") if isinstance(function, dict) else None
        if description is not None:
            if not isinstance(description, str):
                self.logger.warning(
                    "WARNING: Skipping agent %s due to non-string 'description' in '%s'",
                    agent_name,
                    source,
                )
                return None, {}
            if description.strip():
                agent_def["description"] = description.strip()

        tools: list[str] | None = agent.get("tools")
        if tools:
            agent_def["tools"] = tools

        return agent_name, agent_def

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

    def _extract_name_from_reservation_id(self, reservation_id: str) -> str:
        # re.search() scans through the string looking for the UUID pattern
        # The pattern explained:
        #   -           matches a literal hyphen (separator between name and UUID)
        #   [0-9a-f]    matches any hex character (digits 0-9 or letters a-f)
        #   {8}         exactly 8 hex characters  → "550e8400"
        #   -           literal hyphen
        #   [0-9a-f]{4} exactly 4 hex characters  → "e29b"
        #   -           literal hyphen
        #   [0-9a-f]{4} exactly 4 hex characters  → "41d4"
        #   -           literal hyphen
        #   [0-9a-f]{4} exactly 4 hex characters  → "a716"
        #   -           literal hyphen
        #   [0-9a-f]{12} exactly 12 hex characters → "446655440000"
        #   $           end of string (UUID must be at the very end)
        #
        # re.IGNORECASE makes it match both uppercase and lowercase hex (a-f or A-F)
        match: Match | None = re.search(
            r"-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", reservation_id, re.IGNORECASE
        )

        # match.start() gives the index where the UUID pattern begins in the string
        # reservation_id[:match.start()] slices the string from the beginning up to (not including) that index
        # if no UUID is found (match is None), we just return the original string unchanged
        return reservation_id[: match.start()] if match else reservation_id
