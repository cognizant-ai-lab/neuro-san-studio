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
"""Example of how to use tools from mcp server"""

from typing import Any
from typing import Dict

from langchain_mcp_adapters.client import MultiServerMCPClient
from neuro_san.interfaces.coded_tool import CodedTool


class BmiCalculator(CodedTool):
    """
    CodedTool implementation which calculates BMI using a tool from mcp server
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> float:
        """
        Calculate BMI.

        :param args: Dictionary containing 'weight' and 'height'.
        :param sly_data: A dictionary whose keys are defined by the agent
            hierarchy, but whose values are meant to be kept out of the
            chat stream.

            This dictionary is largely to be treated as read-only.
            It is possible to add key/value pairs to this dict that do not
            yet exist as a bulletin board, as long as the responsibility
            for which coded_tool publishes new entries is well understood
            by the agent chain implementation and the coded_tool implementation
            adding the data is not invoke()-ed more than once.

            Keys expected for this implementation are:
                None
        :return: BMI or error message
        """
        # Extract arguments from the input dictionary
        weight: str = args.get("weight")
        height: str = args.get("height")

        if not weight:
            return "Error: No weight provided."

        if not height:
            return "Error: No height provided."

        # neuro-san uses langchain-mcp-adapter to create mcp client
        # In this example, there is only 1 server at localhost:8000
        # however, client can be connected to multiple servers,
        # and a server can also have multiple tools.
        # Note that mcp server can contain tools, resources, and prompts
        # but langchain-mcp-adapter only works with **tools**.
        client = MultiServerMCPClient(
            {
                # This key only used as a reference here and may be different
                # from the actual name in mcp server.
                "bmi": {
                    # streamable_http is preferred over stdio as transport method.
                    # make sure the port here matches the one in your server.
                    "url": "http://localhost:8000/mcp/",
                    "transport": "streamable_http",
                }
            }
        )

        # `get_tools` method returns a list of StructuredTool ordered by
        # server and tool's order in the server, respectively.
        # In this example, there is only one server and one tool in the server.
        tools = await client.get_tools()

        # Note that to `invoke` or `ainvoke` for StructureTool require
        # dictionary input.
        return await tools[0].ainvoke({"weight": weight, "height": height})
