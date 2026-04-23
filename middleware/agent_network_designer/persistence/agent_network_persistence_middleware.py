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
from coded_tools.agent_network_editor.constants import MCP_SERVERS
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_query_generator.set_sample_queries import AGENT_NETWORK_QUERIES
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

# To use reservations, turn this environment variable to true and also
# export AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS=5
WRITE_TO_FILE: bool = environ.get("AGENT_NETWORK_DESIGNER_USE_RESERVATIONS", "false").lower() != "true"

# Set this to False if the agents are grounded and don't need demo mode instructions
DEMO_MODE: bool = environ.get("AGENT_NETWORK_DESIGNER_DEMO_MODE", "true").lower() == "true"

# Subdirectory under registries directory where networks are saved when using file persistence.
SUBDIRECTORY: str = environ.get("AGENT_NETWORK_DESIGNER_SUBDIRECTORY", DEFAULT_SUBDIRECTORY)


class AgentNetworkPersistenceMiddleware(AgentMiddleware):
    """
    Middleware that validates and persists an agent network after the agent finishes
    (i.e., no more tool calls are pending).

    Runs structural, toolbox, URL, and keyword validators against the current network
    definition stored in sly_data. If validation errors are found, a human message
    containing the errors is injected and control jumps back to the model so
    it can self-correct.

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

    # Reenter the agent loop at the model node if validation fails or there is no agent network definition.
    # See https://github.com/cognizant-ai-lab/neuro-san-studio/blob/main/docs/user_guide.md#middleware and
    # https://reference.langchain.com/python/langchain/agents/middleware/types/hook_config for details on
    # hook_config and jump_to.
    @hook_config(can_jump_to=["model"])
    async def aafter_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """
        Validate and persist the agent network after the agent finishes.

        Called when the agent has no more pending tool calls. Runs structure, toolbox,
        URL, and keyword validators against the network definition in sly_data. If any
        errors are found, injects a human message with the errors and jumps back to the
        model so it can self-correct.

        This validation acts as a final safety net: even if the agent bypassed calling
        the necessary tools or subnetworks (and thus their built-in validators never ran),
        errors will still be caught here before the network is persisted.

        :param state: Current agent state
        :param runtime: Runtime context
        :return: Dict with error message and jump directive, or None if valid
        """
        network_def: dict[str, Any] = self.sly_data.get(AGENT_NETWORK_DEFINITION)
        if not network_def:
            return self._error_response(
                "No agent network found. Please create a new agent network using `/agent_network_editor` tool"
            )

        error_list: list[str] = await self._validate_network(network_def)
        if error_list:
            self.logger.error("Error: %s", error_list)
            return self._error_response(
                f"The current agent network definition has the following issues: {error_list}. "
                "Please fix these issues to ensure the agent network can be properly assembled and executed."
            )

        the_agent_network_name: str = self._normalize_network_name(self.sly_data.get(AGENT_NETWORK_NAME))
        self.sly_data[AGENT_NETWORK_NAME] = the_agent_network_name
        sample_queries: list[str] = self.sly_data.get(AGENT_NETWORK_QUERIES, [])

        await self._assemble_and_persist(network_def, the_agent_network_name, sample_queries)
        self._determine_exported_network_definition(self.sly_data)

        self.logger.debug(">>>>>>>>>>>>>>>>>>> DONE %s !!!>>>>>>>>>>>>>>>>>>", self.__class__.__name__)

        return None

    def _error_response(self, content: str) -> dict[str, Any]:
        """Return a jump-to-model response with the given error content."""
        return {
            # Use human message to ensure that the model follows the instructions
            "messages": [HumanMessage(content)],
            "jump_to": "model",
        }

    async def _validate_network(self, network_def: dict[str, Any]) -> list[str]:
        """
        Run all validators against the network definition, reusing the validation middlewares.

        :return: List of error strings, empty if valid.
        """
        structure_errors = await AgentNetworkStructureValidationMiddleware(self.sly_data).validate(network_def)
        instructions_errors = await AgentNetworkInstructionsValidationMiddleware(self.sly_data).validate(network_def)
        return structure_errors + instructions_errors

    def _normalize_network_name(self, name: str) -> str:
        """Prepend SUBDIRECTORY prefix if not already present."""
        prefix: str = SUBDIRECTORY.rstrip("/") + "/"
        if not name.startswith(prefix):
            # Neuro-SAN only allows '/' as path separator in agent network names.
            return prefix + name
        return name

    async def _assemble_and_persist(
        self,
        network_def: dict[str, Any],
        the_agent_network_name: str,
        sample_queries: list[str],
    ) -> None:
        """
        Assemble the agent network and persist it, then store HOCON text in sly_data.

        If WRITE_TO_FILE is True, the network is persisted by writing a HOCON file to disk.
        Otherwise, it is registered as a temporary network via the reservationist interface.
        """
        self.logger.info(">>>>>>>>>>>>>>>>>>>Create Agent Network>>>>>>>>>>>>>>>>>>")
        self.logger.info("Agent Network Name: %s", the_agent_network_name)

        subnetwork_names: list[str] = GetSubnetwork.get_subnetwork_names(self.sly_data)
        mcp_servers: list[str] = self.sly_data.get(MCP_SERVERS, [])
        persistor: AgentNetworkPersistor = AgentNetworkPersistorFactory.create_persistor(
            {"reservationist": self.reservationist},
            WRITE_TO_FILE,
            DEMO_MODE,
            SUBDIRECTORY,
            subnetwork_names,
            mcp_servers,
        )
        assembler: AgentNetworkAssembler = persistor.get_assembler()
        top_agent_name: str = UnreachableNodesNetworkValidator().find_all_top_agents(network_def).pop()
        persisted_content: str = await assembler.assemble_agent_network(
            network_def, top_agent_name, the_agent_network_name, sample_queries
        )
        self.logger.info("The resulting agent network: \n %s", persisted_content)

        if WRITE_TO_FILE:
            file_reference: str = the_agent_network_name
        else:
            # Reservations API forbids '/', ':', and ' ' — strip subdirectory prefix then sanitize
            file_reference = the_agent_network_name.removeprefix(SUBDIRECTORY)
            for char in ["/", ":", " "]:
                file_reference = file_reference.replace(char, "")

        persisted_reference: str | list[dict[str, Any]] = await persistor.async_persist(
            obj=persisted_content, file_reference=file_reference
        )
        if isinstance(persisted_reference, list):
            self.sly_data["agent_reservations"] = persisted_reference

        if not isinstance(assembler, HoconAgentNetworkAssembler):
            # We don't yet have client-consumable HOCON content, so we need to re-assemble
            # to send that back as a parting gift.
            assembler = HoconAgentNetworkAssembler(DEMO_MODE)
            persisted_content = await assembler.assemble_agent_network(
                network_def, top_agent_name, the_agent_network_name, sample_queries
            )
        self.sly_data[AGENT_NETWORK_HOCON_TEXT] = persisted_content

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
