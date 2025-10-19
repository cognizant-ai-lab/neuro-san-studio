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

from neuro_san.interfaces.agent_progress_reporter import AgentProgressReporter
from neuro_san.interfaces.coded_tool import CodedTool

AGENT_NETWORK_DEFINITION = "agent_network_definition"
AGENT_NETWORK_NAME = "agent_network_name"


class CreateNetwork(CodedTool):
    """
    CodedTool implementation which creates an agent network definition with agent name as key
    and empty dictionary as value then store in sly data.

    Note that if there exists an agent network definition in the sly data, it will be reset and overwritten.

    Agent network definition is a structured representation of an agent network, expressed as a dictionary.
    Each key is an agent name, and its value is an object containing:
    - a description of the agent
    - an instructions to the agent
    - a list of down-chain agents (agents reporting to it)
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "agent_names": list of the names of the agents in the network
                    "is_tool_list": list of booleans indicating whether each agent is a function or not.
                        Must be the same length as agent_names.

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
                the agent network definition as a dictionary.
            otherwise:
                a text string of an error message in the format:
                "Error: <error message>"
        """
        sly_data[AGENT_NETWORK_DEFINITION] = {}
        agent_network_name: str = args.get("agent_network_name")
        if not agent_network_name:
            return "Error: No agent_network_name provided."
        agent_names: list[str] = args.get("agent_names")
        if not agent_names:
            return "Error: No agent_names provided."
        is_tool_list: list[bool] = args.get("is_tool_list")
        if not is_tool_list:
            return "Error: No is_tool_list provided."
        if len(agent_names) != len(is_tool_list):
            return "Error: The length of agent_names and is_tool_list must be the same."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>Create New Agent Netwrok Definiton for %s>>>>>>>>>>>>>>>>>", agent_network_name)
        for i, agent_name in enumerate(agent_names):
            logger.info(">>>>>>>>>>>>>>>>>>>Adding Agent>>>>>>>>>>>>>>>>>>")
            logger.info("Agent Name: %s", agent_name)
            logger.info("Is Tool: %s", str(is_tool_list[i]))
            sly_data[AGENT_NETWORK_DEFINITION][agent_name] = {}
            if not is_tool_list[i]:
                sly_data[AGENT_NETWORK_DEFINITION][agent_name]["instructions"] = ""
        logger.info("The resulting agent network definition: \n %s", str(sly_data[AGENT_NETWORK_DEFINITION]))

        # Put the agent network name in the sly data
        sly_data[AGENT_NETWORK_NAME] = agent_network_name

        # Report progress
        progress_reporter: AgentProgressReporter = args.get("progress_reporter")
        progress: dict[str, Any] = {
            # Agent network definition with added agents
            AGENT_NETWORK_DEFINITION: sly_data[AGENT_NETWORK_DEFINITION],
            AGENT_NETWORK_NAME: sly_data[AGENT_NETWORK_NAME]
        }
        await progress_reporter.async_report_progress(progress)

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return sly_data[AGENT_NETWORK_DEFINITION]
