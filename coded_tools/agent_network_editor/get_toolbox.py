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
import os
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.run_context.langchain.toolbox.toolbox_info_restorer import ToolboxInfoRestorer

DEFAULT_TOOLBOX_INFO_FILE = os.path.join("toolbox", "toolbox_info.hocon")


class GetToolbox(CodedTool):
    """
    CodedTool implementation which provides a way to get tool definition from toolbox info file
    """

    def invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
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
                    None

        :return:
            In case of successful execution:
                the tool definition from toolbox as a dictionary.
            otherwise:
                a text string of an error message in the format:
                "Error: <error message>"
        """
        logger = logging.getLogger(self.__class__.__name__)
        toolbox_info_file: str = os.getenv("AGENT_TOOLBOX_INFO_FILE", DEFAULT_TOOLBOX_INFO_FILE)
        try:
            logger.info(">>>>>>>>>>>>>>>>>>>Getting Tool Definition from Toolbox>>>>>>>>>>>>>>>>>>>")
            logger.info("Toolbox info file: %s", toolbox_info_file)
            tools: dict[str, Any] = ToolboxInfoRestorer().restore(toolbox_info_file)
            logger.info("Successfully loaded the following toolbox: %s", str(tools))

            # Clean up the dict so that it only contains "description" key.
            for tool_name, tool_info in tools.items():
                tools[tool_name] = tool_info.get("description", "")

            return tools
        except FileNotFoundError as not_found_err:
            error_msg = f"Error: Failed to load toolbox info from {toolbox_info_file}. {str(not_found_err)}"
            logger.warning(error_msg)
            return error_msg

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
        """Run invoke asynchronously."""
        return await asyncio.to_thread(self.invoke, args, sly_data)
