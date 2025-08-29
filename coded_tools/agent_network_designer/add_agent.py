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
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

AGENT_NETWORK_NAME = "AutomaticallyDesignedAgentNetwork"


class AddAgent(CodedTool):
    """
    CodedTool implementation which provides a way to add an agent to an agent network and store in sly data
    """

    def __init__(self):
        self.agents = None

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
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
            self.agents = {}
        the_agent_name: str = args.get("agent_name", "")
        if the_agent_name == "":
            return "Error: No agent_name provided."
        the_instructions: str = args.get("instructions", "")
        if the_instructions == "":
            return "Error: No agent instructions provided."
        the_top_agent: bool = args.get("top_agent", False)

        the_down_chains: list[str] = args.get("down_chains", [])
        # the_down_chains = []
        # if the_down_chains_input != "":
        #     # Convert the_down_chains_input into a list if it's a string.
        #     if isinstance(the_down_chains_input, str):
        #         # Assuming the string is comma-separated (e.g. "On, Off"),
        #         # we split it and remove any extra whitespace.
        #         the_down_chains = [chain.strip() for chain in the_down_chains_input.split(",") if chain.strip()]
        #     else:
        #         # If it's already a list, just use it.
        #         the_down_chains = the_down_chains_input

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>AddAgent>>>>>>>>>>>>>>>>>>")
        logger.info("Agent Name: %s", str(the_agent_name))
        logger.info("Instructions: %s", str(the_instructions))
        logger.info("Down Chain Agents: %s", str(the_down_chains))
        logger.info("Top Agent?: %s", str(the_top_agent))
        the_agent_network_str = self.add_agent(the_agent_name, the_instructions, the_down_chains, the_top_agent)
        logger.info("The resulting agent network: \n %s", str(the_agent_network_str))
        sly_data[AGENT_NETWORK_NAME] = self.agents
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return the_agent_network_str

    def add_agent(self, agent_name: str, instructions: str, down_chains: list[str], top_agent: bool) -> str:
        """
        Adds an agent to the hierarchy.

        Parameters:
        - agent_name (str): A unique identifier for the agent.
        - instructions (str): A textual description of the agent's role.
        - down_chains (list): A list of agent keys representing the children of this agent.
        - top_agent (str): A textual indication of whether the agent is the top agent.

        Example usage:
            add_agent("light", "You are a light", ["On", "Off"], True)
            add_agent("On", "You turn the light on", [], False)
            add_agent("Off", "You turn the light off", [], False)
        """
        self.agents[agent_name] = {
            "instructions": instructions,
            "down_chains": down_chains,
            "top_agent": top_agent,
        }
        return str(self.agents[agent_name])
