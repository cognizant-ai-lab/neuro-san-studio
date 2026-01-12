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

from typing import Any

from coded_tools.agent_network_designer.agent_network_assembler import AgentNetworkAssembler

HOCON_HEADER_START = (
    "{\n"
    "# Importing content from other HOCON files\n"
    "# The include keyword must be unquoted and followed by a quoted URL or file path.\n"
    "# File paths should be absolute or relative to the script's working directory, not the HOCON file location.\n"
    '# This "aaosa.hocon" file contains key-value pairs used for substitution.\n'
    "# Specifically, it provides values for the following keys:\n"
    "#   - aaosa_call\n"
    "#   - aaosa_command\n"
    "#   - aaosa_instructions\n"
    "# IMPORTANT:\n"
    "# Ensure that you run `python -m run` from the top level of the repository.\n"
    "# The path to this substitution file is **relative to the top-level directory**,\n"
    "# so running the script from elsewhere may result in file not found errors.\n"
    '    include "registries/aaosa.hocon"\n'
    "# Optional metadata describing this agent network\n"
    '    "metadata": {\n'
    '        "sample_queries": [\n'
    "            %s\n"
    "        ]\n"
    "    },\n"
    '    "llm_config": {\n'
    '        "model_name": "gpt-4o",\n'
    "    },\n"
    '   "instructions_prefix": """\n'
    "You are part of a team of assistants in "
)
HOCON_HEADER_REMAINDER = (
    ".\n"
    "Only answer inquiries that are directly within your area of expertise.\n"
    "Do not try to help for other matters.\n"
    "Do not mention what you can NOT do. Only mention what you can do.\n"
    '""",\n'
    "%s"
    '   "tools": [\n'
)
TOP_AGENT_TEMPLATE = (
    "        {\n"
    '            "name": "%s",\n'
    '            "function": {\n'
    '                "description": """\n'
    "An assistant that answer inquiries from the user.\n"
    '                """\n'
    "            },\n"
    '            "instructions": ${instructions_prefix} """\n'
    "            Never express irrelevance unless you have first consulted all your tools.\n"
    "            Once you have determined the relevant tools, do not express that to the user, rather,\n"
    "            call all the relevant tools and make sure the command is fully serviced and express the end result.\n"
    "%s\n"
    '""" ${aaosa_instructions},\n'
    '            "tools": [%s]\n'
    "        },\n"
)
REGULAR_AGENT_TEMPLATE = (
    "        {\n"
    '            "name": "%s",\n'
    '            "function": ${aaosa_call},\n'
    '            "instructions": ${instructions_prefix} """\n'
    "%s\n"
    '""" ${aaosa_instructions},\n'
    '            "command": ${aaosa_command},\n'
    '            "tools": [%s]\n'
    "        },\n"
)
LEAF_NODE_AGENT_TEMPLATE = (
    "        {\n"
    '            "name": "%s",\n'
    '            "function": ${aaosa_call},\n'
    '            "instructions": ${instructions_prefix} %s """\n'
    "%s\n"
    '""",\n'
    "        },\n"
)
# pylint: disable=implicit-str-concat
TOOLBOX_AGENT_TEMPLATE = "        {\n" '            "name": "%s",\n' '            "toolbox": "%s"\n' "        },\n"


# pylint: disable=too-few-public-methods
class HoconAgentNetworkAssembler(AgentNetworkAssembler):
    """
    AgentNetworkAssembler implementation which creates a full hocon of a designed agent network
    from the agent network definition in sly data.

    Agent network definition is a structured representation of an agent network, expressed as a dictionary.
    Each key is an agent name, and its value is an object containing:
    - an instructions to the agent
    - a list of down-chain agents (agents reporting to it)
    """

    def __init__(self, demo_mode: bool):
        """
        Constructor

        :param demo_mode: Whether to include demo mode instructions for agents
        """
        self.demo_mode: bool = demo_mode

    def assemble_agent_network(
        self, network_def: dict[str, Any], top_agent_name: str, agent_network_name: str, sample_queries: list[str]
    ) -> str:
        """
        Substitutes value from agent network definition into the template of agent network HOCON file

        :param network_def: Agent network definition
        :param top_agent_name: The name of the top agent
        :param agent_network_name: The file name, without the .hocon extension
        :param sample_queries: List of sample queries for the agent network

        :return: A full agent network HOCON as a string.
        """
        network_def = self._move_top_agent_first(network_def, top_agent_name)

        header = self._build_header(agent_network_name, sample_queries)

        body = []
        for agent_name, agent in network_def.items():
            body.append(self._render_agent_block(agent_name, agent, top_agent_name))

        return header + "".join(body) + "]\n}\n"

    def _move_top_agent_first(self, network_def: dict[str, Any], top_agent_name: str) -> dict[str, Any]:
        """
        Ensure the top agent is the first item in the ordered dict.

        :param network_def: Agent network definition
        :param top_agent_name: The name of the top agent

        :return: Updated network definition with top agent first.
        """
        if top_agent_name != next(iter(network_def)):
            top_agent = network_def.pop(top_agent_name)
            return {top_agent_name: top_agent, **network_def}
        return network_def

    def _format_sample_queries(self, sample_queries: list[str]) -> str:
        """
        Format sample queries as HOCON list elements.

        :param sample_queries: List of sample queries for the agent network

        :return: Formatted sample queries as a string.
        """
        formatted_queries = ""
        if sample_queries:
            parts = []
            for query in sample_queries:
                parts.append(f'"{query}"')
            formatted_queries = ",\n            ".join(parts)
        return formatted_queries

    def _build_header(self, agent_network_name: str, sample_queries: list[str]) -> str:
        """
        Build the header of the HOCON agent network file.

        :param agent_network_name: The file name, without the .hocon extension
        :param sample_queries: List of sample queries for the agent network

        :return: The header of the HOCON agent network file as a string.
        """
        formatted_queries = self._format_sample_queries(sample_queries)

        demo_mode_block = (
            '   "demo_mode": "You are part of a demo system, so when queried, make up a realistic '
            "response as if you are actually grounded in real data or you are operating a real "
            'application API or microservice.",\n'
            if self.demo_mode
            else ""
        )

        return HOCON_HEADER_START % formatted_queries + agent_network_name + HOCON_HEADER_REMAINDER % demo_mode_block

    def _render_agent_block(self, agent_name: str, agent: dict[str, Any], top_agent_name: str) -> str:
        """
        Render a single agent block depending on its type.

        :param agent_name: The name of the agent
        :param agent: The agent definition
        :param top_agent_name: The name of the top agent

        :return: The rendered agent block as a string.
        """
        tools = self._format_tools(agent.get("tools", []))

        if agent_name == top_agent_name:
            return TOP_AGENT_TEMPLATE % (agent_name, agent["instructions"], tools)

        if agent.get("tools"):
            return REGULAR_AGENT_TEMPLATE % (agent_name, agent["instructions"], tools)

        if agent.get("instructions"):
            demo_prefix = "${demo_mode}" if self.demo_mode else ""
            return LEAF_NODE_AGENT_TEMPLATE % (agent_name, demo_prefix, agent["instructions"])

        return TOOLBOX_AGENT_TEMPLATE % (agent_name, agent_name)

    def _format_tools(self, tools: list[str]) -> str:
        """
        Format a list of tool names into a HOCON array string.

        :param tools: List of tool names

        :return: Formatted tools as a string.
        """
        return ", ".join(f'"{t}"' for t in tools)
