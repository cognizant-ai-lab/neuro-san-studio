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

"""The reusable per-fixture results file consumed by the UI."""

import json
import logging
import os
import shutil
import tempfile
from functools import partial
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector


class TestFixtureRunner(TestCase):
    """Verify fixture execution, reporting, and file restoration behavior."""

    def setUp(self) -> None:
        """Create and configure one isolated nsflow job directory."""
        self.tmp_path = Path(tempfile.mkdtemp())
        self.enterContext(
            patch.dict(
                os.environ,
                {"NSFLOW_JOB_ID": "job1", "NSFLOW_JOB_DIR": str(self.tmp_path)},
            )
        )

    def tearDown(self) -> None:
        """Remove the isolated nsflow job directory after each test."""
        shutil.rmtree(self.tmp_path)

    def _job(self) -> Path:
        """
        Return the configured temporary nsflow results file.

        :return: The resulting value.
        """
        return self.tmp_path / "job1.results.json"

    @staticmethod
    def _fail_with_api_key_error(_fixture_path: str) -> None:
        """
        Emit the provider marker before the driver reports its resulting assertion.

        :param _fixture_path: The unused fixture path required by the patched interface.
        :raises AssertionError: Raised when the requested operation cannot complete.
        """
        logging.getLogger("provider").error("API KEY error detected: invalid credential")
        raise AssertionError("response did not satisfy the fixture")

    @staticmethod
    def _return_driver(driver: Mock, _asserts: object, _fixture_name: str) -> Mock:
        """
        Return the configured driver through the fixture-runner factory interface.

        :param driver: The configured fixture driver.
        :param _asserts: The asserts value.
        :param _fixture_name: The unused fixture name required by the patched interface.
        :return: The resulting value.
        """
        return driver

    @staticmethod
    def _ignore_thinking_trace(_fixture_name: str, _started: float) -> None:
        """
        Disable thinking-trace output for the isolated fixture test.

        :param _fixture_name: The unused fixture name required by the patched interface.
        :param _started: The unused fixture start time required by the patched interface.
        """

    def test_a_subset_round_keeps_the_verdicts_it_did_not_re_run(self) -> None:
        """
        The whole point of merging: the runner re-tests only what was failing, and a re-check of one fixture says
        nothing about the others -- they must not vanish from the UI.

        """
        path = self._job()
        FixtureRunner.write_fixture_results(
            [
                {"fixture": "a.hocon", "passed": True, "message": None, "infrastructure_error": False},
                {
                    "fixture": "b.hocon",
                    "passed": False,
                    "message": "'owners' not found",
                    "infrastructure_error": False,
                },
            ]
        )
        FixtureRunner.write_fixture_results(
            [{"fixture": "b.hocon", "passed": True, "message": None, "infrastructure_error": False}]
        )

        recorded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(recorded), {"a.hocon", "b.hocon"})
        self.assertIs(recorded.get("a.hocon", {}).get("passed"), True)
        self.assertIs(recorded.get("b.hocon", {}).get("passed"), True)
        self.assertIsNone(recorded.get("b.hocon", {}).get("message"))

    def test_failure_reason_and_infrastructure_flag_survive(self) -> None:
        """
        Failure details survive serialization to the UI results file.

        """
        path = self._job()
        FixtureRunner.write_fixture_results(
            [{"fixture": "c.hocon", "passed": False, "message": "TIMEOUT_ISSUE: ...", "infrastructure_error": True}]
        )
        recorded = json.loads(path.read_text(encoding="utf-8")).get("c.hocon")
        self.assertEqual(
            recorded,
            {"passed": False, "message": "TIMEOUT_ISSUE: ...", "infrastructure_error": True},
        )

    def test_no_file_written_outside_an_nsflow_job(self) -> None:
        """
        Plain CLI use must not litter -- and has nowhere to write to anyway.

        """
        with patch.dict(os.environ, {"NSFLOW_JOB_ID": ""}):
            FixtureRunner.write_fixture_results([{"fixture": "a.hocon", "passed": True}])
        self.assertFalse(list(self.tmp_path.iterdir()))

    def test_a_corrupt_file_does_not_fail_the_test_run(self) -> None:
        """
        The runner may be mid-write when something else reads it; losing old verdicts beats raising out of a suite
        that has already finished running.

        """
        path = self._job()
        path.write_text("{not json", encoding="utf-8")
        with self.assertLogs("network_consultant", level="WARNING") as captured:
            FixtureRunner.write_fixture_results([{"fixture": "a.hocon", "passed": True}])
        recorded = json.loads(path.read_text(encoding="utf-8")).get("a.hocon", {})
        self.assertIs(recorded.get("passed"), True)
        self.assertIn("Could not read existing fixture results", "\n".join(captured.output))

    def test_a_non_object_results_file_is_reported_and_replaced(self) -> None:
        """Report a valid JSON value with the wrong shape before replacing it with current results."""
        path = self._job()
        path.write_text("[]", encoding="utf-8")

        with self.assertLogs("network_consultant", level="WARNING") as captured:
            FixtureRunner.write_fixture_results([{"fixture": "a.hocon", "passed": True}])

        recorded = json.loads(path.read_text(encoding="utf-8")).get("a.hocon", {})
        self.assertIs(recorded.get("passed"), True)
        self.assertIn("Ignoring malformed fixture results", "\n".join(captured.output))

    def test_provider_api_key_error_is_an_infrastructure_failure(self) -> None:
        """
        Provider credential failures remain distinct from network behavior failures.

        """
        driver = Mock()

        driver.one_test.side_effect = TestFixtureRunner._fail_with_api_key_error
        with (
            patch.object(FixtureRunner, "_create_driver", partial(TestFixtureRunner._return_driver, driver)),
            patch.object(ThinkingTraceCollector, "write", TestFixtureRunner._ignore_thinking_trace),
        ):
            result = FixtureRunner.run_fixture("tests/fixtures/example.hocon")

        self.assertIs(result.get("infrastructure_error"), True)
        self.assertEqual(
            result.get("message"),
            "Provider API-key validation failed. Verify the configured credentials.",
        )

    def test_sensitive_values_are_redacted_from_returned_and_persisted_messages(self) -> None:
        """Remove credential values before a fixture verdict reaches callers or the results file."""
        secret = "sk-proj-example-secret-value"
        safe_message = FixtureRunner.redact_sensitive_text(f"OPENAI_API_KEY={secret}; Authorization: Bearer {secret}")
        verdict = {
            "fixture": "example.hocon",
            "passed": False,
            "message": safe_message,
            "infrastructure_error": False,
        }

        FixtureRunner.write_fixture_results([verdict])

        persisted_message = str(json.loads(self._job().read_text(encoding="utf-8")).get("example.hocon", {}))
        self.assertNotIn(secret, safe_message)
        self.assertNotIn(secret, persisted_message)
        self.assertIn("[REDACTED]", safe_message)

    def test_report_names_every_failure_and_the_total_but_not_the_passing_text(self) -> None:
        """Include every failed criterion and omit passing criterion text."""
        scorecard = [("contains 'actions'", 1, 1), ("contains 'KPIs'", 0, 1)]

        message: str = FixtureRunner.scorecard_message(AssertionError("first failure"), scorecard)

        self.assertIn("1 of 2 acceptance criteria failing", message)
        self.assertIn("contains 'KPIs'", message)
        self.assertNotIn("contains 'actions'", message)

    def test_falls_back_to_the_raw_cause_when_nothing_was_recorded(self) -> None:
        """Retain the driver's original error when no scorecard entries exist."""
        self.assertEqual(FixtureRunner.scorecard_message(AssertionError("raw"), []), "raw")
