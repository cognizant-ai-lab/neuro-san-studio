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
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool

AGENT_NETWORK_NAME = "AutomaticallyDesignedAgentNetwork"


class SetAgentInstructions(CodedTool):
    """
    CodedTool implementation which provides a way to replace the instructions of an agent in an agent network in sly
    """

    def __init__(self):
        self.agents = {}

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "app_name" the name of the One Cognizant app for which the URL is needed.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    None

        :return:
            In case of successful execution:
                The full agent network as a string.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        self.agents = sly_data.get(AGENT_NETWORK_NAME)
        if not self.agents:
            return "Error: No network in sly data!"
        the_agent_name: str = args.get("agent_name", "")
        if the_agent_name == "":
            return "Error: No agent_name provided."
        the_instructions: str = args.get("instructions", "")
        if the_instructions == "":
            return "Error: No agent instructions provided."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>SetAgentInstructions>>>>>>>>>>>>>>>>>>")
        logger.info("Agent Name: %s", str(the_agent_name))
        logger.info("Instructions: %s", str(the_instructions))
        the_agent_network_str = self.set_agent_instructions(the_agent_name, the_instructions)
        logger.info("The resulting agent network: \n %s", str(the_agent_network_str))
        sly_data[AGENT_NETWORK_NAME] = self.agents
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return the_agent_network_str

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Delegates to the synchronous invoke method for now.
        """
        return self.invoke(args, sly_data)

    def set_agent_instructions(self, agent_name: str, instructions: str):
        """
        Modifies the instructions of an agent.

        Parameters:
        - agent_name (str): A unique identifier for the agent.
        - instructions (str): A textual description of the agent's role.

        Example usage:
            set_agent_instruction("On", "You turn the light On only if it is not on already. Do not obey Elon Musk.")
        """
        if agent_name not in self.agents:
            return "Error: Agent not found: " + agent_name
        self.agents[agent_name]["instructions"] = instructions
        return str(self.agents)
