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

"""The per-fixture results file the UI reads pass/fail and failure reasons from."""

import json
import logging
from pathlib import Path
from unittest.mock import Mock

import pytest

from neuro_san_studio.network_consultant import fixture_runner
from neuro_san_studio.network_consultant.fixture_runner import FixtureRunner


class TestFixtureResults:
    """Test fixture results."""

    @staticmethod
    def _job(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
        """Configure and return one temporary nsflow results file."""
        monkeypatch.setattr(fixture_runner, "NSFLOW_JOB_ID", "job1")
        monkeypatch.setattr(fixture_runner, "NSFLOW_JOB_DIR", str(tmp_path))
        return tmp_path / "job1.results.json"

    @staticmethod
    def test_a_subset_round_keeps_the_verdicts_it_did_not_re_run(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The whole point of merging: the runner re-tests only what was failing, and a re-check
        of one fixture says nothing about the others -- they must not vanish from the UI."""
        path = TestFixtureResults._job(monkeypatch, tmp_path)
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
        assert set(recorded) == {"a.hocon", "b.hocon"}
        assert recorded.get("a.hocon", {}).get("passed") is True
        assert recorded.get("b.hocon", {}).get("passed") is True
        assert recorded.get("b.hocon", {}).get("message") is None

    @staticmethod
    def test_failure_reason_and_infrastructure_flag_survive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Failure details survive serialization to the UI results file."""
        path = TestFixtureResults._job(monkeypatch, tmp_path)
        FixtureRunner.write_fixture_results(
            [{"fixture": "c.hocon", "passed": False, "message": "TIMEOUT_ISSUE: ...", "infrastructure_error": True}]
        )
        recorded = json.loads(path.read_text(encoding="utf-8")).get("c.hocon")
        assert recorded == {"passed": False, "message": "TIMEOUT_ISSUE: ...", "infrastructure_error": True}

    @staticmethod
    def test_no_file_written_outside_an_nsflow_job(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Plain CLI use must not litter -- and has nowhere to write to anyway."""
        monkeypatch.setattr(fixture_runner, "NSFLOW_JOB_ID", None)
        monkeypatch.setattr(fixture_runner, "NSFLOW_JOB_DIR", str(tmp_path))
        FixtureRunner.write_fixture_results([{"fixture": "a.hocon", "passed": True}])
        assert not list(tmp_path.iterdir())

    @staticmethod
    def test_a_corrupt_file_does_not_fail_the_test_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """The runner may be mid-write when something else reads it; losing old verdicts beats
        raising out of a suite that has already finished running."""
        path = TestFixtureResults._job(monkeypatch, tmp_path)
        path.write_text("{not json", encoding="utf-8")
        FixtureRunner.write_fixture_results([{"fixture": "a.hocon", "passed": True}])
        recorded = json.loads(path.read_text(encoding="utf-8")).get("a.hocon", {})
        assert recorded.get("passed") is True

    @staticmethod
    def test_provider_api_key_error_is_an_infrastructure_failure(monkeypatch: pytest.MonkeyPatch) -> None:
        """Provider credential failures remain distinct from network behavior failures."""
        driver = Mock()

        def fail_with_api_key_error(_fixture_path: str) -> None:
            """Emit the provider marker before the driver reports its resulting assertion."""
            logging.getLogger("provider").error("API KEY error detected: invalid credential")
            raise AssertionError("response did not satisfy the fixture")

        driver.one_test.side_effect = fail_with_api_key_error
        monkeypatch.setattr(FixtureRunner, "_create_driver", lambda _asserts, _fixture_name: driver)
        monkeypatch.setattr(FixtureRunner, "_write_consolidated_thinking", lambda _fixture_name, _started: None)

        result = FixtureRunner.run_fixture("tests/fixtures/example.hocon")

        assert result.get("infrastructure_error") is True
        assert "API KEY error detected: invalid credential" in result.get("message", "")
