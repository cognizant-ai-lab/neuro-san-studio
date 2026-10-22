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

"""Tests for nsflow job-file exchange used by Agent Network Consultant."""

import os
import shutil
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any
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
        self.job_files = ConsultantJobFiles()

    def _write_answer(self, _seconds: float) -> None:
        """
        Simulate nsflow answering during one polling interval.

        :param _seconds: The unused polling interval.
        """
        answer_path = self.job_files.path("answer.txt")
        if answer_path is None:
            self.fail("The active test job did not resolve an answer path.")
        answer_path.write_text("operator answer\n", encoding="utf-8")

    @staticmethod
    def _advance_clock(values: list[float]) -> float:
        """
        Return and consume the next simulated monotonic-clock value.

        :param values: The remaining clock values.
        :return: The next clock value.
        """
        return values.pop(0)

    @staticmethod
    def _record_replace(
        calls: list[tuple[Any, Any]],
        real_replace: Callable[[Any, Any], None],
        source: Any,
        destination: Any,
    ) -> None:
        """
        Record an atomic publication and perform the real replacement.

        :param calls: The collected source and destination pairs.
        :param real_replace: The unpatched replacement operation.
        :param source: The staged source path.
        :param destination: The published destination path.
        """
        calls.append((source, destination))
        real_replace(source, destination)

    def test_write_uses_the_active_job_path(self) -> None:
        """Write a result file using the job identifier and requested suffix."""
        replacements: list[tuple[Any, Any]] = []
        real_replace: Callable[[Any, Any], None] = os.replace
        with patch(
            "neuro_san_studio.agent_network_consultant.consultant_job_files.os.replace",
            side_effect=partial(self._record_replace, replacements, real_replace),
        ):
            self.job_files.write("result.txt", "complete")

        self.assertTrue(self.job_files.active())
        self.assertEqual("job-1", self.job_files.identifier())
        self.assertEqual(self.job_directory, self.job_files.directory())
        self.assertEqual("complete", (self.job_directory / "job-1.result.txt").read_text(encoding="utf-8"))
        self.assertEqual(1, len(replacements))
        self.assertEqual(self.job_directory / "job-1.result.txt", replacements[0][1])

    def test_inactive_job_has_no_path_and_does_not_write(self) -> None:
        """Treat either missing environment value as a plain non-nsflow run."""
        with patch.dict(os.environ, {"NSFLOW_JOB_ID": ""}):
            inactive_job_files = ConsultantJobFiles()
            inactive_job_files.write("result.txt", "ignored")

            self.assertFalse(inactive_job_files.active())
            self.assertIsNone(inactive_job_files.path("result.txt"))
        self.assertFalse((self.job_directory / "job-1.result.txt").exists())

    def test_ask_returns_answer_and_removes_exchange_files(self) -> None:
        """Return the operator answer and clean up both one-shot exchange files."""
        with patch(
            "neuro_san_studio.agent_network_consultant.consultant_job_files.time.sleep",
            side_effect=self._write_answer,
        ):
            answer = self.job_files.ask("Need guidance", timeout=5.0)

        self.assertEqual("operator answer", answer)
        self.assertFalse((self.job_directory / "job-1.question.txt").exists())
        self.assertFalse((self.job_directory / "job-1.answer.txt").exists())

    def test_ask_rejects_non_nsflow_use(self) -> None:
        """Report an actionable error instead of waiting without a job directory."""
        with patch.dict(os.environ, {"NSFLOW_JOB_DIR": ""}):
            inactive_job_files = ConsultantJobFiles()
            with self.assertRaisesRegex(RuntimeError, "outside an nsflow job"):
                inactive_job_files.ask("Need guidance", timeout=5.0)

    def test_ask_times_out_and_removes_the_question(self) -> None:
        """Stop waiting at the monotonic deadline and remove the published question."""
        clock_values = [100.0, 105.0]
        with patch(
            "neuro_san_studio.agent_network_consultant.consultant_job_files.time.monotonic",
            side_effect=partial(self._advance_clock, clock_values),
        ):
            with self.assertRaisesRegex(TimeoutError, "within 5 seconds"):
                self.job_files.ask("Need guidance", timeout=5.0)

        self.assertFalse((self.job_directory / "job-1.question.txt").exists())

    def test_ask_reports_an_unreadable_answer_and_removes_the_question(self) -> None:
        """Propagate an answer-file read error without leaving a stale question."""
        answer_path = self.job_directory / "job-1.answer.txt"
        answer_path.write_text("answer", encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=PermissionError("answer is unreadable")):
            with self.assertRaisesRegex(PermissionError, "answer is unreadable"):
                self.job_files.ask("Need guidance", timeout=5.0)

        self.assertFalse((self.job_directory / "job-1.question.txt").exists())

    def test_ask_rejects_a_nonpositive_timeout(self) -> None:
        """Reject a timeout that cannot provide bounded polling."""
        with self.assertRaisesRegex(ValueError, "timeout"):
            self.job_files.ask("Need guidance", timeout=0.0)
