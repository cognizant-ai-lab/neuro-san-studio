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

"""Every acceptance criterion is reported, not just the first that failed."""

import concurrent.futures
from unittest import TestCase

from neuro_san.test.driver.assert_capture import AssertCapture

from neuro_san_studio.network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.network_consultant.scorecard_assert_forwarder import ScorecardAssertForwarder


class TestScorecard:
    """Test scorecard."""

    @staticmethod
    def _forwarder() -> ScorecardAssertForwarder:
        """Return the same forwarding stack used by the fixture runner."""
        return ScorecardAssertForwarder(TestCase())

    @staticmethod
    def test_all_failing_criteria_are_captured_not_just_the_first() -> None:
        """The bug: neuro-san checks every criterion, then re-raises only asserts[0]."""
        asserts = TestScorecard._forwarder()
        capture = AssertCapture(asserts)  # the real wrapper the driver puts in front of us
        body = '{"actions": []}'
        for keyword in ("actions", "owners", "timelines", "KPIs"):
            capture.assertIn(keyword, body)

        failing = [name for name, met, total in asserts.scorecard() if met < total]
        assert failing == ["contains 'owners'", "contains 'timelines'", "contains 'KPIs'"]
        # AssertCapture swallowed them all, which is exactly why we record on the way past.
        assert len(capture.get_asserts()) == 3

    @staticmethod
    def test_report_names_every_failure_and_the_total_but_not_the_passing_text() -> None:
        """Failure reports include every failed criterion but omit passing text."""
        asserts = TestScorecard._forwarder()
        capture = AssertCapture(asserts)
        capture.assertIn("actions", '{"actions": []}')
        capture.assertIn("KPIs", '{"actions": []}')

        message = FixtureRunner.scorecard_message(AssertionError("first failure"), asserts.scorecard())
        # The count carries the scale, so the passing criteria need not be spelled out -- this
        # message is persisted to the results file and shown in the UI.
        assert "1 of 2 acceptance criteria failing" in message
        assert "contains 'KPIs'" in message
        assert "contains 'actions'" not in message

    @staticmethod
    def test_a_flaky_criterion_reads_as_flaky_not_broken() -> None:
        """Repeated attempts come from success_ratio. One pass in three is a different problem
        from zero in three, and reporting only the first exception hides the difference."""
        asserts = TestScorecard._forwarder()
        capture = AssertCapture(asserts)
        for body in ('{"KPIs": 1}', "{}", "{}"):
            capture.assertIn("KPIs", body)

        message = FixtureRunner.scorecard_message(AssertionError("boom"), asserts.scorecard())
        assert "met on 1 of 3 attempts" in message

    @staticmethod
    def test_parallel_iterations_do_not_drop_counts() -> None:
        """success_ratio iterations run concurrently over a shared forwarder."""
        asserts = TestScorecard._forwarder()
        attempts = 200

        # The executor requires a one-argument callback; keeping it local captures this test's tally.
        def one_attempt(_i: int) -> None:
            """Record one concurrent failed criterion attempt."""
            AssertCapture(asserts).assertIn("KPIs", "{}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(one_attempt, range(attempts)))

        assert asserts.scorecard() == [("contains 'KPIs'", 0, attempts)]

    @staticmethod
    def test_gist_equivocation_check_is_not_reported_as_a_criterion() -> None:
        """gist_agent_evaluator asserts assertEqual(only_one, True) internally."""
        asserts = TestScorecard._forwarder()
        AssertCapture(asserts).assertEqual(True, True)
        assert asserts.scorecard() == []

    @staticmethod
    def test_falls_back_to_the_raw_cause_when_nothing_was_recorded() -> None:
        """An empty scorecard retains the driver's original error message."""
        assert FixtureRunner.scorecard_message(AssertionError("raw"), []) == "raw"
