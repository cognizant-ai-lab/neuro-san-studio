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

"""Coded tool for reading the current Network Consultant job log."""

import asyncio
import logging
import os
from typing import Any
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.agent_network_editor.and_logger import AndLogger

NSFLOW_JOB_ID = os.environ.get("NSFLOW_JOB_ID")
NSFLOW_JOB_DIR = os.environ.get("NSFLOW_JOB_DIR")
JOB_LOG_TAIL_LINES = 200


class ReadJobLog(CodedTool):
    """Read round-level context from the current nsflow job log."""

    @staticmethod
    def _read_tail(log_path: str, tail_lines: int) -> str | None:
        """Read a bounded log tail when the job log exists."""
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
                return "".join(log_file.readlines()[-tail_lines:])
        except FileNotFoundError:
            return None

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """Return the requested tail of the current job log."""
        del sly_data
        logger = AndLogger(logging.getLogger(self.__class__.__name__))
        if not (NSFLOW_JOB_ID and NSFLOW_JOB_DIR):
            return "Error: Not running as an nsflow job -- there is no per-job log to read."

        tail_lines = args.get("tail_lines") or JOB_LOG_TAIL_LINES
        log_path = os.path.join(NSFLOW_JOB_DIR, f"{NSFLOW_JOB_ID}.log")
        content = await asyncio.to_thread(self._read_tail, log_path, tail_lines)
        if content is None:
            return f"Error: Job log not found: {log_path}"

        logger.info("Reading job log: %s", log_path)
        return {"job_log_tail": content}
