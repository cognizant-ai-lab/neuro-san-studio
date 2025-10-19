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

from coded_tools.agent_network_validator import AgentNetworkValidator

AGENT_NETWORK_DEFINITION = "agent_network_definition"


class ValidateInstructions(CodedTool):
    """
    CodedTool implementation which validates the instructions of the agent network
    to ensure that each non-tool agent has it.
    """

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    None

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
                a text string indicating there is no error.
            otherwise:
                a text string of an error message in the format:
                "Error: <error message>"
        """
        logger = logging.getLogger(self.__class__.__name__)

        network_def: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        if not network_def:
            return "Error: No network in sly data!"

        logger.info(">>>>>>>>>>>>>>>>>>>Validate Agent Network Instructions>>>>>>>>>>>>>>>>>>")
        # Validate the agent network and return error message if there are any issues.
        validator = AgentNetworkValidator(network_def)
        error_list: list[str] = validator.validate_network_keywords()
        if error_list:
            error_msg = f"Error: {error_list}"
            logger.error(error_msg)
            return error_msg

        success_msg = "No error found."
        logger.info(success_msg)
        return success_msg

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
