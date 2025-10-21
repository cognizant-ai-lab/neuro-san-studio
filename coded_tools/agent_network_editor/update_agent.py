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


class UpdateAgent(CodedTool):
    """
    CodedTool implementation which updates the down-chained agent list for an agent in the agent network definition
    in the sly data.

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
                     "agent_name": the name of the agent to update.
                     "new_down_chains": the new value of down_chains.

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
                 the agent network definition as a dictionary.
             otherwise:
                 a text string of an error message in the format:
                 "Error: <error message>"
        """
        network_def: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        if not network_def:
            return "Error: No network in sly data!"

        the_agent_name: str = args.get("agent_name")
        if not the_agent_name:
            return "Error: No agent_name provided."
        if the_agent_name not in network_def:
            return "Error: agent_name not in the agent network"

        new_down_chains: list[str] = args.get("new_down_chains")
        if new_down_chains is None:
            return "Error: No down chains list provided."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>Update Agent Network Definiton>>>>>>>>>>>>>>>>>>")
        logger.info("Agent Name: %s", str(the_agent_name))
        logger.info("Down Chain Agents: %s", str(new_down_chains))
        network_def[the_agent_name]["tools"] = new_down_chains
        logger.info("The resulting agent network definition: \n %s", str(network_def))
        sly_data[AGENT_NETWORK_DEFINITION] = network_def

        # Report progress
        progress_reporter: AgentProgressReporter = args.get("progress_reporter")
        progress: dict[str, Any] = {
            # Agent network definition with an updated agent
            AGENT_NETWORK_DEFINITION: network_def
        }
        await progress_reporter.async_report_progress(progress)

        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return network_def
