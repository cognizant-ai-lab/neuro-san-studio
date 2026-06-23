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

import asyncio
import logging
from typing import Any

from neuro_san.interfaces.coded_tool import CodedTool
from neuro_san.internals.graph.activations.branch_activation import BranchActivation

from neuro_san_studio.coded_tools.coded_tool_agent_caller import CodedToolAgentCaller


# pylint: disable=too-many-ancestors
class WriteAllInstructions(BranchActivation, CodedTool):
    """
    CodedTool that fans out per-agent instruction writing in parallel.

    The instructions_editor agent invokes this tool ONCE per request with:
      - agent_network_description (shared network-wide context, sent once)
      - agents: [{"agent_name": "...", "change_request": "..."}, ...]

    The tool dispatches one `instructions_writer` invocation per entry concurrently via
    asyncio.gather(). This avoids forcing the editor LLM to re-emit `agent_network_description`
    N times across N parallel tool calls, while preserving the writer-level parallelism that
    the framework already provides.

    Note that we doubly-inherit from BranchActivation to access the framework hook
    `use_tool()` that lets a CodedTool call other agents (in the same network or not).
    The actual call is wrapped via CodedToolAgentCaller.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        Fan out one `instructions_writer` invocation per entry in `args["agents"]`,
        running them concurrently via asyncio.gather().

        :param args: Tool arguments. Expected keys:
            - "agents": list of {"agent_name": str, "change_request": str (optional)}.
            - "agent_network_description": shared network-wide context, sent once and
              applied to every entry.
            - "tools": optional mapping with "instructions_writer" -> agent name to
              dispatch to (defaults to "instructions_writer").
        :param sly_data: Shared private data dictionary forwarded unchanged to each
            writer call (carries the `agent_network_definition`).
        :return: A success summary string if all writers succeeded, or an "Error: ..."
            string listing per-agent failures otherwise.
        """
        agents: list[dict[str, Any]] = args.get("agents") or []
        if not agents:
            return "Error: No agents provided."

        agent_network_description: str = args.get("agent_network_description") or ""

        # Resolve the writer agent name via args.tools so hocon controls connectivity.
        tools_map: dict[str, str] = args.get("tools") or {}
        writer_name: str = tools_map.get("instructions_writer", "instructions_writer")

        logger = logging.getLogger(self.__class__.__name__)
        logger.info("Dispatching %d parallel '%s' calls", len(agents), writer_name)

        tasks = []
        for entry in agents:
            tasks.append(self.call_writer(writer_name, entry, agent_network_description, sly_data))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        ok: list[str] = []
        errs: list[str] = []
        for entry, result in zip(agents, results):
            name = entry.get("agent_name") or "<unknown>"
            if isinstance(result, BaseException):
                errs.append(f"{name}: {result!r}")
            elif isinstance(result, str) and result.lstrip().startswith("Error:"):
                errs.append(f"{name}: {result.strip()}")
            else:
                ok.append(name)

        if errs:
            return f"Error: Instructions/description set for {len(ok)} agents; {len(errs)} failed: " + "; ".join(errs)
        return f"Instructions/description have been set for all {len(ok)} agents."

    async def call_writer(
        self,
        writer_name: str,
        entry: dict[str, Any],
        agent_network_description: str,
        sly_data: dict[str, Any],
    ) -> str:
        """
        Invoke `instructions_writer` once for a single agent entry.

        :param writer_name: The downstream agent name to dispatch to (typically
            "instructions_writer", resolved from `args.tools`).
        :param entry: One element of the `agents` list, e.g.
            {"agent_name": "...", "change_request": "..."}. `change_request` is
            optional and forwarded only when present.
        :param agent_network_description: Shared network-wide context, forwarded
            only when non-empty.
        :param sly_data: Shared private data forwarded to the writer call.
        :return: The writer's response string. A `ValueError` is raised if `entry`
            has no `agent_name`.
        """
        agent_name: str = entry.get("agent_name")
        if not agent_name:
            raise ValueError("Missing 'agent_name' in agents entry.")

        tool_args: dict[str, Any] = {"agent_name": agent_name}
        if agent_network_description:
            tool_args["agent_network_description"] = agent_network_description
        change_request = entry.get("change_request")
        if change_request:
            tool_args["change_request"] = change_request

        caller = CodedToolAgentCaller(self, parsing=None, name=writer_name)
        return await caller.call_agent(tool_args=tool_args, sly_data=sly_data)
