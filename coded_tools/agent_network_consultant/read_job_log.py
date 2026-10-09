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

"""Coded tool for reading the current Agent Network Consultant job log."""

import logging
from numbers import Integral
from pathlib import Path
from typing import Any
from typing import Union
from typing import override

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_editor.and_logger import AndLogger
from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor
from neuro_san_studio.coded_tools.file_management.read_file import MAX_FILE_BYTES
from neuro_san_studio.coded_tools.file_management.read_file import ReadFile


class ReadJobLog(CodedTool):
    """Read round-level context from the current nsflow job log."""

    # Two hundred lines bound prompt size while retaining the most recent diagnostics.
    JOB_LOG_TAIL_LINES = 200

    @staticmethod
    def _tail(content: str, tail_lines: int) -> str:
        """
        Return a bounded tail from previously read log content.

        :param content: The complete managed-file content.
        :param tail_lines: The maximum number of trailing log lines to read.
        :return: The requested trailing log lines.
        """
        return "".join(content.splitlines(keepends=True)[-tail_lines:])

    @staticmethod
    def _positive_line_count(value: Any) -> int | None:
        """
        Normalize a positive integral line count.

        :param value: The requested number of trailing lines.
        :return: The positive line count, or `None` when the value is invalid.
        """
        if value is True or value is False:
            return None
        if not isinstance(value, Integral):
            return None
        line_count = int(value)
        if line_count < 1:
            return None
        return line_count

    @override
    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Read a bounded tail from the active nsflow job log.

        :param args: The optional positive `tail_lines` limit.
        :param sly_data: The shared agent runtime data.
        :return: The requested job-log tail or an actionable error.
        """
        logger = AndLogger(logging.getLogger(self.__class__.__name__))
        job_log_path = ConsultantJobFiles().path("log")
        if job_log_path is None:
            return "Error: Not running as an nsflow job -- there is no per-job log to read."

        requested_tail_lines: Any = args.get("tail_lines")
        if requested_tail_lines is None:
            requested_tail_lines = self.JOB_LOG_TAIL_LINES
        tail_lines = self._positive_line_count(requested_tail_lines)
        if tail_lines is None:
            return f"Error: 'tail_lines' must be a positive integer, got {requested_tail_lines!r}."
        log_path = Path(job_log_path).resolve()
        file_args: dict[str, Any] = {
            "file_path": str(log_path),
            "allowed_paths": [str(log_path)],
            "allowed_file_extensions": [".log"],
            "max_content_chars": MAX_FILE_BYTES,
        }
        try:
            result: dict[str, Any] = await ReadFile().async_invoke(file_args, sly_data)
        except ValueError as exc:
            if str(exc).startswith("path_not_found:"):
                return f"Error: Job log not found: {log_path}"
            logger.error("Could not read job log %s: %s", log_path, exc)
            return f"Error: {exc}"
        content: str = str(result.get("content", ""))

        logger.info("Reading job log: %s", log_path)
        return {"job_log_tail": SensitiveDataRedactor.redact_text(self._tail(content, tail_lines))}
