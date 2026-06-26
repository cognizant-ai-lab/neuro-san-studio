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

from logging import Logger
from logging import getLogger
from os import environ
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware import AgentState
from langchain.agents.middleware import hook_config
from langchain.messages import HumanMessage
from langgraph.runtime import Runtime
from neuro_san.interfaces.reservationist import Reservationist
from neuro_san.internals.validation.network.unreachable_nodes_network_validator import UnreachableNodesNetworkValidator

from coded_tools.agent_network_editor.connectivity_dictionary_converter import ConnectivityDictionaryConverter
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_HOCON_TEXT
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_query_generator.set_sample_queries import AGENT_NETWORK_QUERIES
from middleware.agent_network_designer.agent_network_definition_middleware import SKIP_DESIGNER
from middleware.agent_network_designer.persistence.agent_network_assembler import AgentNetworkAssembler
from middleware.agent_network_designer.persistence.agent_network_persistor import AgentNetworkPersistor
from middleware.agent_network_designer.persistence.agent_network_persistor_factory import AgentNetworkPersistorFactory
from middleware.agent_network_designer.persistence.file_system_agent_network_persistor import DEFAULT_SUBDIRECTORY
from middleware.agent_network_designer.persistence.hocon_agent_network_assembler import HoconAgentNetworkAssembler
from middleware.agent_network_designer.validation.agent_network_instructions_validation_middleware import (
    AgentNetworkInstructionsValidationMiddleware,
)
from middleware.agent_network_designer.validation.agent_network_structure_validation_middleware import (
    AgentNetworkStructureValidationMiddleware,
)

# To use reservations, turn this environment variable to true
WRITE_TO_FILE: bool = environ.get("AGENT_NETWORK_DESIGNER_USE_RESERVATIONS", "false").lower() != "true"

# Set this to False if the agents are grounded and don't need demo mode instructions
DEMO_MODE: bool = environ.get("AGENT_NETWORK_DESIGNER_DEMO_MODE", "true").lower() == "true"

# Subdirectory under registries directory where networks are saved when using file persistence.
SUBDIRECTORY: str = environ.get("AGENT_NETWORK_DESIGNER_SUBDIRECTORY", DEFAULT_SUBDIRECTORY)

# Default number of validation retry rounds when the env var is unset or unparseable.
DEFAULT_MAX_VALIDATION_ATTEMPTS: int = 3


class AgentNetworkPersistenceMiddleware(AgentMiddleware):
    """
    Middleware that validates and persists an agent network after the agent finishes
    (i.e., no more tool calls are pending).

    If an agent network definition is present in sly_data, runs structural and instruction
    validators against it. If validation errors are found, a human message containing the
    errors is injected and control jumps back to the model so it can self-correct.

    If no agent network definition is present, this middleware does nothing and returns None,
    allowing the agent to respond freely. This handles cases where loading failed upstream
    (e.g., in AgentNetworkDefinitionMiddleware) and the agent needs to report that error
    rather than produce a network definition.

    Note: Validation is intentionally duplicated here even though individual subnetworks
    already perform their own validation. This is a safeguard for cases where the agent
    returns a final response without having called the necessary tools or subnetworks —
    meaning the subnetwork validators may never have run. By validating in this middleware,
    we catch those premature completions and force the agent to correct itself.
    """

    def __init__(self, reservationist: Reservationist, sly_data: dict[str, Any]) -> None:
        """
        Initialize agent network persistence middleware.

        :param reservationist: Reservationist interface for making reservations on temporary networks
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
        self.logger: Logger = getLogger(self.__class__.__name__)
        self.reservationist = reservationist
        self.sly_data = sly_data
        # Maximum number of validation retry rounds before bailing without persisting.
        # Parsed per-instance so a bad env var degrades this one session, not the whole server.
        raw_max: str = environ.get(
            "AGENT_NETWORK_DESIGNER_MAX_VALIDATION_ATTEMPTS", str(DEFAULT_MAX_VALIDATION_ATTEMPTS)
        )
        try:
            self.max_validation_attempts: int = max(0, int(raw_max))
        except ValueError:
            self.logger.warning(
                "Invalid AGENT_NETWORK_DESIGNER_MAX_VALIDATION_ATTEMPTS=%r; falling back to %d.",
                raw_max,
                DEFAULT_MAX_VALIDATION_ATTEMPTS,
            )
            self.max_validation_attempts = DEFAULT_MAX_VALIDATION_ATTEMPTS
        # Counts validation rounds that failed in this session, used to cap retries.
        self._validation_attempts: int = 0

    # Reenter the agent loop at the model node if validation fails.
    # If no agent network definition is present, return None to let the agent respond freely.
    # See https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#middleware and
    # https://reference.langchain.com/python/langchain/agents/middleware/types/hook_config for details on
    # hook_config and jump_to.
    @hook_config(can_jump_to=["model"])
    async def aafter_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """
        Validate and persist the agent network after the agent finishes.

        Called when the agent has no more pending tool calls. If an agent network definition
        is present in sly_data, runs structure and instruction validators against it. If any
        errors are found, injects a human message with the errors and jumps back to the model
        so it can self-correct. If no definition is present, returns None so the agent can
        respond freely (e.g., to report a loading error from AgentNetworkDefinitionMiddleware).

        This validation acts as a final safety net: even if the agent bypassed calling
        the necessary tools or subnetworks (and thus their built-in validators never ran),
        errors will still be caught here before the network is persisted.

        :param state: Current agent state
        :param runtime: Runtime context
        :return: Dict with error message and jump directive, or None if valid
        """
        network_def: dict[str, Any] = self.sly_data.get(AGENT_NETWORK_DEFINITION)
        agent_network_name: str = self.sly_data.get(AGENT_NETWORK_NAME)
        # Only validate and persist if there is an agent_network_definition with a valid name; otherwise let
        # the agent respond to the user freely. This allows the agent to ask clarifying questions or report
        # issues without being forced to produce a network definition — for example, when
        # AgentNetworkDefinitionMiddleware failed to load from a HOCON file or S3 reservation and
        # already reported the error (jumping to end), so no network definition will be present.
        # A valid name is also required for file path and reservation name construction.
        if network_def and agent_network_name and isinstance(agent_network_name, str):
            structure_errors, instructions_errors = await self._validate_network(network_def)
            if structure_errors or instructions_errors:
                self.logger.warning("Validation errors: %s", structure_errors + instructions_errors)
                # Bail out if we've already retried the max number of times. Returning None
                # ends the session without persisting; the agent's last message reaches the user.
                # Prevents runaway loops when the model can't fix the errors (e.g., the required
                # tool was silently dropped from the tools array under load).
                if self._validation_attempts >= self.max_validation_attempts:
                    self.logger.warning(
                        "Reached max validation attempts (%d); ending without persisting.",
                        self.max_validation_attempts,
                    )
                    return None
                self._validation_attempts += 1
                self.logger.warning(
                    "Invoking agent network designer to fix the issues (attempt %d/%d).",
                    self._validation_attempts,
                    self.max_validation_attempts,
                )
                message_parts: list[str] = []
                if structure_errors:
                    message_parts.append(
                        f"The agent network definition has structural issues: {structure_errors}. "
                        "Call `agent_network_editor` to fix these structural problems."
                    )
                if instructions_errors:
                    message_parts.append(
                        f"The agent network definition has instructions-related issues: {instructions_errors}. "
                        "Call `agent_network_instructions_editor` to fix these instructions problems."
                    )
                if structure_errors and instructions_errors:
                    message_parts.append(
                        "Fix the structural issues first by calling `agent_network_editor`, "
                        "then address the instructions issues with `agent_network_instructions_editor`."
                    )
                return self._error_response(" ".join(message_parts))

            # Validation succeeded. Reset the counter so a later turn in the same session
            # (e.g., a follow-up modification) gets its own full retry budget.
            self._validation_attempts = 0

            sample_queries: list[str] = self.sly_data.get(AGENT_NETWORK_QUERIES, [])

            await self._assemble_and_persist(network_def, agent_network_name, sample_queries)
            self._determine_exported_network_definition(self.sly_data)

            self.logger.debug(">>>>>>>>>>>>>>>>>>> DONE %s !!!>>>>>>>>>>>>>>>>>>", self.__class__.__name__)

        return None

    def _error_response(self, content: str) -> dict[str, Any]:
        """Return a jump-to-model response with the given error content."""
        # Set the skip designer value to False to prevent infinite loop since jumping to model actually jump to the
        # before model method in AgentNetworkDefinitionMiddleware, which jumps back to here if skip designer is True.
        # This is also an indicator for client that there are issues with input agent_network_definition and that the
        # designer has made changes to the definition.
        if self.sly_data.get(SKIP_DESIGNER) is True:
            self.sly_data[SKIP_DESIGNER] = False
        return {
            # Use human message to ensure that the model follows the instructions
            "messages": [HumanMessage(content)],
            "jump_to": "model",
        }

    async def _validate_network(self, network_def: dict[str, Any]) -> tuple[list[str], list[str]]:
        """
        Run all validators against the network definition, reusing the validation middlewares.

        :return: Tuple of (structure_errors, instructions_errors), each a list of error strings.
        """
        structure_errors: list[str] = await AgentNetworkStructureValidationMiddleware(self.sly_data).validate(
            network_def
        )
        instructions_errors: list[str] = await AgentNetworkInstructionsValidationMiddleware(self.sly_data).validate(
            network_def
        )
        return structure_errors, instructions_errors

    async def _assemble_and_persist(
        self,
        network_def: dict[str, Any],
        agent_network_name: str,
        sample_queries: list[str],
    ) -> None:
        """
        Assemble the agent network, store HOCON text in sly_data, and persist it.

        HOCON content is always assembled first and stored in sly_data for client consumption.
        If WRITE_TO_FILE is True, that same HOCON content is persisted to disk; the subdirectory
        prefix is added by FileSystemAgentNetworkPersistor internally.
        Otherwise, a deployable config is assembled and registered as a temporary network via
        the reservationist interface using the sanitized raw name.

        :param agent_network_name: The raw network name without any subdirectory prefix.
        """
        self.logger.info(">>>>>>>>>>>>>>>>>>>Assemble and Persist Agent Network>>>>>>>>>>>>>>>>>>")
        self.logger.info("Agent Network Name: %s", agent_network_name)

        subnetwork_names: list[str] = await GetSubnetwork.get_subnetwork_names(self.sly_data)
        mcp_servers: list[str] = await GetMcpTool.get_mcp_servers(self.sly_data)
        persistor: AgentNetworkPersistor = AgentNetworkPersistorFactory.create_persistor(
            {"reservationist": self.reservationist},
            WRITE_TO_FILE,
            DEMO_MODE,
            SUBDIRECTORY,
            subnetwork_names,
            mcp_servers,
        )
        top_agent_name: str = UnreachableNodesNetworkValidator().find_all_front_man_agents(network_def).pop()

        # Always assemble and store HOCON content for client consumption.
        persisted_content: str = await HoconAgentNetworkAssembler(DEMO_MODE).assemble_agent_network(
            network_def, top_agent_name, agent_network_name, sample_queries
        )
        self.logger.info("The resulting agent network content: \n %s", persisted_content)
        self.sly_data[AGENT_NETWORK_HOCON_TEXT] = persisted_content

        # Reservations API forbids '/', ':', and ' ' — sanitize the raw name for that case.
        # FileSystemAgentNetworkPersistor handles its own subdirectory prefixing internally.
        file_reference: str = agent_network_name
        if not WRITE_TO_FILE:
            for char in ["/", ":", " "]:
                file_reference = file_reference.replace(char, "")
            # For reservations, assemble a deployable config instead of HOCON.
            assembler: AgentNetworkAssembler = persistor.get_assembler()
            # The persisted content for reservations is config.
            persisted_content: dict[str, Any] = await assembler.assemble_agent_network(
                network_def, top_agent_name, agent_network_name, sample_queries
            )
        # Persist the agent network
        persisted_reference: str | list[dict[str, Any]] = await persistor.async_persist(
            obj=persisted_content, file_reference=file_reference
        )
        # Store information on reservations in the sly data
        if isinstance(persisted_reference, list):
            self.sly_data["agent_reservations"] = persisted_reference

    def _determine_exported_network_definition(self, sly_data: dict[str, Any]):
        """
        Check the AGENT_NETWORK_DESIGNER_PROGRESS_STYLE env var to determine how to export
        the agent network definition.
        """
        network_definition: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        use_network_definition: dict[str, Any] | list[dict[str, Any]] = network_definition

        agent_progress_style: str = environ.get("AGENT_NETWORK_DESIGNER_PROGRESS_STYLE", "internal")
        if agent_progress_style == "connectivity":
            # The idea here is that a multi-user MAUI server can turn on this env variable
            # so that agent network progress is converted to connectivity-style data format
            # that it already knows how to render.  Using the different key name allows the AGENT_PROGRESS
            # dictionary to look just like a ConnectivityResponse from the service.
            converter = ConnectivityDictionaryConverter()
            use_network_definition: list[dict[str, Any]] = converter.from_dict(network_definition)

        elif agent_progress_style == "internal":
            # Report the internal structure used by Agent Network Designer and pals.
            # This is what was used in the first iterations with nsflow.
            use_network_definition: dict[str, Any] = network_definition

        sly_data[AGENT_NETWORK_DEFINITION] = use_network_definition
