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
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.run_context.langchain.toolbox.toolbox_info_restorer import ToolboxInfoRestorer

from coded_tools.agent_network_editor.sly_data_lock import SlyDataLock


DEFAULT_TOOLBOX_INFO_FILE = os.path.join("toolbox", "agent_network_designer_toolbox_info.hocon")


class GetToolbox(CodedTool):
    """
    CodedTool implementation which provides a way to get tool definition from toolbox info file
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> dict[str, Any] | str:
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
        toolbox_info_file: str = os.getenv("AGENT_NETWORK_DESIGNER_TOOLBOX_INFO_FILE", DEFAULT_TOOLBOX_INFO_FILE)

        tools: dict[str, Any] | str = None
        async with SlyDataLock.get_lock(sly_data, "toolbox_info_lock"):
            # Try getting from sly_data
            tools = sly_data.get("toolbox_info")
            if tools is not None:
                # Return whatever we had cached before
                return tools

            # Go fish, but only once.
            logger.info(">>>>>>>>>>>>>>>>>>>Getting Tool Definition from Toolbox>>>>>>>>>>>>>>>>>>>")
            logger.info("Toolbox info file: %s", toolbox_info_file)
            try:
                # Need to do the load
                tools = await ToolboxInfoRestorer().async_restore(toolbox_info_file)
                logger.info("Successfully loaded the following toolbox: %s", str(tools))

                # Clean up the dict so that it only contains "description" key.
                for tool_name, tool_info in tools.items():
                    tools[tool_name] = tool_info.get("description", "")

            except FileNotFoundError as not_found_err:
                tools = f"Error: Failed to load toolbox info from {toolbox_info_file}. {str(not_found_err)}"
                logger.warning(tools)

            # Cache the results in sly_data - success or failure.
            sly_data["toolbox_info"] = tools

        return tools
