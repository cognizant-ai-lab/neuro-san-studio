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

"""Tests for chart-ready Agent Network Consultant progress tracking."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.progress_tracker import ProgressTracker


class TestProgressTracker(TestCase):
    """Verify full-suite checkpoints persist complete, deduplicated chart state."""

    def test_advances_improvement_iterations(self) -> None:
        """Keep chart iteration numbering with the chart progress state."""
        tracker = ProgressTracker()

        self.assertEqual(tracker.next_improvement_iteration(), 1)
        self.assertEqual(tracker.next_improvement_iteration(), 2)

    def test_record_rejects_an_unknown_checkpoint(self) -> None:
        """Reject a checkpoint that the chart cannot interpret."""
        tracker = ProgressTracker()

        with self.assertRaisesRegex(ValueError, "Unsupported progress checkpoint"):
            tracker.record([], "unknown", 0)

    def test_record_writes_changed_checkpoints_and_skips_an_identical_repeat(self) -> None:
        """Append distinct checkpoints while suppressing a repeated final result."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(
                os.environ,
                {"NSFLOW_JOB_ID": "job-1", "NSFLOW_JOB_DIR": temporary_directory},
            ):
                tracker = ProgressTracker()
                before: list[dict[str, Any]] = [
                    {"fixture": "a.hocon", "passed": True},
                    {"fixture": "b.hocon", "passed": False},
                ]
                after: list[dict[str, Any]] = [
                    {"fixture": "a.hocon", "passed": True},
                    {"fixture": "b.hocon", "passed": True},
                ]
                tracker.record(before, "before", 2)
                tracker.record(after, "after", 2)
                tracker.record(after, "after", 2)

            entries: list[dict[str, Any]] = []
            progress_path = Path(temporary_directory) / "job-1.progress.jsonl"
            for line in progress_path.read_text(encoding="utf-8").splitlines():
                entries.append(json.loads(line))

        self.assertEqual(2, len(entries))
        self.assertEqual([1], entries[0].get("segments"))
        self.assertEqual([2], entries[1].get("segments"))
        self.assertEqual(2, entries[1].get("passed"))

    def test_synchronize_full_suite_replaces_inferred_cohorts_without_writing_a_checkpoint(self) -> None:
        """Use a non-terminal full-suite probe as the baseline for the next published subset result."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(
                os.environ,
                {"NSFLOW_JOB_ID": "job-1", "NSFLOW_JOB_DIR": temporary_directory},
            ):
                tracker = ProgressTracker()
                tracker.record(
                    [
                        {"fixture": "a.hocon", "passed": True},
                        {"fixture": "b.hocon", "passed": False},
                        {"fixture": "c.hocon", "passed": True},
                    ],
                    "before",
                    3,
                )
                tracker.synchronize_full_suite(
                    [
                        {"fixture": "a.hocon", "passed": False},
                        {"fixture": "b.hocon", "passed": True},
                        {"fixture": "c.hocon", "passed": False},
                    ]
                )
                tracker.record(
                    [{"fixture": "c.hocon", "passed": True}],
                    "iteration",
                    3,
                    1,
                )

            entries: list[dict[str, Any]] = []
            progress_path = Path(temporary_directory) / "job-1.progress.jsonl"
            for line in progress_path.read_text(encoding="utf-8").splitlines():
                entries.append(json.loads(line))

        self.assertEqual(2, len(entries))
        self.assertEqual("iteration", entries[1].get("checkpoint"))
        self.assertEqual([1, 1], entries[1].get("segments"))
        self.assertEqual(2, entries[1].get("passed"))
