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

"""Filtered diagnostic thinking traces for failed Agent Network Consultant fixtures."""

import glob
import logging
import os
import re
from pathlib import Path
from re import Pattern

from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor

logger = logging.getLogger(__name__)


class ThinkingTraceCollector:
    """Consolidate useful agent reasoning for one isolated Consultant run."""

    DEFAULT_OUTPUT_DIRECTORY = Path("logs") / "thinking_dir" / "improvement"
    ENTRY_HEADER: Pattern[str] = re.compile(r"^\[(?P<type>[A-Z_]+)[^\]]*\] @ .+:$", re.MULTILINE)
    COST_ACCOUNTING_KEYS = ("prompt_tokens", "completion_tokens", "total_cost", "total_tokens")

    def __init__(
        self,
        run_id: str,
        basis_directory: str | Path | None = None,
        output_directory: str | Path | None = None,
    ) -> None:
        """
        Initialize thinking-trace collection for one Consultant run.

        :param run_id: The unique Agent Network Consultant run identifier.
        :param basis_directory: The raw Neuro SAN trace directory, or `None` to read the child environment.
        :param output_directory: The root directory for filtered traces.
        :raises ValueError: If the run identifier is empty or unsafe for use as a directory name.
        """
        if not run_id or re.fullmatch(r"[\w.-]+", run_id) is None:
            raise ValueError("The Agent Network Consultant run identifier is missing or invalid.")
        configured_basis = basis_directory
        if configured_basis is None:
            configured_basis = os.environ.get("AGENT_TEST_THINKING_BASIS")
        self._basis_directory = Path(configured_basis) if configured_basis else None
        self._output_directory = Path(output_directory or self.DEFAULT_OUTPUT_DIRECTORY)
        self._run_directory = self._output_directory / run_id

    def run_directory(self) -> str:
        """
        Return this run's isolated consolidated-trace directory.

        :return: The run-owned consolidated-trace directory.
        """
        return str(self._run_directory)

    def strip_system_entries(self, raw_text: str) -> str:
        """
        Remove system prompts, chat context, and cost telemetry from one raw trace.

        :param raw_text: The raw thinking-trace text.
        :return: The filtered trace text.
        """
        headers = list(self.ENTRY_HEADER.finditer(raw_text))
        if not headers:
            return raw_text.strip()
        kept: list[str] = []
        for index, header in enumerate(headers):
            if header.group("type") == "SYSTEM":
                continue
            end = headers[index + 1].start() if index + 1 < len(headers) else len(raw_text)
            header_line = header.group(0)
            body = raw_text[header.end() : end].strip()
            paragraphs: list[str] = []
            for paragraph in body.split("\n\n"):
                if not self._is_noise_paragraph(paragraph.strip()):
                    paragraphs.append(paragraph)
            body = "\n\n".join(paragraphs).strip()
            entry = f"{header_line}\n{body}" if body else ""
            if entry:
                kept.append(entry)
        return "\n\n".join(kept)

    def write(self, fixture_name: str, started: float) -> None:
        """
        Consolidate one fixture's useful reasoning into a diagnostic trace.

        :param fixture_name: The fixture base name.
        :param started: The fixture start time used to exclude older traces.
        """
        if self._basis_directory is None:
            return
        sections = self._sections(self._run_directories(fixture_name, started))
        if not sections:
            return

        self._run_directory.mkdir(parents=True, exist_ok=True)
        output_path = self._run_directory / f"{fixture_name}.txt"
        with output_path.open("w", encoding="utf-8") as output_file:
            for agent_origin, chunks in sections.items():
                output_file.write(f"--- {agent_origin} ---\n")
                output_file.write("\n\n".join(chunks))
                output_file.write("\n\n")
        logger.info("Consolidated thinking trace written: %s (%d agent(s))", output_path, len(sections))

    def _is_noise_paragraph(self, paragraph: str) -> bool:
        """
        Return whether a trace paragraph contains bookkeeping instead of dialogue.

        :param paragraph: The thinking-trace paragraph to inspect.
        :return: Whether the paragraph is chat context or cost telemetry.
        """
        if paragraph.startswith("chat_context:"):
            return True
        body = paragraph.strip("`").removeprefix("json").strip() if paragraph.startswith("```") else paragraph
        if not body.startswith("{"):
            return False
        for key in self.COST_ACCOUNTING_KEYS:
            if key in body:
                return True
        return False

    @staticmethod
    def _iteration_of(run_directory: str) -> str:
        """
        Return a thinking directory's success-ratio iteration suffix.

        :param run_directory: The thinking-trace run directory.
        :return: The iteration suffix, or an empty string when absent.
        """
        match = re.search(r"_(\d+)$", os.path.basename(run_directory))
        return match.group(1) if match else ""

    def _run_directories(self, fixture_name: str, started: float) -> list[str]:
        """
        Find current thinking directories for one representative fixture iteration.

        :param fixture_name: The fixture base name.
        :param started: The fixture start time used to exclude older traces.
        :return: The representative run directories.
        """
        if self._basis_directory is None:
            return []
        matching_directories: list[str] = []
        pattern = str(self._basis_directory / f"*_{fixture_name}*")
        for directory in glob.glob(pattern):
            if os.path.isdir(directory) and os.path.getmtime(directory) >= started:
                matching_directories.append(directory)
        run_directories = sorted(matching_directories)
        if not run_directories:
            return []

        # Each success-ratio iteration contains near-identical retries. Keep every turn from the earliest iteration.
        first_iteration = self._iteration_of(run_directories[0])
        representative_directories: list[str] = []
        for directory in run_directories:
            if self._iteration_of(directory) == first_iteration:
                representative_directories.append(directory)
        return representative_directories

    def _read_section(self, path: Path, agent_file: str) -> tuple[str, str]:
        """
        Read and filter one agent's thinking-trace section.

        :param path: The thinking-trace file path.
        :param agent_file: The trace file name used when no origin is recorded.
        :return: The agent origin and filtered trace text.
        """
        with path.open(encoding="utf-8", errors="replace") as trace_file:
            raw = trace_file.read()
        first_line, _, rest = raw.partition("\n")
        agent_origin = first_line[len("Agent: ") :].strip() if first_line.startswith("Agent: ") else agent_file
        filtered_trace = self.strip_system_entries(rest)
        return agent_origin, SensitiveDataRedactor.redact_text(filtered_trace)

    def _sections(self, run_directories: list[str]) -> dict[str, list[str]]:
        """
        Group filtered thinking traces by their originating agent.

        :param run_directories: The thinking-trace run directories.
        :return: Filtered trace chunks keyed by agent origin.
        """
        sections: dict[str, list[str]] = {}
        for run_directory in run_directories:
            directory = Path(run_directory)
            for path in sorted(directory.iterdir()):
                if not path.is_file():
                    continue
                agent_origin, filtered = self._read_section(path, path.name)
                if filtered:
                    sections.setdefault(agent_origin, []).append(filtered)
        return sections
