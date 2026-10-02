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

"""Chart-ready progress tracking for nsflow-launched consultant runs."""

import json
import os
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Optional

from neuro_san_studio.network_consultant.fixture_runner import NSFLOW_JOB_DIR
from neuro_san_studio.network_consultant.fixture_runner import NSFLOW_JOB_ID


@dataclass
class ProgressTracker:
    """Persist chart-ready test checkpoints for an nsflow-launched run.

    The runner frequently re-tests only the fixtures that were failing.  The chart still needs
    to show progress against the *whole* suite, so this tracker retains the last known state of
    untested fixtures and assigns newly passing fixtures to a new blue cohort on each iteration.
    A full-suite Before/After checkpoint resets that assumption with authoritative results.
    """

    path: str | None = field(init=False)
    check_number: int = 0
    fixture_cohorts: dict[str, int] = field(default_factory=dict)
    next_cohort: int = 1
    last_entry: Optional[dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Resolve optional nsflow output after constructing the tracker state."""
        self.path = (
            os.path.join(NSFLOW_JOB_DIR, f"{NSFLOW_JOB_ID}.progress.jsonl")
            if NSFLOW_JOB_ID and NSFLOW_JOB_DIR
            else None
        )

    def record(
        self,
        results: list[dict[str, Any]],
        checkpoint: str,
        total_fixture_count: int,
        improvement_iteration: Optional[int] = None,
    ) -> None:
        """Update cumulative state and, for nsflow jobs, append one complete checkpoint."""
        passing = {result.get("fixture", "") for result in results if result.get("passed")}
        tested = {result.get("fixture", "") for result in results}

        if checkpoint in {"generated", "before", "after"}:
            # These checkpoints always come from the complete suite and therefore replace every
            # inferred state left over from targeted re-tests.
            self.fixture_cohorts = {fixture: 0 for fixture in passing}
            self.next_cohort = 1
            segments = [len(passing)]
        else:
            cohort = self.next_cohort
            for fixture in tested:
                if fixture in passing:
                    if fixture not in self.fixture_cohorts:
                        self.fixture_cohorts.update({fixture: cohort})
                else:
                    self.fixture_cohorts.pop(fixture, None)
            self.next_cohort += 1
            segments = [
                sum(1 for fixture_cohort in self.fixture_cohorts.values() if fixture_cohort == cohort_index)
                for cohort_index in range(self.next_cohort)
            ]

        if not self.path:
            return
        entry = {
            "check": self.check_number + 1,
            "checkpoint": checkpoint,
            "improvement_iteration": improvement_iteration,
            "passed": min(len(self.fixture_cohorts), total_fixture_count),
            "total": total_fixture_count,
            "segments": segments,
        }
        # Some paths confirm the same full suite twice in a row (e.g. a subset re-check's
        # confirmation run, followed by a consultant that then makes no edit). One After bar per
        # result, not two identical ones side by side.
        if self.last_entry is not None and {**entry, "check": 0} == {**self.last_entry, "check": 0}:
            return
        self.check_number += 1
        self.last_entry = entry
        with open(self.path, "a", encoding="utf-8") as progress_file:
            progress_file.write(json.dumps(entry) + "\n")
