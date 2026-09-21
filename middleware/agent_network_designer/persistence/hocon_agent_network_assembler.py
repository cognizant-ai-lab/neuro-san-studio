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

import json
from copy import copy as shallow_copy
from datetime import datetime
from datetime import timezone
from typing import Any

from middleware.agent_network_designer.persistence.agent_network_assembler import (
    GENERATED_NETWORK_MAX_EXECUTION_SECONDS,
)
from middleware.agent_network_designer.persistence.agent_network_assembler import AgentNetworkAssembler
from middleware.agent_network_designer.persistence.agent_network_metadata_block import AgentNetworkMetadataBlock

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
    '    "metadata": %s,\n'
    "\n"
    "# Load the shared LLM configuration from a single source of truth.\n"
    "# This allows users to change the model in one file rather than\n"
    "# modifying the configuration for each agent network.\n"
    "# Note that the file path here is relative to the root level of the repo.\n"
    '    include "config/llm_config.hocon",\n'
    "\n"
    f'    "max_execution_seconds": {GENERATED_NETWORK_MAX_EXECUTION_SECONDS},\n'
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
        client_token_mcp_headers: dict[str, list[str]] | None = None,
        metadata: dict[str, Any] | None = None,
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
        :param metadata: Metadata block to carry forward (see the base class);
                None builds the block from sample_queries alone

        :return: A full agent network HOCON as a string.
        """
        use_network_def: dict[str, Any] = shallow_copy(network_def)
        use_network_def = self._move_top_agent_first(use_network_def, top_agent_name)

        # Idempotent when the persistence middleware already built the block: the same queries
        # overlay the same block.
        block: dict[str, Any] = (
            AgentNetworkMetadataBlock(metadata, f"agent network {agent_network_name}")
            .merge_sample_queries(sample_queries)
            .as_dict()
        )
        # A rendered file always carries a creation date: this text is what a client downloads
        # and drops into a registries directory, so a block that has none is stamped here, as the
        # header always did. In file mode the persistence middleware has already stamped both
        # dates and this is a no-op. In reservations mode the block deliberately has no studio
        # dates (a reservation is a new network on every save; neuro-san records its write time
        # as stored_at), so only the downloadable text gets the date, not the deployed spec.
        block.setdefault(AgentNetworkMetadataBlock.DATE_CREATED_KEY, datetime.now(tz=timezone.utc).isoformat())
        header: str = self._build_header(agent_network_name, block)

        sly_data_schema_block: str = self._render_sly_data_schema_block(
            self.build_mcp_sly_data_schema(use_network_def, client_token_mcp_headers)
        )

        body: list[str] = []
        for agent_name, agent in use_network_def.items():
            body.append(self._render_agent_block(agent_name, agent, top_agent_name, sly_data_schema_block))

        return header + "".join(body) + "]\n}\n"

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

    def _build_header(self, agent_network_name: str, metadata: dict[str, Any]) -> str:
        """
        Build the header of the HOCON agent network file.

        :param agent_network_name: The file name, without the .hocon extension
        :param metadata: The merged metadata block to write, as returned by
                AgentNetworkMetadataBlock.as_dict(); may be empty

        :return: The header of the HOCON agent network file as a string.
        """
        # The block is rendered as JSON rather than the former hand-built triple-quoted list so
        # that arbitrary keys carry forward (issue #1398) and so that a query containing three
        # double quotes or a tab, which broke the triple-quoted rendering, survives a round trip
        # (see _render_json_block for what pyhocon still cannot read back).
        metadata_block: str = self._render_json_block(metadata, " " * 4)
        demo_mode_block: str = (
            '   "demo_mode": "You are part of a demo system, so when queried, make up a realistic '
            "response as if you are actually grounded in real data or you are operating a real "
            'application API or microservice.",\n'
            if self.demo_mode
            else ""
        )

        return HOCON_HEADER_START % metadata_block + agent_network_name + HOCON_HEADER_REMAINDER % demo_mode_block

    @staticmethod
    def _render_json_block(value: dict[str, Any], indent: str) -> str:
        """
        Render a dict as an indented HOCON object fragment.

        JSON is valid HOCON, and json.dumps keeps every key and value double-quoted, so the
        fragment always parses as written: HOCON performs no ${...} substitution inside
        double-quoted strings, newlines, tabs and quotes inside values come out as JSON
        escapes that pyhocon reads back verbatim, and ensure_ascii=False keeps non-ASCII text
        (and non-ASCII keys, which pyhocon would not un-escape) as raw characters. pyhocon has
        three reading limits: keys come back raw (a double quote, a backslash or a control
        character in a key does not survive), control characters other than tab, newline and
        carriage return come back as their escape text, and empty strings are dropped from
        lists. AgentNetworkMetadataBlock drops exactly those entries from the metadata block
        before it gets here (see HoconStorabilityUtil), so it reads back as written; the
        schema block holds URLs, header names and fixed text, which never contain them. The
        text is split on the newline character only: str.splitlines() would also split on the
        Unicode line and paragraph separators and on NEL inside a value and corrupt the file.

        :param value: The dict to render
        :param indent: The indentation of the key the fragment follows; every line but the
                first ("{", which lands right after the key) is prefixed with it
        :return: The rendered fragment, starting with "{" and ending with "}"
        """
        lines: list[str] = json.dumps(value, indent=4, ensure_ascii=False).split("\n")
        body_lines: list[str] = [lines[0]]
        for line in lines[1:]:
            body_lines.append(indent + line)
        return "\n".join(body_lines)

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
        body: str = HoconAgentNetworkAssembler._render_json_block(schema, indent)
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

        if agent_name == top_agent_name:
            use_description = description or "An assistant that answers inquiries from the user."
            return TOP_AGENT_TEMPLATE % (agent_name, use_description, sly_data_schema_block, instructions, tools)

        if raw_tools:
            return REGULAR_AGENT_TEMPLATE % (agent_name, description, instructions, tools)

        if instructions:
            demo_prefix = "${demo_mode}" if self.demo_mode else ""
            return LEAF_NODE_AGENT_TEMPLATE % (agent_name, description, demo_prefix, instructions)
        return TOOLBOX_AGENT_TEMPLATE % (agent_name, agent_name)

    def _format_tools(self, tools: list[str]) -> str:
        """
        Format a list of tool names into a HOCON array string.

        :param tools: List of tool names

        :return: Formatted tools as a string.
        """
        return ", ".join(f'"{t}"' for t in tools)
