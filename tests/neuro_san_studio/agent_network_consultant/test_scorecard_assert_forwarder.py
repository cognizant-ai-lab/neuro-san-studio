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

"""Every reusable fixture criterion is reported, not only the first that failed."""

import concurrent.futures
from functools import partial
from unittest import TestCase

from neuro_san.test.driver.assert_capture import AssertCapture

from neuro_san_studio.agent_network_consultant.scorecard_assert_forwarder import ScorecardAssertForwarder


class TestScorecardAssertForwarder(TestCase):
    """Verify every fixture criterion result is recorded safely."""

    @staticmethod
    def _forwarder() -> ScorecardAssertForwarder:
        """
        Return the same forwarding stack used by the fixture runner.

        :return: The resulting value.
        """
        return ScorecardAssertForwarder(TestCase())

    @staticmethod
    def _record_failed_attempt(asserts: ScorecardAssertForwarder, _index: int) -> None:
        """
        Record one concurrent failed criterion attempt.

        :param asserts: The assertion forwarder used to collect fixture results.
        :param _index: The unused executor item required by the mapping interface.
        """
        AssertCapture(asserts).assertIn("KPIs", "{}")

    def test_all_failing_criteria_are_captured_not_just_the_first(self) -> None:
        """
        The bug: neuro-san checks every criterion, then re-raises only asserts[0].
        """
        asserts = TestScorecardAssertForwarder._forwarder()
        capture = AssertCapture(asserts)  # the real wrapper the driver puts in front of us
        body = '{"actions": []}'
        for keyword in ("actions", "owners", "timelines", "KPIs"):
            capture.assertIn(keyword, body)

        failing: list[str] = []
        for name, met, total in asserts.scorecard():
            if met < total:
                failing.append(name)
        self.assertEqual(failing, ["contains 'owners'", "contains 'timelines'", "contains 'KPIs'"])
        # AssertCapture swallowed them all, which is exactly why we record on the way past.
        self.assertEqual(len(capture.get_asserts()), 3)

    def test_a_flaky_criterion_reads_as_flaky_not_broken(self) -> None:
        """
        Repeated attempts come from success_ratio. One pass in three is a different problem from zero in three, and
        reporting only the first exception hides the difference.
        """
        asserts = TestScorecardAssertForwarder._forwarder()
        capture = AssertCapture(asserts)
        for body in ('{"KPIs": 1}', "{}", "{}"):
            capture.assertIn("KPIs", body)

        scorecard: list[tuple[str, int, int]] = asserts.scorecard()
        self.assertEqual(scorecard, [("contains 'KPIs'", 1, 3)])

    def test_parallel_iterations_do_not_drop_counts(self) -> None:
        """
        success_ratio iterations run concurrently over a shared forwarder.
        """
        asserts = TestScorecardAssertForwarder._forwarder()
        attempts = 200

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(partial(TestScorecardAssertForwarder._record_failed_attempt, asserts), range(attempts)))

        self.assertEqual(asserts.scorecard(), [("contains 'KPIs'", 0, attempts)])

    def test_gist_equivocation_check_is_not_reported_as_a_criterion(self) -> None:
        """
        gist_agent_evaluator asserts assertEqual(only_one, True) internally.
        """
        asserts = TestScorecardAssertForwarder._forwarder()
        AssertCapture(asserts).assertEqual(True, True)
        self.assertFalse(asserts.scorecard())
