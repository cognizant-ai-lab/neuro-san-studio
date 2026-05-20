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

import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.run_context.langchain.mcp.langchain_mcp_adapter import LangChainMcpAdapter
from neuro_san.internals.run_context.langchain.mcp.mcp_servers_info_restorer import McpServersInfoRestorer

from coded_tools.agent_network_editor.constants import MCP_SERVERS
from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock
from neuro_san_studio import mcp as _mcp_pkg

# Path to the mcp_info.hocon shipped inside the neuro_san_studio package.
# Resolved via the imported package's __file__ so it works both in-repo and
# after `pip install` on every platform. Mirrors run.py.
BUNDLED_MCP_INFO_FILE: Path = Path(_mcp_pkg.__file__).parent / "mcp_info.hocon"
logger = logging.getLogger(__name__)


class GetMcpTool(CodedTool):
    """
    CodedTool implementation which provides a way to get tool definition from given MCP servers
    """

    # TODO: This duplicates NeuroSanRunner._resolve_mcp_info_file in
    # neuro_san_studio/commands/run.py. Refactor so run.py calls this method
    # instead of maintaining its own copy.
    @staticmethod
    def get_mcp_info_file() -> str:
        """Resolve the mcp_info.hocon path at call time.

        Precedence (mirrors NeuroSanRunner._resolve_mcp_info_file):
          1. MCP_SERVERS_INFO_FILE env var (used verbatim if non-empty).
          2. <cwd>/mcp/mcp_info.hocon if it exists (what `init` scaffolds).
          3. The mcp_info.hocon bundled in the neuro_san_studio package.
        """
        env_value = os.getenv("MCP_SERVERS_INFO_FILE")
        if env_value:
            return env_value
        scaffolded = Path.cwd() / "mcp" / "mcp_info.hocon"
        if scaffolded.is_file():
            return str(scaffolded)
        return str(BUNDLED_MCP_INFO_FILE)

    @staticmethod
    async def get_mcp_servers(sly_data: dict[str, Any]) -> list[str]:
        """
        Read the MCP servers associated with this instance
        either from a cache on sly_data or from a file.

        :param sly_data: sly_data possibly containing cached mcp_servers info
        :return: list of MCP servers
        """
        mcp_servers: list[str] = []

        async with await SlyDataLock.get_lock(sly_data, "mcp_servers_lock"):
            # Try getting from sly_data
            if MCP_SERVERS in sly_data:
                # Exit early, including when the cached value is an empty list
                return sly_data.get(MCP_SERVERS)

            use_mcp_info_file: str = GetMcpTool.get_mcp_info_file()

            # Try to restore
            mcp_servers_from_file: dict[str, Any] = {}
            try:
                restorer = McpServersInfoRestorer()
                mcp_servers_from_file = await restorer.async_restore(file_reference=use_mcp_info_file)
            except FileNotFoundError:
                logger.warning(
                    "MCP servers info file not found at %s. No MCP Servers will be used.", use_mcp_info_file
                )

            mcp_servers = list(mcp_servers_from_file.keys())
            sly_data[MCP_SERVERS] = mcp_servers

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
        logger.info(">>>>>>>>>>>>>>>>>>>Getting Tool Definition from MCP Servers>>>>>>>>>>>>>>>>>>>")

        async with await SlyDataLock.get_lock(sly_data, "tool_dict_lock"):
            if "tool_dict" not in sly_data:
                # tool_dict is a dict with urls as keys and combined descriptions of tools as a values.
                tool_dict: dict[str, str] = {}
                mcp_servers: list[str] = await self.get_mcp_servers(sly_data)
                for mcp_server in mcp_servers:
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

                # Stash a string representation of the tool_dict
                sly_data["tool_dict"] = str(tool_dict)

        # Return the cached tool_dict
        return sly_data["tool_dict"]
