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

"""Coded tool for reading a fixture's saved agent-thinking trace."""

import logging
import re
from pathlib import Path
from typing import Any
from typing import Union
from typing import override

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_editor.and_logger import AndLogger
from neuro_san_studio.agent_network_consultant.consultant_state import ConsultantState
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector
from neuro_san_studio.coded_tools.file_management.read_file import MAX_FILE_BYTES
from neuro_san_studio.coded_tools.file_management.read_file import ReadFile


class ReadThinkingTrace(CodedTool):
    """
    Read one filtered fixture trace written by `ThinkingTraceCollector.write()` for this run.

    Agent Network Consultant diagnosing agents can first omit `agent_name` to list available trace sections, then
    request one agent's reasoning without loading every trace into context. `ReadJobLog` separately supplies
    round-level context when an nsflow job log is available.
    """

    SECTION_HEADER = re.compile(r"^--- (.+) ---$", re.MULTILINE)
    RUN_ID_KEY = ConsultantState.AGENT_NETWORK_CONSULTANT_RUN_ID

    def __init__(self, trace_root: Path | None = None) -> None:
        """
        Store the optional root containing isolated filtered traces.

        :param trace_root: An explicit filtered-trace root, primarily for isolated callers and tests.
        """
        self._trace_root = trace_root

    def _parse_sections(self, content: str) -> dict[str, str]:
        """
        Split a consolidated thinking file into agent trace sections.

        :param content: The complete consolidated trace text.
        :return: Trace text keyed by originating agent.
        """
        headers = list(self.SECTION_HEADER.finditer(content))
        sections: dict[str, str] = {}
        for index, header in enumerate(headers):
            start = header.end()
            end = headers[index + 1].start() if index + 1 < len(headers) else len(content)
            sections.update({header.group(1): content[start:end].strip()})
        return sections

    @staticmethod
    async def _read_trace(path: Path, run_directory: Path, sly_data: dict[str, Any]) -> str | None:
        """
        Read a trace through the shared file-management controls.

        :param path: The file or token path to process.
        :param run_directory: The isolated directory containing this run's traces.
        :param sly_data: The shared agent runtime data.
        :return: The resulting value, or `None` when unavailable.
        :raises ValueError: If an existing trace cannot be read safely.
        """
        file_args: dict[str, Any] = {
            "file_path": str(path),
            "allowed_paths": [str(run_directory)],
            "allowed_file_extensions": [".txt"],
            "max_content_chars": MAX_FILE_BYTES,
        }
        try:
            result: dict[str, Any] = await ReadFile().async_invoke(file_args, sly_data)
        except ValueError as exc:
            if str(exc).startswith("path_not_found:"):
                return None
            raise
        return SensitiveDataRedactor.redact_text(str(result.get("content", "")))

    @staticmethod
    def _select_trace(
        sections: dict[str, str],
        agent_name: str,
        fixture_name: str,
    ) -> Union[dict[str, Any], str]:
        """
        Return the available agents or one selected agent trace.

        :param sections: The parsed traces keyed by agent name.
        :param agent_name: The optional agent whose trace was requested.
        :param fixture_name: The fixture name used in actionable errors.
        :return: Available agents, the selected trace, or a missing-agent error.
        """
        if not agent_name:
            return {"available_agents": list(sections.keys())}
        if agent_name not in sections:
            return (
                f"Error: No trace for agent '{agent_name}' in fixture '{fixture_name}'. "
                f"Available agents: {list(sections.keys())}"
            )
        return {"agent_name": agent_name, "trace": sections.get(agent_name, "")}

    @override
    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        List available agent traces or read one selected trace for a failed fixture.

        :param args: The required fixture name and optional agent name.
        :param sly_data: Shared runtime data used to audit the managed file read.
        :return: Available agent names, the selected trace, or an actionable error.
        """
        logger = AndLogger(logging.getLogger(self.__class__.__name__))

        fixture_name: str = args.get("fixture_name", "")
        if not fixture_name:
            return "Error: No 'fixture_name' provided."

        run_id = str(sly_data.get(self.RUN_ID_KEY) or "")
        try:
            trace_collector = ThinkingTraceCollector(run_id, output_directory=self._trace_root)
            run_directory = Path(trace_collector.run_directory()).resolve()
        except ValueError as exc:
            logger.error("Could not resolve the Agent Network Consultant thinking-trace directory: %s", exc)
            return f"Error: {exc}"
        safe_name = re.sub(r"[^\w.\-]", "_", Path(fixture_name).name)
        trace_path = (run_directory / f"{safe_name}.txt").resolve()
        try:
            trace_path.relative_to(run_directory)
        except ValueError:
            return "Error: fixture_name resolves outside the thinking-trace directory."
        try:
            content: str | None = await self._read_trace(trace_path, run_directory, sly_data)
        except ValueError as exc:
            logger.error("Could not read thinking trace %s: %s", trace_path, exc)
            return f"Error: {exc}"
        if content is None:
            return f"Error: No saved thinking trace found for fixture '{fixture_name}'."

        logger.info("Reading thinking trace: %s", trace_path)
        sections = self._parse_sections(content)

        agent_name: str = args.get("agent_name", "")
        return self._select_trace(sections, agent_name, fixture_name)
