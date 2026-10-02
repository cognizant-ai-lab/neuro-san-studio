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

"""Assertion forwarding that retains every fixture criterion result."""

import threading
from typing import Any
from unittest import TestCase

from neuro_san.test.unittest.unit_test_assert_forwarder import UnitTestAssertForwarder


# The external UnitTestAssertForwarder interface requires camelCase assertion method names.
class ScorecardAssertForwarder(UnitTestAssertForwarder):
    """Forward assertions while retaining per-criterion success counts."""

    def __init__(self, test_case: TestCase) -> None:
        """Create an insertion-ordered, thread-safe criterion tally."""
        super().__init__(test_case)
        self._tally: dict[str, list[int]] = {}
        self._lock = threading.Lock()

    def _record(self, criterion: str, method: str, *args: Any) -> None:
        """Run and tally one delegated assertion."""
        try:
            getattr(super(), method)(*args)
        except AssertionError:
            self._note(criterion, met=False)
            raise
        self._note(criterion, met=True)

    def _note(self, criterion: str, met: bool) -> None:
        """Record one criterion attempt without losing concurrent updates."""
        with self._lock:
            entry = self._tally.setdefault(criterion, [0, 0])
            entry[0] += int(met)
            entry[1] += 1

    def criteria_counts(self) -> tuple[int, int]:
        """Return criteria met on every attempt and criteria checked."""
        with self._lock:
            total = len(self._tally)
            met = sum(1 for met_count, attempts in self._tally.values() if met_count == attempts)
        return met, total

    def scorecard(self) -> list[tuple[str, int, int]]:
        """Return criterion, successes, and attempts in first-checked order."""
        with self._lock:
            return [(criterion, met, attempts) for criterion, (met, attempts) in self._tally.items()]

    def assertGist(self, gist: Any, acceptance_criteria: str, text_sample: Any, msg: Any = None) -> None:
        """Forward neuro-san's gist assertion and record its result."""
        self._record(acceptance_criteria, "assertGist", gist, acceptance_criteria, text_sample, msg)

    def assertNotGist(self, gist: Any, acceptance_criteria: str, text_sample: Any, msg: Any = None) -> None:
        """Forward neuro-san's negative gist assertion and record its result."""
        self._record(f"NOT: {acceptance_criteria}", "assertNotGist", gist, acceptance_criteria, text_sample, msg)

    def assertIn(self, member: Any, container: Any, msg: Any = None) -> None:
        """Forward a membership assertion and record its result."""
        self._record(f"contains {member!r}", "assertIn", member, container, msg)

    def assertNotIn(self, member: Any, container: Any, msg: Any = None) -> None:
        """Forward a negative membership assertion and record its result."""
        self._record(f"does not contain {member!r}", "assertNotIn", member, container, msg)

    def assertEqual(self, first: Any, second: Any, msg: Any = None) -> None:
        """Forward an equality assertion and record fixture criteria only."""
        if isinstance(first, bool) and second is True:
            super().assertEqual(first, second, msg)
            return
        self._record(f"equals {first!r}", "assertEqual", first, second, msg)

    def assertNotEqual(self, first: Any, second: Any, msg: Any = None) -> None:
        """Forward an inequality assertion and record its result."""
        self._record(f"does not equal {first!r}", "assertNotEqual", first, second, msg)

    def assertGreater(self, first: Any, second: Any, msg: Any = None) -> None:
        """Forward a greater-than assertion and record its result."""
        self._record(f"greater than {first!r}", "assertGreater", first, second, msg)

    def assertGreaterEqual(self, first: Any, second: Any, msg: Any = None) -> None:
        """Forward a greater-or-equal assertion and record its result."""
        self._record(f"not less than {first!r}", "assertGreaterEqual", first, second, msg)

    def assertLess(self, first: Any, second: Any, msg: Any = None) -> None:
        """Forward a less-than assertion and record its result."""
        self._record(f"less than {first!r}", "assertLess", first, second, msg)

    def assertLessEqual(self, first: Any, second: Any, msg: Any = None) -> None:
        """Forward a less-or-equal assertion and record its result."""
        self._record(f"not greater than {first!r}", "assertLessEqual", first, second, msg)
