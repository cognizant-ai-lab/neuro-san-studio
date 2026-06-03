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

"""
CodedTool that calls the Confidence Assessment MCP server.

Demonstrates how any agent network can assess answer confidence
by connecting to the MCP server over streamable HTTP — no local
GPU or model dependencies required.
"""

from typing import Any
from typing import Dict

from langchain_mcp_adapters.client import MultiServerMCPClient
from neuro_san.interfaces.coded_tool import CodedTool


class ConfidenceChecker(CodedTool):
    """
    CodedTool that assesses answer confidence via the MCP server.

    Connects to the ConfidenceAssessment MCP server and invokes
    the assess_confidence tool. The MCP server handles all GPU
    inference — this coded tool only needs network access.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Assess confidence for a question via the MCP server.

        :param args: Dictionary with:
            - "question" (str, required): The question to evaluate.
        :param sly_data: Out-of-band data (unused by this tool).
        :return: Confidence assessment result or error message.
        """
        question = args.get("question")
        if not question:
            return "Error: No question provided."

        client = MultiServerMCPClient(
            {
                "confidence": {
                    "url": "http://localhost:8100/mcp/",
                    "transport": "streamable_http",
                }
            }
        )

        tools = await client.get_tools()
        return await tools[0].ainvoke({"question": question})
