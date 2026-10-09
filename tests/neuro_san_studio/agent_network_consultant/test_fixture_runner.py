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

"""Tests for reusable Agent Network Consultant fixture execution."""

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.fixture_driver import FixtureDriver
from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.sensitive_data_redactor import SensitiveDataRedactor
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector


class TestFixtureRunner(TestCase):
    """Verify fixture execution, reporting, and source-file preservation."""

    def setUp(self) -> None:
        """Create one isolated job, fixture tree, trace collector, and runner."""
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_path)
        self.enterContext(
            patch.dict(
                os.environ,
                {"NSFLOW_JOB_ID": "job1", "NSFLOW_JOB_DIR": str(self.tmp_path)},
            )
        )
        self.fixture_root = self.tmp_path / "fixtures"
        self.fixture_root.mkdir()
        self.trace_collector = ThinkingTraceCollector(
            "run-one",
            basis_directory="",
            output_directory=self.tmp_path / "thinking",
        )
        self.runner = FixtureRunner(
            "run-one",
            fixture_root=str(self.fixture_root),
            trace_collector=self.trace_collector,
        )

    def _job(self) -> Path:
        """
        Return the configured temporary nsflow results file.

        :return: The result sidecar path.
        """
        return self.tmp_path / "job1.results.json"

    @staticmethod
    def _fail_with_api_key_error(_fixture_path: str) -> None:
        """
        Emit the provider marker before the driver reports its resulting assertion.

        :param _fixture_path: The unused fixture path required by the patched interface.
        :raises AssertionError: Always raised after the provider log is emitted.
        """
        logging.getLogger("provider").error("API KEY error detected: invalid credential")
        raise AssertionError("response did not satisfy the fixture")

    def test_a_subset_round_keeps_the_verdicts_it_did_not_re_run(self) -> None:
        """Keep prior verdicts for fixtures absent from a subset re-test."""
        path = self._job()
        self.runner.write_fixture_results(
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
        self.runner.write_fixture_results(
            [{"fixture": "b.hocon", "passed": True, "message": None, "infrastructure_error": False}]
        )

        recorded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(recorded), {"a.hocon", "b.hocon"})
        self.assertIs(recorded.get("a.hocon", {}).get("passed"), True)
        self.assertIs(recorded.get("b.hocon", {}).get("passed"), True)
        self.assertIsNone(recorded.get("b.hocon", {}).get("message"))

    def test_failure_reason_and_infrastructure_flag_survive(self) -> None:
        """Preserve failure details when serializing UI fixture results."""
        path = self._job()
        self.runner.write_fixture_results(
            [{"fixture": "c.hocon", "passed": False, "message": "TIMEOUT_ISSUE: ...", "infrastructure_error": True}]
        )
        recorded = json.loads(path.read_text(encoding="utf-8")).get("c.hocon")
        self.assertEqual(
            recorded,
            {"passed": False, "message": "TIMEOUT_ISSUE: ...", "infrastructure_error": True},
        )

    def test_no_file_written_outside_an_nsflow_job(self) -> None:
        """Skip sidecar output when no nsflow job is active."""
        with patch.dict(os.environ, {"NSFLOW_JOB_ID": ""}):
            FixtureRunner("run-one").write_fixture_results([{"fixture": "a.hocon", "passed": True}])
        self.assertFalse(self._job().exists())

    def test_a_corrupt_file_does_not_fail_the_test_run(self) -> None:
        """Report and replace a corrupt results sidecar after the suite has completed."""
        path = self._job()
        path.write_text("{not json", encoding="utf-8")
        with self.assertLogs("neuro_san_studio.agent_network_consultant.fixture_runner", level="WARNING") as captured:
            self.runner.write_fixture_results([{"fixture": "a.hocon", "passed": True}])
        recorded = json.loads(path.read_text(encoding="utf-8")).get("a.hocon", {})
        self.assertIs(recorded.get("passed"), True)
        self.assertIn("Could not read existing fixture results", "\n".join(captured.output))

    def test_a_non_object_results_file_is_reported_and_replaced(self) -> None:
        """Report a valid JSON value with the wrong shape before replacing it."""
        path = self._job()
        path.write_text("[]", encoding="utf-8")

        with self.assertLogs("neuro_san_studio.agent_network_consultant.fixture_runner", level="INFO") as captured:
            self.runner.write_fixture_results([{"fixture": "a.hocon", "passed": True}])

        recorded = json.loads(path.read_text(encoding="utf-8")).get("a.hocon", {})
        self.assertIs(recorded.get("passed"), True)
        self.assertIn("Ignoring malformed fixture results", "\n".join(captured.output))

    def test_provider_api_key_error_is_an_infrastructure_failure(self) -> None:
        """Keep provider credential failures distinct from network behavior failures."""
        driver = Mock()
        driver.one_test.side_effect = self._fail_with_api_key_error
        with patch(
            "neuro_san_studio.agent_network_consultant.fixture_driver.DataDrivenAgentTestDriver",
            return_value=driver,
        ):
            result = self.runner.run_fixture("tests/fixtures/example.hocon")

        self.assertIs(result.get("infrastructure_error"), True)
        self.assertEqual(
            result.get("message"),
            "Provider API-key validation failed. Verify the configured credentials.",
        )

    def test_programming_error_propagates_instead_of_becoming_an_infrastructure_verdict(self) -> None:
        """Expose runner defects instead of misreporting them as infrastructure failures."""
        with (
            patch.object(FixtureDriver, "execute", side_effect=TypeError("programming defect")),
            self.assertRaisesRegex(TypeError, "programming defect"),
        ):
            self.runner.run_fixture("tests/fixtures/example.hocon")

    def test_expected_file_error_returns_a_redacted_infrastructure_verdict(self) -> None:
        """Report an expected fixture I/O failure without exposing credentials."""
        secret = "sk-proj-example-secret-value"
        with (
            patch.object(FixtureDriver, "execute", side_effect=OSError(f"OPENAI_API_KEY={secret}")),
            self.assertLogs("neuro_san_studio.agent_network_consultant.fixture_executor", level="WARNING") as captured,
        ):
            result = self.runner.run_fixture("tests/fixtures/example.hocon")

        message = str(result.get("message"))
        logged = "\n".join(captured.output)
        self.assertIs(result.get("infrastructure_error"), True)
        self.assertNotIn(secret, message)
        self.assertNotIn(secret, logged)
        self.assertIn("[REDACTED]", message)
        self.assertIn("[REDACTED]", logged)

    def test_thinking_trace_failure_does_not_replace_a_completed_verdict(self) -> None:
        """Keep optional diagnostic I/O from changing a completed fixture result."""
        with (
            patch.object(FixtureDriver, "execute"),
            patch.object(self.trace_collector, "write", side_effect=OSError("trace unavailable")),
            self.assertLogs("neuro_san_studio.agent_network_consultant.fixture_executor", level="WARNING") as captured,
        ):
            result = self.runner.run_fixture("tests/fixtures/example.hocon")

        self.assertIs(result.get("passed"), True)
        self.assertIn("Could not collect thinking trace", "\n".join(captured.output))

    def test_unknown_subset_fixture_is_reported_before_any_fixture_runs(self) -> None:
        """Reject every unknown selection before any fixture starts."""
        fixture_directory = self.fixture_root / "example"
        fixture_directory.mkdir()
        (fixture_directory / "valid.hocon").write_text("{}", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "missing.hocon"):
            self.runner.run_all_tests("example", ["valid.hocon", "missing.hocon"])

    def test_sensitive_values_are_redacted_from_returned_and_persisted_messages(self) -> None:
        """Remove credential values before a verdict reaches callers or the results sidecar."""
        secret = "sk-proj-example-secret-value"
        safe_message = SensitiveDataRedactor.redact_text(f"OPENAI_API_KEY={secret}; Authorization: Bearer {secret}")
        verdict = {
            "fixture": "example.hocon",
            "passed": False,
            "message": safe_message,
            "infrastructure_error": False,
        }

        self.runner.write_fixture_results([verdict])

        persisted_message = str(json.loads(self._job().read_text(encoding="utf-8")).get("example.hocon", {}))
        self.assertNotIn(secret, safe_message)
        self.assertNotIn(secret, persisted_message)
        self.assertIn("[REDACTED]", safe_message)
