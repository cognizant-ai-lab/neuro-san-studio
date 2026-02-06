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
from copy import deepcopy
from os import environ
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.validation.network.keyword_network_validator import KeywordNetworkValidator
from neuro_san.internals.validation.network.structure_network_validator import StructureNetworkValidator
from neuro_san.internals.validation.network.toolbox_network_validator import ToolboxNetworkValidator
from neuro_san.internals.validation.network.unreachable_nodes_network_validator import UnreachableNodesNetworkValidator
from neuro_san.internals.validation.network.url_network_validator import UrlNetworkValidator

from coded_tools.agent_network_designer.agent_network_assembler import AgentNetworkAssembler
from coded_tools.agent_network_designer.agent_network_persistor import AgentNetworkPersistor
from coded_tools.agent_network_designer.agent_network_persistor_factory import AgentNetworkPersistorFactory
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_NAME
from coded_tools.agent_network_editor.get_mcp_tool import GetMcpTool
from coded_tools.agent_network_editor.get_subnetwork import GetSubnetwork
from coded_tools.agent_network_editor.get_toolbox import GetToolbox

# To use reservations, turn this environment variable to true and also
# export AGENT_TEMPORARY_NETWORK_UPDATE_PERIOD_SECONDS=5
WRITE_TO_FILE: bool = environ.get("AGENT_NETWORK_DESIGNER_USE_RESERVATIONS", "false") != "true"

# Turn this to False if the agents are grouped and don't need demo mode instructions
DEMO_MODE: bool = True

SUBDIRECTORY: str = "generated/"


class PersistAgentNetwork(CodedTool):
    """
    CodedTool implementation which creates a persisted representation of a designed agent network
    from the agent network definition in sly data.

    Agent network definition is a structured representation of an agent network, expressed as a dictionary.
    Each key is an agent name, and its value is an object containing:
    - an instructions to the agent
    - a list of down-chain agents (agents reporting to it)
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "agent_network_name": the name of the agent network HOCON file.

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

        :return:
            In case of successful execution:
                The full agent network content as a string.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        logger = logging.getLogger(self.__class__.__name__)

        # Use copy here since we may have to rearrange the dictionary to get the correct frontman
        network_def: dict[str, Any] = deepcopy(sly_data.get(AGENT_NETWORK_DEFINITION))
        if not network_def:
            return "Error: No network in sly data!"

        # Validate the agent network and return error message if there are any issues.
        # Gather all external agents (subnetworks) into a list.
        subnetworks: dict[str, Any] | str = GetSubnetwork().invoke(None, None)
        if isinstance(subnetworks, dict):
            subnetworks: list[str] = list(subnetworks.keys())
        else:
            subnetworks = []

        error_list: list[str] = (
            StructureNetworkValidator().validate(network_def)
            + KeywordNetworkValidator().validate(network_def)
            + ToolboxNetworkValidator(GetToolbox().invoke(None, None)).validate(network_def)
            + UrlNetworkValidator(subnetworks, GetMcpTool().mcp_servers).validate(network_def)
        )
        if error_list:
            error_msg = f"Error: {error_list}"
            logger.error(error_msg)
            return error_msg

        # Get sample queries from args
        sample_queries: list[str] = args.get("sample_queries")

        # Get the agent network name from sly data
        the_agent_network_name: str = sly_data.get(AGENT_NETWORK_NAME)
        # Prepend subdirectory to the agent network name before persisting
        # if not already present.
        # This is needed for the NSflow launcher to connect to the right network.
        if not the_agent_network_name.startswith(SUBDIRECTORY):
            # Neuro-SAN only allows '/' as path separator in agent network names.
            the_agent_network_name = SUBDIRECTORY + the_agent_network_name
        sly_data[AGENT_NETWORK_NAME] = the_agent_network_name

        logger.info(">>>>>>>>>>>>>>>>>>>Create Agent Network>>>>>>>>>>>>>>>>>>")
        logger.info("Agent Network Name: %s", str(the_agent_network_name))
        # Get the persistor first, as that will determine how we want to assemble the agent network
        persistor: AgentNetworkPersistor = AgentNetworkPersistorFactory.create_persistor(
            args, WRITE_TO_FILE, DEMO_MODE
        )
        assembler: AgentNetworkAssembler = persistor.get_assembler()
        top_agent_name: str = UnreachableNodesNetworkValidator().find_all_top_agents(network_def).pop()
        persisted_content: str = assembler.assemble_agent_network(
            network_def, top_agent_name, the_agent_network_name, sample_queries
        )
        logger.info("The resulting agent network: \n %s", str(persisted_content))

        persisted_reference: str | list[dict[str, Any]] = await persistor.async_persist(
            obj=persisted_content, file_reference=the_agent_network_name
        )

        if isinstance(persisted_reference, list):
            sly_data["agent_reservations"] = persisted_reference

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return (
            f"The agent network file for {the_agent_network_name}"
            f"has been successfully created from the agent network definition: {network_def}."
        )
