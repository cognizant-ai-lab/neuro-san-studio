# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
import logging
from copy import deepcopy
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_designer.agent_network_assembler import AgentNetworkAssembler
from coded_tools.agent_network_designer.agent_network_persistor import AgentNetworkPersistor
from coded_tools.agent_network_designer.agent_network_persistor_factory import AgentNetworkPersistorFactory
from coded_tools.agent_network_designer.hocon_agent_network_assembler import HoconAgentNetworkAssembler
from coded_tools.agent_network_validator import AgentNetworkValidator

WRITE_TO_FILE = True
AGENT_NETWORK_DEFINITION = "agent_network_definition"
AGENT_NETWORK_NAME = "agent_network_name"


class CreateAgentNetworkHocon(CodedTool):
    """
    CodedTool implementation which creates a full hocon of a designed agent network
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
                The full agent network hocon as a string.
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
        validator = AgentNetworkValidator(network_def)
        error_list: list[str] = (
            validator.validate_network_structure()
            + validator.validate_network_keywords()
            + validator.validate_toolbox_agents()
            + validator.validate_url()
        )
        if error_list:
            error_msg = f"Error: {error_list}"
            logger.error(error_msg)
            return error_msg

        # Get the agent network name from sly data
        the_agent_network_name: str = sly_data.get(AGENT_NETWORK_NAME)

        logger.info(">>>>>>>>>>>>>>>>>>>Create Agent Network Hocon>>>>>>>>>>>>>>>>>>")
        logger.info("Agent Network Name: %s", str(the_agent_network_name))

        assembler: AgentNetworkAssembler = HoconAgentNetworkAssembler()
        the_agent_network_hocon_str: str = assembler.assemble_agent_network(
            validator.network, validator.get_top_agent(), the_agent_network_name
        )
        logger.info("The resulting agent network HOCON: \n %s", str(the_agent_network_hocon_str))

        persistor: AgentNetworkPersistor = AgentNetworkPersistorFactory.create_persistor(args, WRITE_TO_FILE)
        await persistor.async_persist(obj=the_agent_network_hocon_str, file_reference=the_agent_network_name)

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return (
            f"The agent network HOCON file for {the_agent_network_name}"
            f"has been successfully created from the agent network definition: {network_def}."
        )
