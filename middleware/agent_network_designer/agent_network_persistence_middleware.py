
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

from logging import getLogger
from logging import Logger
from os import environ
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware import AgentState
from langchain.agents.middleware import hook_config
from langchain.messages import HumanMessage
from langgraph.runtime import Runtime

from neuro_san.interfaces.reservationist import Reservationist
from neuro_san.internals.validation.network.unreachable_nodes_network_validator import UnreachableNodesNetworkValidator

from coded_tools.agent_network_designer.agent_network_assembler import AgentNetworkAssembler
from coded_tools.agent_network_designer.agent_network_persistor import AgentNetworkPersistor
from coded_tools.agent_network_designer.agent_network_persistor_factory import AgentNetworkPersistorFactory
from coded_tools.agent_network_designer.hocon_agent_network_assembler import HoconAgentNetworkAssembler
from coded_tools.agent_network_editor.connectivity_dictionary_converter import ConnectivityDictionaryConverter
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_HOCON_TEXT
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME

# To use reservations, turn this environment variable to true and also
# export AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS=5
WRITE_TO_FILE: bool = environ.get("AGENT_NETWORK_DESIGNER_USE_RESERVATIONS", "false") != "true"

# Turn this to False if the agents are grouped and don't need demo mode instructions
DEMO_MODE: bool = True

SUBDIRECTORY: str = "generated/"


# pylint: disable=too-few-public-methods
class AgentNetworkPersistenceMiddleware(AgentMiddleware):
    """
    Middleware that validates an agent network definition after each agent turn.

    Runs structural, toolbox, and URL validators against the current network
    definition stored in sly_data. If validation errors are found, an AI message
    containing the errors is injected and control jumps back to the model so
    it can self-correct.
    """

    def __init__(
            self,
            reservationist: Reservationist,
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
        self.logger: Logger = getLogger(self.__class__.__name__)
        self.reservationist = reservationist
        self.sly_data = sly_data

    @hook_config(can_jump_to=["model"])
    async def aafter_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """
        Validate the agent network definition after each agent turn.

        Runs structure, toolbox, and URL validators. If any errors are found,
        returns an AI message with the errors and jumps back to the model.

        :param state: Current agent state
        :param runtime: Runtime context
        :return: Dict with error message and jump directive, or None if valid
        """
        network_def: dict[str, Any] = self.sly_data.get(AGENT_NETWORK_DEFINITION)
        if not network_def:
            content: str = (
                "Error: No agent network found. "
                "Please create a new agent network using `/agent_network_editor` tool"
            )
            return {
                # Use human message to ensure that the model follows the instructions
                "messages": [HumanMessage(content)],
                "jump_to": "model"
            }

        # Get sample queries from args
        sample_queries: list[str] = self.sly_data.get("agent_network_queries")

        # Get the agent network name from sly data
        the_agent_network_name: str = self.sly_data.get(AGENT_NETWORK_NAME)
        # Prepend subdirectory to the agent network name before persisting
        # if not already present.
        # This is needed for the NSflow launcher to connect to the right network.
        if not the_agent_network_name.startswith(SUBDIRECTORY):
            # Neuro-SAN only allows '/' as path separator in agent network names.
            the_agent_network_name = SUBDIRECTORY + the_agent_network_name
        self.sly_data[AGENT_NETWORK_NAME] = the_agent_network_name

        self.logger.info(">>>>>>>>>>>>>>>>>>>Create Agent Network>>>>>>>>>>>>>>>>>>")
        self.logger.info("Agent Network Name: %s", str(the_agent_network_name))
        # Get the persistor first, as that will determine how we want to assemble the agent network
        persistor: AgentNetworkPersistor = AgentNetworkPersistorFactory.create_persistor(
            {"reservationist": self.reservationist}, WRITE_TO_FILE, DEMO_MODE, None, None
        )
        assembler: AgentNetworkAssembler = persistor.get_assembler()
        top_agent_name: str = UnreachableNodesNetworkValidator().find_all_top_agents(network_def).pop()
        persisted_content: str = await assembler.assemble_agent_network(
            network_def, top_agent_name, the_agent_network_name, sample_queries
        )
        self.logger.info("The resulting agent network: \n %s", str(persisted_content))

        persisted_reference: str | list[dict[str, Any]] = await persistor.async_persist(
            obj=persisted_content, file_reference=the_agent_network_name
        )

        if isinstance(persisted_reference, list):
            self.sly_data["agent_reservations"] = persisted_reference

        hocon_text: str = persisted_content
        if not isinstance(assembler, HoconAgentNetworkAssembler):
            # We don't yet have client-consumable HOCON content, so we need to re-assemble
            # to send that back as a parting gift.
            assembler = HoconAgentNetworkAssembler(DEMO_MODE)
            hocon_text: str = await assembler.assemble_agent_network(
                network_def, top_agent_name, the_agent_network_name, sample_queries
            )
        self.sly_data[AGENT_NETWORK_HOCON_TEXT] = hocon_text

        self._determine_exported_network_definition(self.sly_data)

        self.logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")

        return None
    
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
