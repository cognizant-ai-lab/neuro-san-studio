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

"""Tests for nsflow job-file exchange used by Network Consultant."""

import os
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles


class TestConsultantJobFiles(TestCase):
    """Verify job paths, optional writes, and headless clarification exchange."""

    def setUp(self) -> None:
        """Create one isolated active job environment."""
        self.job_directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.job_directory)
        self.environment = patch.dict(
            os.environ,
            {"NSFLOW_JOB_ID": "job-1", "NSFLOW_JOB_DIR": str(self.job_directory)},
        )
        self.addCleanup(self.environment.stop)
        self.environment.start()

    def _write_answer(self, _seconds: float) -> None:
        """
        Simulate nsflow answering during one polling interval.

        :param _seconds: The unused polling interval.
        """
        answer_path = ConsultantJobFiles.path("answer.txt")
        if answer_path is None:
            self.fail("The active test job did not resolve an answer path.")
        Path(answer_path).write_text("operator answer\n", encoding="utf-8")

    def test_write_uses_the_active_job_path(self) -> None:
        """Write a result file using the job identifier and requested suffix."""
        ConsultantJobFiles.write("result.txt", "complete")

        self.assertTrue(ConsultantJobFiles.active())
        self.assertEqual("complete", (self.job_directory / "job-1.result.txt").read_text(encoding="utf-8"))

    def test_inactive_job_has_no_path_and_does_not_write(self) -> None:
        """Treat either missing environment value as a plain non-nsflow run."""
        with patch.dict(os.environ, {"NSFLOW_JOB_ID": ""}):
            ConsultantJobFiles.write("result.txt", "ignored")

            self.assertFalse(ConsultantJobFiles.active())
            self.assertIsNone(ConsultantJobFiles.path("result.txt"))
        self.assertFalse((self.job_directory / "job-1.result.txt").exists())

    def test_ask_returns_answer_and_removes_exchange_files(self) -> None:
        """Return the operator answer and clean up both one-shot exchange files."""
        with patch(
            "neuro_san_studio.agent_network_consultant.consultant_job_files.time.sleep",
            side_effect=self._write_answer,
        ):
            answer = ConsultantJobFiles.ask("Need guidance", 0.01)

        self.assertEqual("operator answer", answer)
        self.assertFalse((self.job_directory / "job-1.question.txt").exists())
        self.assertFalse((self.job_directory / "job-1.answer.txt").exists())

    def test_ask_rejects_non_nsflow_use(self) -> None:
        """Report an actionable error instead of waiting without a job directory."""
        with patch.dict(os.environ, {"NSFLOW_JOB_DIR": ""}):
            with self.assertRaisesRegex(RuntimeError, "outside an nsflow job"):
                ConsultantJobFiles.ask("Need guidance", 0.01)
