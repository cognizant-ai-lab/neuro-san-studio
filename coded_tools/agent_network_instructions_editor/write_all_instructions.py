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
from neuro_san.message.parsers.structure.json_structure_parser import JsonStructureParser

from coded_tools.agent_network_editor.and_logger import AndLogger
from coded_tools.agent_network_editor.constants import AGENT_NETWORK_DEFINITION
from coded_tools.agent_network_editor.progress_handler import ProgressHandler
from neuro_san_studio.coded_tools.coded_tool_agent_caller import CodedToolAgentCaller


# pylint: disable=too-many-ancestors
class WriteAllInstructions(BranchActivation, CodedTool):
    """
    CodedTool that fans out per-agent instruction writing in parallel.

    The instructions_editor agent invokes this tool ONCE per request with:
      - agent_network_description (shared network-wide context, sent once)
      - agents: [{"agent_name": "...", "change_request": "..."}, ...]

    The tool dispatches one `instructions_writer` invocation per entry concurrently via
    asyncio.gather(). Each writer is a single LLM turn that answers with a JSON object
    ({"instructions": ..., "description": ...}); THIS tool parses that answer and writes
    the fields into sly_data's agent_network_definition itself. The writer has no tools
    of its own, so each agent costs exactly one model call — the earlier design's
    setter-tool round trip and closing confirmation turn are gone, and the writer can
    no longer misroute a field to the wrong agent, because the agent_name the fields
    are applied to is pinned here rather than re-stated by the model.

    Note that we doubly-inherit from BranchActivation to access the framework hook
    `use_tool()` that lets a CodedTool call other agents (in the same network or not).
    The actual call is wrapped via CodedToolAgentCaller.
    """

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> str:
        """
        Fan out one `instructions_writer` invocation per entry in `args["agents"]`,
        running them concurrently via asyncio.gather(), and apply each writer's
        JSON answer to the agent_network_definition as it completes.

        :param args: Tool arguments. Expected keys:
            - "agents": list of {"agent_name": str, "change_request": str (optional)}.
            - "agent_network_description": shared network-wide context, sent once and
              applied to every entry.
            - "tools": optional mapping with "instructions_writer" -> agent name to
              dispatch to (defaults to "instructions_writer").
        :param sly_data: Shared private data dictionary forwarded unchanged to each
            writer call (carries the `agent_network_definition` the fields are
            written into).
        :return: A success summary string if all writers succeeded, or an "Error: ..."
            string listing per-agent failures otherwise.
        """
        # list[Any], not list[dict]: malformed entries are tolerated here and
        # fail loudly per-entry in call_writer.
        agents: list[Any] = args.get("agents") or []
        if not agents:
            return "Error: No agents provided."
        if not sly_data.get(AGENT_NETWORK_DEFINITION):
            return "Error: No network in sly data!"

        # Resolve the writer agent name via args.tools so hocon controls connectivity.
        tools_map: dict[str, str] = args.get("tools") or {}
        writer_name: str = tools_map.get("instructions_writer", "instructions_writer")

        agents = self._dedup_agents(agents)

        logger = AndLogger(logging.getLogger(self.__class__.__name__))
        logger.info("Dispatching %d parallel '%s' calls", len(agents), writer_name)

        tasks = []
        for entry in agents:
            tasks.append(self.call_writer(writer_name, entry, args, sly_data))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        ok: list[str] = []
        errs: list[str] = []
        for entry, result in zip(agents, results):
            name = (entry.get("agent_name") if isinstance(entry, dict) else None) or "<unknown>"
            if isinstance(result, BaseException):
                errs.append(f"{name}: {result!r}")
            elif result:
                # call_writer returns "" on success, or an "Error: ..." string.
                errs.append(f"{name}: {result}")
            else:
                ok.append(name)

        if errs:
            return f"Error: Instructions/description set for {len(ok)} agents; {len(errs)} failed: " + "; ".join(errs)
        return f"Instructions/description have been set for all {len(ok)} agents."

    @staticmethod
    def _dedup_agents(agents: list[Any]) -> list[Any]:
        """
        Collapse duplicate entries so at most one writer is dispatched per
        agent_name — duplicates would race to write the same agent's fields
        concurrently, leaving whichever writer finished last in the network
        definition. The LAST entry wins (its change_request is the most
        recent directive), at the first occurrence's position. Malformed
        entries (non-dicts, and dicts without an agent_name) get a unique
        per-index key so each survives to fail loudly per-entry in
        call_writer instead of collapsing together or being dropped here.

        :param agents: The raw agents list from the tool arguments.
        :return: The deduplicated list, in first-seen order.
        """
        unique: dict[Any, Any] = {}
        for index, entry in enumerate(agents):
            key = entry.get("agent_name") if isinstance(entry, dict) else None
            if not key:
                key = f"<malformed entry {index}>"
            unique[key] = entry
        return list(unique.values())

    async def call_writer(
        self,
        writer_name: str,
        entry: Any,
        args: dict[str, Any],
        sly_data: dict[str, Any],
    ) -> str:
        """
        Invoke `instructions_writer` once for a single agent entry and apply its
        JSON answer to the network definition. Applying here — inside the
        gathered task, rather than after the whole gather — lets early writers'
        results reach the (throttled) progress stream while slower writers are
        still running, matching the incremental progress the setter tools used
        to produce.

        :param writer_name: The downstream agent name to dispatch to (typically
            "instructions_writer", resolved from `args.tools`).
        :param entry: One element of the `agents` list, e.g.
            {"agent_name": "...", "change_request": "..."}. `change_request` is
            optional and forwarded only when present.
        :param args: This tool's own args — carries the shared
            agent_network_description (forwarded only when non-empty) and the
            progress_reporter used for the per-agent progress report.
        :param sly_data: Shared private data forwarded to the writer call.
        :return: "" on success, or an "Error: ..." string describing the failure.
            A `ValueError` is raised if `entry` is not a dict with an `agent_name`.
        """
        agent_name: str | None = entry.get("agent_name") if isinstance(entry, dict) else None
        if not agent_name:
            raise ValueError(f"Malformed agents entry (expected an object with an 'agent_name'): {entry!r}")

        tool_args: dict[str, Any] = {"agent_name": agent_name}
        agent_network_description: str = args.get("agent_network_description") or ""
        if agent_network_description:
            tool_args["agent_network_description"] = agent_network_description
        change_request = entry.get("change_request")
        if change_request:
            tool_args["change_request"] = change_request

        caller = CodedToolAgentCaller(self, parsing=None, name=writer_name)
        response: str = await caller.call_agent(tool_args=tool_args, sly_data=sly_data)

        if isinstance(response, str) and response.lstrip().startswith("Error:"):
            # Writer failure surfaced through the framework's plain-string error
            # path (error_formatter unset). Under this network's
            # "error_formatter": "json", failures arrive instead as a JSON
            # {"error": ..., "tool": ...} body, detected in _apply_writer_response.
            return response.strip()

        error: str = self._apply_writer_response(agent_name, response, sly_data)
        if error:
            return error

        await ProgressHandler.report_progress(args, sly_data, sly_data.get(AGENT_NETWORK_DEFINITION))
        return ""

    @staticmethod
    def _apply_writer_response(agent_name: str, response: str, sly_data: dict[str, Any]) -> str:
        """
        Parse one writer's JSON answer and write its fields into the
        agent_network_definition — the apply logic that previously lived in the
        set_agent_instructions/set_agent_description setter tools, minus the
        model round trips that drove them.

        Must stay synchronous (no awaits): the N concurrent writers share this
        sly_data without a lock, and what makes that safe is that this method
        runs start-to-finish in one step of the session's event loop, so
        applies can never interleave. (Writers also touch disjoint agent
        entries, but don't lean on that alone.)

        :param agent_name: The agent whose fields are being written. Pinned by
            the caller (not read back from the model's output), so a writer
            cannot misroute fields to another agent.
        :param response: The writer's response text; expected to be (or to
            contain) a JSON object with optional "instructions" and
            "description" string fields. A field absent from the object keeps
            its current value — the writer omits a field when a single-field
            change_request leaves the other unchanged, instead of re-emitting
            the existing text through the model. An empty object is the
            writer's documented no-op ("no change needed") and succeeds
            without writing anything.
        :param sly_data: Carries the agent_network_definition to update.
        :return: "" on success, or an "Error: ..." string.
        """
        network_def: dict[str, Any] = sly_data.get(AGENT_NETWORK_DEFINITION)
        if not network_def:
            return "Error: No network in sly data!"
        if agent_name not in network_def:
            return f"Error: Agent not found: {agent_name}"
        if network_def[agent_name].get("instructions") is None:
            return f"Error: Agent has no instructions field: {agent_name}. It is a function agent."

        updates, error = WriteAllInstructions._validate_writer_fields(response)
        if error:
            return error

        logger = AndLogger(logging.getLogger(WriteAllInstructions.__name__))
        if not updates:
            # The writer's documented no-op: {} means "no change needed".
            logger.info("Writer reported no change needed for '%s'", agent_name)
            return ""

        for field, value in updates.items():
            network_def[agent_name][field] = value
            logger.info("Set %s for '%s' (%d chars)", field, agent_name, len(value))

        sly_data[AGENT_NETWORK_DEFINITION] = network_def
        return ""

    @staticmethod
    def _validate_writer_fields(response: str) -> tuple[dict[str, str], str]:
        """
        Parse a writer's answer and validate its fields BEFORE anything is
        applied, so a bad value can never leave an agent half-updated.

        :param response: The writer's response text.
        :return: An (updates, error) tuple. On success, `updates` holds the
            validated field values to apply and `error` is "" — an empty
            `updates` with no error is the writer's documented {} no-op
            ("no change needed"). On failure, `error` is an "Error: ..."
            string and `updates` is empty.
        """
        fields: dict[str, Any] | None = WriteAllInstructions._parse_writer_fields(response)
        if fields is None:
            return {}, f"Error: Writer response was not a JSON object: {response[:200]!r}"
        if "error" in fields:
            # The framework's "json" error_formatter replaces a failed agent's
            # answer with {"error": ..., "tool": ...}; surface it as this
            # writer's failure instead of "neither field present".
            return {}, f"Error: Writer failed: {str(fields['error'])[:200]}"

        updates: dict[str, str] = {}
        invalid: list[str] = []
        for field in ("instructions", "description"):
            if field not in fields:
                # Omitted field keeps its current value, by contract.
                continue
            value = fields[field]
            if isinstance(value, str) and value.strip():
                updates[field] = value
            else:
                invalid.append(f"{field}={value!r}"[:120])
        if invalid:
            return {}, f"Error: Writer returned non-text or empty value(s): {'; '.join(invalid)}"
        if not updates and fields:
            return {}, "Error: Writer response contained neither 'instructions' nor 'description'."
        return updates, ""

    @staticmethod
    def _parse_writer_fields(response: str) -> dict[str, Any] | None:
        """
        Best-effort parse of a writer's answer into a dict.

        Delegates to the framework's JsonStructureParser — the same parser
        behind hocon "structure_formats" (which only applies to front men,
        so it must be invoked by hand here). It extracts the JSON object
        from code fences or surrounding prose and parses via json_repair,
        so it also recovers near-JSON the model is prone to emit: literal
        newlines inside string values (likely, given this prompt's
        ~120-char wrapped lines), trailing commas, and single-quoted keys.

        :param response: The writer's response text.
        :return: The parsed dict, or None when no JSON object can be extracted.
            An empty object parses to {} — distinct from None — so callers
            can tell "writer said no-op" from "writer answered garbage".
        """
        if not isinstance(response, str):
            # JsonStructureParser raises TypeError on None; degrade to "no structure".
            return None
        return JsonStructureParser().parse_structure(response)
