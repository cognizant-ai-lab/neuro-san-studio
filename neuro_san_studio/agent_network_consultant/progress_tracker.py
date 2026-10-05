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
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Optional

from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles


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
        """
        Resolve optional nsflow output after constructing the tracker state.
        """
        self.path = ConsultantJobFiles.path("progress.jsonl")

    def record(
        self,
        results: list[dict[str, Any]],
        checkpoint: str,
        total_fixture_count: int,
        improvement_iteration: Optional[int] = None,
    ) -> None:
        """
        Update cumulative state and, for nsflow jobs, append one complete checkpoint.

        :param results: The fixture result records.
        :param checkpoint: The progress checkpoint category.
        :param total_fixture_count: The number of fixtures in the complete suite.
        :param improvement_iteration: The optional displayed improvement iteration.
        """
        passing, tested = self._fixture_sets(results)
        if checkpoint in {"generated", "before", "after"}:
            segments = self._reset_cohorts(passing)
        else:
            segments = self._update_cohorts(passing, tested)

        if not self.path:
            return
        entry = self._entry(checkpoint, improvement_iteration, total_fixture_count, segments)
        # Some paths confirm the same full suite twice in a row (e.g. a subset re-check's
        # confirmation run, followed by a consultant that then makes no edit). One After bar per
        # result, not two identical ones side by side.
        if self._duplicates_last_entry(entry):
            return
        self.check_number += 1
        self.last_entry = entry
        with open(self.path, "a", encoding="utf-8") as progress_file:
            progress_file.write(json.dumps(entry) + "\n")

    @staticmethod
    def _fixture_sets(results: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
        """
        Return the passing and tested fixture names from one result set.

        :param results: The fixture result records.
        :return: The passing fixture names followed by all tested fixture names.
        """
        passing: set[str] = set()
        tested: set[str] = set()
        for result in results:
            fixture = result.get("fixture", "")
            tested.add(fixture)
            if result.get("passed"):
                passing.add(fixture)
        return passing, tested

    def _reset_cohorts(self, passing: set[str]) -> list[int]:
        """
        Replace inferred cohort state with an authoritative full-suite result.

        :param passing: The fixtures passing in the complete suite.
        :return: The single full-suite chart segment.
        """
        self.fixture_cohorts = {}
        for fixture in passing:
            self.fixture_cohorts.update({fixture: 0})
        self.next_cohort = 1
        return [len(passing)]

    def _update_cohorts(self, passing: set[str], tested: set[str]) -> list[int]:
        """
        Merge a subset result into retained fixture cohorts.

        :param passing: The fixtures passing in the subset.
        :param tested: Every fixture evaluated in the subset.
        :return: The chart segment sizes after the update.
        """
        cohort = self.next_cohort
        for fixture in tested:
            if fixture in passing and fixture not in self.fixture_cohorts:
                self.fixture_cohorts.update({fixture: cohort})
            elif fixture not in passing:
                self.fixture_cohorts.pop(fixture, None)
        self.next_cohort += 1
        return self._cohort_segments()

    def _cohort_segments(self) -> list[int]:
        """
        Count passing fixtures in each chart cohort.

        :return: The ordered chart segment sizes.
        """
        segments: list[int] = []
        for cohort_index in range(self.next_cohort):
            cohort_size = 0
            for fixture_cohort in self.fixture_cohorts.values():
                if fixture_cohort == cohort_index:
                    cohort_size += 1
            segments.append(cohort_size)
        return segments

    def _entry(
        self,
        checkpoint: str,
        improvement_iteration: Optional[int],
        total_fixture_count: int,
        segments: list[int],
    ) -> dict[str, Any]:
        """
        Build one complete progress entry.

        :param checkpoint: The progress checkpoint category.
        :param improvement_iteration: The optional displayed improvement iteration.
        :param total_fixture_count: The number of fixtures in the complete suite.
        :param segments: The passing-fixture counts grouped by cohort.
        :return: The serializable progress entry.
        """
        return {
            "check": self.check_number + 1,
            "checkpoint": checkpoint,
            "improvement_iteration": improvement_iteration,
            "passed": min(len(self.fixture_cohorts), total_fixture_count),
            "total": total_fixture_count,
            "segments": segments,
        }

    def _duplicates_last_entry(self, entry: dict[str, Any]) -> bool:
        """
        Return whether an entry repeats the previous result apart from its check number.

        :param entry: The new progress entry.
        :return: Whether the new entry duplicates the previous result.
        """
        if self.last_entry is None:
            return False
        comparable_entry = dict(entry)
        comparable_entry.update({"check": 0})
        comparable_last_entry = dict(self.last_entry)
        comparable_last_entry.update({"check": 0})
        return comparable_entry == comparable_last_entry
