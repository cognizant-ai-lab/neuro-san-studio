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
    The actual call is wrapped via CodedToolAgentCaller, matching the convention used
    elsewhere in this repo (see decomposition_solver.py).
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        agents: list[dict[str, Any]] = args.get("agents") or []
        if not agents:
            return "Error: No agents provided."

        agent_network_description: str = args.get("agent_network_description") or ""

        # Resolve the writer agent name via args.tools so hocon controls connectivity
        # (mirrors the decomposition_solver pattern).
        tools_map: dict[str, str] = args.get("tools") or {}
        writer_name: str = tools_map.get("instructions_writer", "instructions_writer")

        logger = logging.getLogger(self.__class__.__name__)
        logger.info("Dispatching %d parallel '%s' calls", len(agents), writer_name)

        async def call_writer(entry: dict[str, Any]) -> str:
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

        results = await asyncio.gather(
            *[call_writer(entry) for entry in agents],
            return_exceptions=True,
        )

        ok: list[str] = []
        errs: list[str] = []
        for entry, result in zip(agents, results):
            name = entry.get("agent_name", "<unknown>")
            if isinstance(result, BaseException):
                errs.append(f"{name}: {result!r}")
            else:
                ok.append(name)

        if errs:
            return (
                f"Instructions/description set for {len(ok)} agents; "
                f"{len(errs)} failed: " + "; ".join(errs)
            )
        return f"Instructions/description have been set for all {len(ok)} agents."
