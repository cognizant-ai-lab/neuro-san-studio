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

"""Behavioral tests for managed Network Consultant job-log reads."""

import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from coded_tools.agent_network_consultant.read_job_log import ReadJobLog


class TestReadJobLog(IsolatedAsyncioTestCase):
    """Verify job-log reads use file management while retaining tail semantics."""

    def setUp(self) -> None:
        """Create one isolated job directory for each test."""
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        """Remove the isolated job directory after each test."""
        shutil.rmtree(self.tmp_path)

    async def test_reads_requested_tail_and_records_history(self) -> None:
        """
        Return only the requested trailing lines and audit the managed read.

        """
        log_path: Path = self.tmp_path / "job-1.log"
        log_path.write_text("one\ntwo\nthree\n", encoding="utf-8")
        sly_data: dict[str, Any] = {}

        with patch.dict("os.environ", {"NSFLOW_JOB_ID": "job-1", "NSFLOW_JOB_DIR": str(self.tmp_path)}):
            result: dict[str, Any] = await ReadJobLog().async_invoke({"tail_lines": 2}, sly_data)

        self.assertEqual(result.get("job_log_tail"), "two\nthree\n")
        self.assertEqual(sly_data.get("read_file_history"), [str(log_path.resolve())])

    async def test_reports_a_missing_job_log(self) -> None:
        """
        Preserve the Consultant-facing missing-log error contract.

        """
        with patch.dict("os.environ", {"NSFLOW_JOB_ID": "missing", "NSFLOW_JOB_DIR": str(self.tmp_path)}):
            result: str = await ReadJobLog().async_invoke({}, {})

        expected_path: Path = (self.tmp_path / "missing.log").resolve()
        self.assertEqual(result, f"Error: Job log not found: {expected_path}")

    async def test_rejects_an_invalid_tail_size(self) -> None:
        """
        Reject an invalid line count before accessing the filesystem.

        """
        with patch.dict("os.environ", {"NSFLOW_JOB_ID": "job-1", "NSFLOW_JOB_DIR": str(self.tmp_path)}):
            result: str = await ReadJobLog().async_invoke({"tail_lines": "many"}, {})
        self.assertEqual(result, "Error: 'tail_lines' must be a positive integer, got 'many'.")

    async def test_rejects_a_boolean_tail_size(self) -> None:
        """Reject a boolean even though it implements Python's integer-index interface."""
        with patch.dict("os.environ", {"NSFLOW_JOB_ID": "job-1", "NSFLOW_JOB_DIR": str(self.tmp_path)}):
            result: str = await ReadJobLog().async_invoke({"tail_lines": True}, {})

        self.assertEqual(result, "Error: 'tail_lines' must be a positive integer, got True.")

    async def test_reports_when_no_job_context_is_active(self) -> None:
        """Resolve the current environment and report when nsflow has not supplied a complete job context."""
        with patch.dict("os.environ", {"NSFLOW_JOB_ID": "", "NSFLOW_JOB_DIR": ""}):
            result: str = await ReadJobLog().async_invoke({}, {})

        self.assertEqual(result, "Error: Not running as an nsflow job -- there is no per-job log to read.")
