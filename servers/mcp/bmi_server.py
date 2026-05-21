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

"""Example of MCP server"""

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("BMI", port=8000)


# langchain-mcp-adapter only support mcp tools but not resources or prompts.
# Function's name, docstring, and argument annotation are converted to
# attribute `nanme`, `description`, and `args_schema`, respectively.
@mcp.tool()
def calculate_bmi(weight: float, height: float) -> float:
    """Calculate BMI given weight in kg and height in meters"""
    return weight / (height ** 2)


if __name__ == "__main__":
    # streamable http is prefered over stdio as transport method.
    mcp.run(transport="streamable-http")
