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

"""Filtered diagnostic thinking traces for failed Network Consultant fixtures."""

import glob
import logging
import os
import re

logger = logging.getLogger("network_consultant")

IMPROVEMENT_THINKING_DIR = os.path.join("logs", "thinking_dir", "improvement")
THINKING_ENTRY_HEADER = re.compile(r"^\[(?P<type>[A-Z_]+)[^\]]*\] @ .+:$", re.MULTILINE)
COST_ACCOUNTING_KEYS = ("prompt_tokens", "completion_tokens", "total_cost", "total_tokens")


class ThinkingTraceCollector:
    """Consolidate useful agent reasoning while removing system prompts and telemetry."""

    @staticmethod
    def run_directory(run_id: str) -> str:
        """
        Return the isolated consolidated-trace directory for one Consultant run.

        :param run_id: The unique Consultant run identifier.
        :return: The run-owned consolidated-trace directory.
        :raises ValueError: If the run identifier is empty or unsafe for use as a directory name.
        """
        if not run_id or re.fullmatch(r"[\w.-]+", run_id) is None:
            raise ValueError("The Consultant run identifier is missing or invalid.")
        return os.path.join(IMPROVEMENT_THINKING_DIR, run_id)

    @staticmethod
    def _is_noise_paragraph(paragraph: str) -> bool:
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
        for key in COST_ACCOUNTING_KEYS:
            if key in body:
                return True
        return False

    @staticmethod
    def strip_system_entries(raw_text: str) -> str:
        """
        Remove system prompts, chat context, and cost telemetry from one raw trace.

        :param raw_text: The raw thinking-trace text.
        :return: The filtered trace text.
        """
        headers = list(THINKING_ENTRY_HEADER.finditer(raw_text))
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
                if not ThinkingTraceCollector._is_noise_paragraph(paragraph.strip()):
                    paragraphs.append(paragraph)
            body = "\n\n".join(paragraphs).strip()
            entry = f"{header_line}\n{body}" if body else ""
            if entry:
                kept.append(entry)
        return "\n\n".join(kept)

    @staticmethod
    def _iteration_of(run_directory: str) -> str:
        """
        Return a thinking directory's success-ratio iteration suffix.

        :param run_directory: The thinking-trace run directory.
        :return: The iteration suffix, or an empty string when absent.
        """
        match = re.search(r"_(\d+)$", os.path.basename(run_directory))
        return match.group(1) if match else ""

    @staticmethod
    def _run_directories(basis_directory: str, fixture_name: str, started: float) -> list[str]:
        """
        Find current thinking directories for one representative fixture iteration.

        :param basis_directory: The directory containing raw thinking traces.
        :param fixture_name: The fixture base name.
        :param started: The fixture start time used to exclude older traces.
        :return: The representative run directories.
        """
        matching_directories: list[str] = []
        for directory in glob.glob(os.path.join(basis_directory, f"*_{fixture_name}*")):
            if os.path.isdir(directory) and os.path.getmtime(directory) >= started:
                matching_directories.append(directory)
        run_directories = sorted(matching_directories)
        if not run_directories:
            return []

        # Each success-ratio iteration contains near-identical retries. Keep every turn from the earliest iteration.
        first_iteration = ThinkingTraceCollector._iteration_of(run_directories[0])
        representative_directories: list[str] = []
        for directory in run_directories:
            if ThinkingTraceCollector._iteration_of(directory) == first_iteration:
                representative_directories.append(directory)
        return representative_directories

    @staticmethod
    def _read_section(path: str, agent_file: str) -> tuple[str, str]:
        """
        Read and filter one agent's thinking-trace section.

        :param path: The thinking-trace file path.
        :param agent_file: The trace file name used when no origin is recorded.
        :return: The agent origin and filtered trace text.
        """
        with open(path, encoding="utf-8", errors="replace") as trace_file:
            raw = trace_file.read()
        first_line, _, rest = raw.partition("\n")
        agent_origin = first_line[len("Agent: ") :].strip() if first_line.startswith("Agent: ") else agent_file
        return agent_origin, ThinkingTraceCollector.strip_system_entries(rest)

    @staticmethod
    def _sections(run_directories: list[str]) -> dict[str, list[str]]:
        """
        Group filtered thinking traces by their originating agent.

        :param run_directories: The thinking-trace run directories.
        :return: Filtered trace chunks keyed by agent origin.
        """
        sections: dict[str, list[str]] = {}
        for run_directory in run_directories:
            for agent_file in sorted(os.listdir(run_directory)):
                path = os.path.join(run_directory, agent_file)
                if not os.path.isfile(path):
                    continue
                agent_origin, filtered = ThinkingTraceCollector._read_section(path, agent_file)
                if filtered:
                    sections.setdefault(agent_origin, []).append(filtered)
        return sections

    @staticmethod
    def write(fixture_name: str, started: float, run_id: str) -> None:
        """
        Consolidate one fixture's useful reasoning into a diagnostic trace.

        :param fixture_name: The fixture base name.
        :param started: The fixture start time used to exclude older traces.
        :param run_id: The unique Consultant run identifier.
        """
        basis_directory = os.environ.get("AGENT_TEST_THINKING_BASIS")
        if not basis_directory:
            return
        sections = ThinkingTraceCollector._sections(
            ThinkingTraceCollector._run_directories(basis_directory, fixture_name, started)
        )
        if not sections:
            return

        run_directory = ThinkingTraceCollector.run_directory(run_id)
        os.makedirs(run_directory, exist_ok=True)
        output_path = os.path.join(run_directory, f"{fixture_name}.txt")
        with open(output_path, "w", encoding="utf-8") as output_file:
            for agent_origin, chunks in sections.items():
                output_file.write(f"--- {agent_origin} ---\n")
                output_file.write("\n\n".join(chunks))
                output_file.write("\n\n")
        logger.info("Consolidated thinking trace written: %s (%d agent(s))", output_path, len(sections))
