# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
import asyncio
import logging
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool

AGENT_NETWORK_DEFINITION = "agent_network_definition"


class SetAgentInstructions(CodedTool):
    """
    CodedTool implementation which creates or modifies the instructions of an agent
    of an agent network definition in sly data.

    Agent network definition is a structured representation of an agent network, expressed as a dictionary.
    Each key is an agent name, and its value is an object containing:
    - an instructions to the agent
    - a list of down-chain agents (agents reporting to it)
    """

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "agent_name": the name of the agent to update instructions.
                    "new_instructions": the new value of instructions.

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
                a text string indicating the new value of "instructions" of the agent.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        network_def: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        if not network_def:
            return "Error: No network in sly data!"

        the_agent_name: str = args.get("agent_name")
        if not the_agent_name:
            return "Error: No agent_name provided."
        if the_agent_name not in network_def:
            return f"Error: Agent not found: {the_agent_name}"

        new_instructions: str = args.get("new_instructions")
        if not new_instructions:
            return "Error: No agent instructions provided."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>Set Agent Instructions>>>>>>>>>>>>>>>>>>")
        logger.info("Agent Name: %s", the_agent_name)
        logger.info("Instructions: %s", new_instructions)
        network_def[the_agent_name]["instructions"] = new_instructions
        logger.info("The resulting agent network: \n %s", str(network_def))
        sly_data[AGENT_NETWORK_DEFINITION] = network_def
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return network_def

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
