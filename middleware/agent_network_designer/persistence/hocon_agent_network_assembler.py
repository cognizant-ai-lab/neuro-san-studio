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

import datetime
import json
from collections.abc import Collection
from collections.abc import Mapping
from copy import copy as shallow_copy
from typing import Any

from coded_tools.agent_network_editor.constants import MIDDLEWARE_KEY
from middleware.agent_network_designer.persistence.agent_network_assembler import AgentNetworkAssembler

HOCON_HEADER_START = (
    "{\n"
    "# Importing content from other HOCON files\n"
    "# The include keyword must be unquoted and followed by a quoted URL or file path.\n"
    "# File paths should be absolute or relative to the script's working directory, not the HOCON file location.\n"
    '# This "aaosa.hocon" file contains key-value pairs used for substitution.\n'
    "# Specifically, it provides values for the following keys:\n"
    "#   - aaosa_call\n"
    "#   - aaosa_instructions\n"
    "# IMPORTANT:\n"
    "# Ensure that you run `python -m neuro_san_studio run` from the top level of the repository.\n"
    "# The path to this substitution file is **relative to the top-level directory**,\n"
    "# so running the script from elsewhere may result in file not found errors.\n"
    '    include "registries/aaosa.hocon"\n'
    "\n"
    "# Optional metadata describing this agent network\n"
    '    "metadata": {\n'
    '        "sample_queries": [\n'
    "            %s\n"
    "        ],\n"
    '        "date_created": "%s"\n'
    "    },\n"
    "\n"
    "# Load the shared LLM configuration from a single source of truth.\n"
    "# This allows users to change the model in one file rather than\n"
    "# modifying the configuration for each agent network.\n"
    "# Note that the file path here is relative to the root level of the repo.\n"
    '    include "config/llm_config.hocon",\n'
    "\n"
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
    '            "function": ${aaosa_call}{\n'
    '                "description": """\n'
    "%s\n"
    # The slot after the closing triple quotes takes the optional
    # sly_data_schema block (see _render_sly_data_schema_block), which
    # starts with the separating comma when present.
    '                """%s\n'
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
    '            "function": ${aaosa_call}{\n'
    '                "description": """\n'
    "%s\n"
    '                """\n'
    "            },\n"
    '            "instructions": ${instructions_prefix} """\n'
    "%s\n"
    '""" ${aaosa_instructions},\n'
    '            "tools": [%s]\n'
    "        },\n"
)
LEAF_NODE_AGENT_TEMPLATE = (
    "        {\n"
    '            "name": "%s",\n'
    '            "function": ${aaosa_call}{\n'
    '                "description": """\n'
    "%s\n"
    '                """\n'
    "            },\n"
    '            "instructions": ${instructions_prefix} %s """\n'
    "%s\n"
    '""",\n'
    "        },\n"
)
# fmt: off
# pylint: disable=implicit-str-concat
TOOLBOX_AGENT_TEMPLATE = "        {\n" '            "name": "%s",\n' '            "toolbox": "%s"\n' "        },\n"
# fmt: on


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

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    async def assemble_agent_network(
        self,
        network_def: dict[str, Any],
        top_agent_name: str,
        agent_network_name: str,
        sample_queries: list[str],
        client_token_mcp_headers: Mapping[str, Collection[str]] | None = None,
    ) -> str:
        """
        Substitutes value from agent network definition into the template of agent network HOCON file

        :param network_def: Agent network definition
        :param top_agent_name: The name of the top agent
        :param agent_network_name: The file name, without the .hocon extension
        :param sample_queries: List of sample queries for the agent network
        :param client_token_mcp_headers: Optional mapping of client-token MCP
                server URL to the header names the conversation supplied for it,
                driving the front man's sly_data_schema (see the base class)

        :return: A full agent network HOCON as a string.
        """
        use_network_def: dict[str, Any] = shallow_copy(network_def)
        use_network_def = self._move_top_agent_first(use_network_def, top_agent_name)

        header: str = self._build_header(agent_network_name, sample_queries)

        sly_data_schema_block: str = self._render_sly_data_schema_block(
            self.build_mcp_sly_data_schema(use_network_def, client_token_mcp_headers)
        )

        body: list[str] = []
        for agent_name, agent in use_network_def.items():
            body.append(self._render_agent_block(agent_name, agent, top_agent_name, sly_data_schema_block))

        return header + "".join(body) + "    ]\n}\n"

    def _move_top_agent_first(self, network_def: dict[str, Any], top_agent_name: str) -> dict[str, Any]:
        """
        Ensure the top agent is the first item in the ordered dict.

        :param network_def: Agent network definition
        :param top_agent_name: The name of the top agent

        :return: Updated network definition with top agent first.
        """
        if top_agent_name != next(iter(network_def)):
            top_agent: dict[str, Any] = network_def.pop(top_agent_name)
            return {top_agent_name: top_agent, **network_def}
        return network_def

    def _format_sample_queries(self, sample_queries: list[str]) -> str:
        """
        Format sample queries as HOCON list elements.

        :param sample_queries: List of sample queries for the agent network

        :return: Formatted sample queries as a string.
        """
        formatted_queries: str = ""
        if sample_queries:
            parts: list[str] = []
            for query in sample_queries:
                # Put each query in triple quotes to allow for multi-line queries and
                # to avoid issues with special characters.
                parts.append(f'"""{query}"""')
            formatted_queries = ",\n            ".join(parts)
        return formatted_queries

    def _build_header(self, agent_network_name: str, sample_queries: list[str]) -> str:
        """
        Build the header of the HOCON agent network file.

        :param agent_network_name: The file name, without the .hocon extension
        :param sample_queries: List of sample queries for the agent network

        :return: The header of the HOCON agent network file as a string.
        """
        formatted_queries: str = self._format_sample_queries(sample_queries)
        date_created: str = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        demo_mode_block: str = (
            '   "demo_mode": "You are part of a demo system, so when queried, make up a realistic '
            "response as if you are actually grounded in real data or you are operating a real "
            'application API or microservice.",\n'
            if self.demo_mode
            else ""
        )

        return (
            HOCON_HEADER_START % (formatted_queries, date_created)
            + agent_network_name
            + HOCON_HEADER_REMAINDER % demo_mode_block
        )

    @staticmethod
    def _render_sly_data_schema_block(schema: dict[str, Any] | None) -> str:
        """
        Render the front man's sly_data_schema as a HOCON fragment for the
        TOP_AGENT_TEMPLATE slot that follows the description's closing
        triple quotes.

        :param schema: The schema dict from build_mcp_sly_data_schema, or None

        :return: "" when there is no schema (leaving the template output
                unchanged), else a block starting with the comma that
                separates it from the description entry. JSON is valid
                HOCON, and the fragment always parses as written because
                json.dumps keeps every key and value double-quoted and
                HOCON performs no ${...} substitution inside double-quoted
                strings (json.dumps does NOT escape $ or { — a URL
                containing ${...} survives verbatim, safely, only thanks to
                the quoting). ensure_ascii=False keeps a non-ASCII URL key
                as its raw character: pyhocon does not decode \\uXXXX
                escapes, so an escaped key would read back as literal text
                that no longer matches the raw URL in the tools list.
        """
        if not schema:
            return ""
        indent: str = " " * 16
        lines: list[str] = json.dumps(schema, indent=4, ensure_ascii=False).splitlines()
        # Re-indent every line but the first ("{"), which lands right after
        # the key on the same line and needs no leading spaces of its own.
        body_lines: list[str] = [lines[0]]
        for line in lines[1:]:
            body_lines.append(indent + line)
        body: str = "\n".join(body_lines)
        return f',\n{indent}"sly_data_schema": {body}'

    def _render_agent_block(
        self, agent_name: str, agent: dict[str, Any], top_agent_name: str, sly_data_schema_block: str = ""
    ) -> str:
        """
        Render a single agent block depending on its type.

        :param agent_name: The name of the agent
        :param agent: The agent definition
        :param top_agent_name: The name of the top agent
        :param sly_data_schema_block: Rendered sly_data_schema fragment for the
                top agent's function block ("" for none)

        :return: The rendered agent block as a string.
        """
        # Note that `get() or`` pattern is used to avoid issues if the field is set to None.
        raw_tools: list[str] = agent.get("tools") or []
        tools: str = self._format_tools(raw_tools)
        description: str = (agent.get("description") or "").strip()
        instructions: str = (agent.get("instructions") or "").strip()
        middleware_block: str = self._render_middleware(agent.get(MIDDLEWARE_KEY) or [])

        if agent_name == top_agent_name:
            use_description = description or "An assistant that answers inquiries from the user."
            block: str = TOP_AGENT_TEMPLATE % (agent_name, use_description, sly_data_schema_block, instructions, tools)
        elif raw_tools:
            block = REGULAR_AGENT_TEMPLATE % (agent_name, description, instructions, tools)
        elif instructions:
            demo_prefix = "${demo_mode}" if self.demo_mode else ""
            block = LEAF_NODE_AGENT_TEMPLATE % (agent_name, description, demo_prefix, instructions)
        else:
            return TOOLBOX_AGENT_TEMPLATE % (agent_name, agent_name)

        if middleware_block:
            block = self._insert_middleware(block, middleware_block)
        return block

    def _insert_middleware(self, block: str, middleware_block: str) -> str:
        """
        Insert a middleware block before the closing brace of an agent block.

        All agent templates end with "        },\\n". This method removes that suffix,
        ensures the last property line has a trailing comma, appends the middleware block,
        then re-adds the closing brace.

        :param block: The rendered agent block string
        :param middleware_block: The rendered middleware block string
        :return: The agent block with middleware inserted inside its closing brace.
        """
        close = "        },\n"
        prefix = block[: -len(close)]
        prefix = prefix.rstrip("\n")
        if not prefix.endswith(","):
            prefix += ","
        return prefix + "\n" + middleware_block + close

    def _render_middleware(self, middleware: list[dict[str, Any]]) -> str:
        """
        Render the middleware list as a HOCON array string.

        :param middleware: List of middleware dicts, each with "class" and optional "args"

        :return: Formatted middleware block as a string, or empty string if none.
        """
        if not middleware:
            return ""

        lines: list[str] = [f'            "{MIDDLEWARE_KEY}": [']
        for i, entry in enumerate(middleware):
            lines.append("                {")
            lines.append(f'                    "class": "{entry["class"]}",')
            args = entry.get("args")
            if args:
                # HOCON is a superset of JSON, so json.dumps emits valid HOCON for every value
                # type (str/int/float/bool/None/list/dict). Don't try to format these by hand —
                # Python's str() produces Python repr (single quotes, `None`, etc.) which would
                # break round-trip for middleware whose args contain lists or dicts.
                args_lines: list[str] = [f'                        "{k}": {json.dumps(v)}' for k, v in args.items()]
                lines.append('                    "args": {')
                lines.append(",\n".join(args_lines))
                lines.append("                    }")
            else:
                # Remove the trailing comma from "class" line since it's the last field
                lines[-1] = lines[-1].rstrip(",")
            comma = "," if i < len(middleware) - 1 else ""
            lines.append(f"                }}{comma}")
        lines.append("            ]")
        return "\n".join(lines) + "\n"

    def _format_tools(self, tools: list[str]) -> str:
        """
        Format a list of tool names into a HOCON array string.

        :param tools: List of tool names

        :return: Formatted tools as a string.
        """
        return ", ".join(f'"{t}"' for t in tools)
