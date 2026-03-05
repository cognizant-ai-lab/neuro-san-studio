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

from asyncio import Lock
import logging
import os
from typing import Any

from langchain_core.tools import BaseTool
from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.run_context.langchain.mcp.langchain_mcp_adapter import LangChainMcpAdapter
from neuro_san.internals.run_context.langchain.mcp.mcp_servers_info_restorer import McpServersInfoRestorer

from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock


class GetMcpTool(CodedTool):
    """
    CodedTool implementation which provides a way to get tool definition from given MCP servers
    """

    # Use deepwiki MCP server as default since it is free and does not require authorization.
    DEFAULT_MCP_INFO_FILE = os.path.join("mcp", "mcp_info.hocon")

    def __init__(self):
        """
        Constructor
        """
        # Initialize a logger
        self.logger = logging.getLogger(self.__class__.__name__)

    async def get_mcp_servers(self, sly_data: dict[str, Any]) -> list[str]:
        """
        Read the MCP servers associated with this instance
        either from a cache on sly_data or from a file.

        :param sly_data: sly_data possibly containing cached mcp_servers info
        :return: list of MCP servers
        """
        mcp_servers: list[str] = None

        async with SlyDataLock.get_lock(sly_data, "mcp_servers_lock"):
            # Try getting from sly_data
            mcp_servers = sly_data.get("mcp_servers")
            if mcp_servers is not None:
                # Exit early
                return mcp_servers

            # Check for MCP servers info file in env var
            use_mcp_info_file: str = os.getenv("MCP_SERVERS_INFO_FILE")
            if not use_mcp_info_file:
                # Use a default if no value specified
                use_mcp_info_file = self.DEFAULT_MCP_INFO_FILE

            # Try to restore
            mcp_servers_from_file: dict[str, Any] = {}
            try:
                # DEF - make this an async fileio read
                restorer = McpServersInfoRestorer()
                mcp_servers_from_file = restorer.restore(file_reference=use_mcp_info_file)
            except FileNotFoundError:
                self.logger.warning(
                    "MCP servers info file not found at %s. No MCP Servers will be used.", use_mcp_info_file
                )

            mcp_servers = list(mcp_servers_from_file.keys())
            if sly_data is not None:
                sly_data["mcp_servers"] = mcp_servers

        return mcp_servers

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
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

        # Get tool list from MCP servers
        self.logger.info(">>>>>>>>>>>>>>>>>>>Getting Tool Definition from MCP Servers>>>>>>>>>>>>>>>>>>>")

        async with SlyDataLock.get_lock(sly_data, "tool_dict_lock"):
            if not "tool_dict" in sly_data:
                # tool_dict is a dict with urls as keys and combined descriptions of tools as a values.
                tool_dict: dict[str, list[BaseTool]] = {}
                mcp_servers: list[str] = await self.get_mcp_servers(sly_data)
                for mcp_server in mcp_servers:
                    try:
                        self.logger.info("MCP Server: %s", mcp_server)
                        tools: list[BaseTool] = await LangChainMcpAdapter().get_mcp_tools(mcp_server)
                        self.logger.info("Successfully loaded the following tools: %s", str(tools))

                        # Gather each tool's description into one string.
                        tool_dict[mcp_server] = ""
                        for tool in tools:
                            tool_dict[mcp_server] += tool.description + "\n"

                    except ExceptionGroup as exception:
                        error_msg = f"Error: Failed to load tools from {mcp_server}. {str(exception)}"
                        self.logger.warning(error_msg)

                # Stash a string representation of the tool_dict
                sly_data["tool_dict"] = str(tool_dict)

        # Return the cached tool_dict
        return sly_data["tool_dict"]
