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
import os
from typing import Any

from langchain_core.tools import BaseTool
from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.run_context.langchain.mcp.langchain_mcp_adapter import LangChainMcpAdapter
from neuro_san.internals.run_context.langchain.mcp.mcp_clients_info_restorer import McpClientsInfoRestorer

# Use deepwiki MCP server as default since it is free and does not require authorization.
DEFAULT_MCP_INFO_FILE = os.path.join("mcp", "mcp_info.hocon")


class GetMcpTool(CodedTool):
    """
    CodedTool implementation which provides a way to get tool definition from given MCP servers
    """

    def __init__(self):
        if not os.getenv("MCP_CLIENTS_INFO_FILE"):
            os.environ["MCP_CLIENTS_INFO_FILE"] = DEFAULT_MCP_INFO_FILE
        restorer = McpClientsInfoRestorer()
        self.mcp_servers: list[str] = list(restorer.restore().keys())

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, list[BaseTool]] | str:
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
                the server name and tool definition from the server as a dictionary.
            otherwise:
                a text string of an error message in the format:
                "Error: <error message>"
        """
        logger = logging.getLogger(self.__class__.__name__)

        # Get tool list from MCP servers
        logger.info(">>>>>>>>>>>>>>>>>>>Getting Tool Definition from MCP Servers>>>>>>>>>>>>>>>>>>>")
        tool_dict: dict[str, list[BaseTool]] = {}
        for mcp_server in self.mcp_servers:
            try:
                logger.info("MCP Server: %s", mcp_server)
                tools: list[BaseTool] = await LangChainMcpAdapter().get_mcp_tools(mcp_server)
                logger.info("Successfully loaded the following tools: %s", str(tools))

                # Gather each tool's description into one string.
                tool_dict[mcp_server] = ""
                for tool in tools:
                    tool_dict[mcp_server] += tool.description + "\n"

            except ExceptionGroup as exception:
                error_msg = f"Error: Failed to load tools from {mcp_server}. {str(exception)}"
                logger.warning(error_msg)

        # Returns a dict with url as a key and combined descriptions of tools as a value.
        return str(tool_dict)
