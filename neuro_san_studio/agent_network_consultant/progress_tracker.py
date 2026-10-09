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

"""Chart-ready progress tracking for nsflow-launched Agent Network Consultant runs."""

import json
from typing import Any
from typing import ClassVar
from typing import Literal

from neuro_san_studio.agent_network_consultant.consultant_job_files import ConsultantJobFiles


class ProgressTracker:
    """Persist chart-ready test checkpoints for an nsflow-launched run.

    The runner frequently re-tests only the fixtures that were failing.  The chart still needs
    to show progress against the *whole* suite, so this tracker retains the last known state of
    untested fixtures and assigns newly passing fixtures to a new blue cohort on each iteration.
    A full-suite Before/After checkpoint resets that assumption with authoritative results.
    """

    VALID_CHECKPOINTS: ClassVar[tuple[str, ...]] = ("generated", "before", "iteration", "after")

    def __init__(self) -> None:
        """
        Initialize chart state and resolve optional nsflow output.
        """
        self._path = ConsultantJobFiles().path("progress.jsonl")
        self._check_number = 0
        self._improvement_iteration = 0
        self._fixture_cohorts: dict[str, int] = {}
        self._next_cohort = 1
        self._last_entry: dict[str, Any] | None = None

    def next_improvement_iteration(self) -> int:
        """
        Advance and return the chart's improvement iteration.

        :return: The next improvement iteration number.
        """
        self._improvement_iteration += 1
        return self._improvement_iteration

    def record(
        self,
        results: list[dict[str, Any]],
        checkpoint: Literal["generated", "before", "iteration", "after"],
        total_fixture_count: int,
        improvement_iteration: int | None = None,
    ) -> None:
        """
        Update cumulative state and, for nsflow jobs, append one complete checkpoint.

        :param results: The fixture result records.
        :param checkpoint: The progress checkpoint category.
        :param total_fixture_count: The number of fixtures in the complete suite.
        :param improvement_iteration: The optional displayed improvement iteration.
        :raises ValueError: If the checkpoint is not a supported progress category.
        """
        if checkpoint not in self.VALID_CHECKPOINTS:
            raise ValueError(
                f"Unsupported progress checkpoint {checkpoint!r}; expected one of {self.VALID_CHECKPOINTS}."
            )
        passing, tested = self._fixture_sets(results)
        is_complete_suite = total_fixture_count > 0 and len(tested) == total_fixture_count
        if checkpoint in {"generated", "before", "after"} or is_complete_suite:
            segments = self._reset_cohorts(passing)
        else:
            segments = self._update_cohorts(passing, tested)

        if not self._path:
            return
        entry = self._entry(checkpoint, improvement_iteration, total_fixture_count, segments)
        # Some paths confirm the same full suite twice in a row (e.g. a subset re-check's
        # confirmation run, followed by a consultant that then makes no edit). One After bar per
        # result, not two identical ones side by side.
        if self._duplicates_last_entry(entry):
            return
        self._check_number += 1
        self._last_entry = entry
        with open(self._path, "a", encoding="utf-8") as progress_file:
            progress_file.write(json.dumps(entry) + "\n")

    def synchronize_full_suite(self, results: list[dict[str, Any]]) -> None:
        """
        Replace inferred fixture cohorts from a full-suite result without publishing a checkpoint.

        :param results: The complete fixture result records.
        """
        passing, _tested = self._fixture_sets(results)
        self._reset_cohorts(passing)

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
        self._fixture_cohorts = {}
        for fixture in passing:
            self._fixture_cohorts.update({fixture: 0})
        self._next_cohort = 1
        return [len(passing)]

    def _update_cohorts(self, passing: set[str], tested: set[str]) -> list[int]:
        """
        Merge a subset result into retained fixture cohorts.

        :param passing: The fixtures passing in the subset.
        :param tested: Every fixture evaluated in the subset.
        :return: The chart segment sizes after the update.
        """
        cohort = self._next_cohort
        for fixture in tested:
            if fixture in passing and fixture not in self._fixture_cohorts:
                self._fixture_cohorts.update({fixture: cohort})
            elif fixture not in passing:
                self._fixture_cohorts.pop(fixture, None)
        self._next_cohort += 1
        return self._cohort_segments()

    def _cohort_segments(self) -> list[int]:
        """
        Count passing fixtures in each chart cohort.

        :return: The ordered chart segment sizes.
        """
        segments: list[int] = []
        for cohort_index in range(self._next_cohort):
            cohort_size = 0
            for fixture_cohort in self._fixture_cohorts.values():
                if fixture_cohort == cohort_index:
                    cohort_size += 1
            segments.append(cohort_size)
        return segments

    def _entry(
        self,
        checkpoint: Literal["generated", "before", "iteration", "after"],
        improvement_iteration: int | None,
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
            "check": self._check_number + 1,
            "checkpoint": checkpoint,
            "improvement_iteration": improvement_iteration,
            "passed": min(len(self._fixture_cohorts), total_fixture_count),
            "total": total_fixture_count,
            "segments": segments,
        }

    def _duplicates_last_entry(self, entry: dict[str, Any]) -> bool:
        """
        Return whether an entry repeats the previous result apart from its check number.

        :param entry: The new progress entry.
        :return: Whether the new entry duplicates the previous result.
        """
        if self._last_entry is None:
            return False
        comparable_entry = dict(entry)
        comparable_entry.update({"check": 0})
        comparable_last_entry = dict(self._last_entry)
        comparable_last_entry.update({"check": 0})
        return comparable_entry == comparable_last_entry
