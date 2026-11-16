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

"""Tests for one-shot generated-test result caching."""

import os
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.generated_tests_cache import GeneratedTestsCache
from neuro_san_studio.agent_network_consultant.thinking_trace_collector import ThinkingTraceCollector


class TestGeneratedTestsCache(TestCase):
    """Verify cached results and thinking traces are reused only when inputs match."""

    SOURCE_RUN_ID = "run-one"
    TARGET_RUN_ID = "run-two"
    NETWORK_NAME = "sample/network"

    def setUp(self) -> None:
        """Create isolated cache, network, fixture, and thinking-trace paths."""
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.job_directory = self.root / "agent_network_consultant_jobs"
        self.job_directory.mkdir()
        self.hocon_path = self.root / "network.hocon"
        self.fixture_path = self.root / "fixtures" / self.NETWORK_NAME / "fixture.hocon"
        self.fixture_path.parent.mkdir(parents=True)
        self.thinking_root = self.root / "thinking"
        self.hocon_path.write_text('{"tools": []}', encoding="utf-8")
        self.fixture_path.write_text('{"agent": "network"}', encoding="utf-8")
        source_trace_directory = self.thinking_root / self.SOURCE_RUN_ID
        source_trace_directory.mkdir(parents=True)
        (source_trace_directory / "fixture.txt").write_text("trace", encoding="utf-8")
        self.enterContext(
            patch.dict(
                os.environ,
                {"NSFLOW_JOB_ID": "job-1", "NSFLOW_JOB_DIR": str(self.job_directory)},
            )
        )
        self.source_cache = self._cache(self.SOURCE_RUN_ID)

    def _cache(self, run_id: str) -> GeneratedTestsCache:
        """
        Build a cache gateway for one run using real local fixture and trace paths.

        :param run_id: The unique Agent Network Consultant run identifier.
        :return: The configured cache gateway.
        """
        trace_collector = ThinkingTraceCollector(
            run_id,
            basis_directory="",
            output_directory=self.thinking_root,
        )
        fixture_runner = FixtureRunner(
            run_id,
            fixture_root=str(self.fixture_path.parents[2]),
            trace_collector=trace_collector,
        )
        return GeneratedTestsCache(
            run_id,
            fixture_runner=fixture_runner,
            trace_collector=trace_collector,
        )

    def _cache_paths(self) -> tuple[str, str]:
        """
        Return cache paths for the active isolated test job.

        :return: The result and thinking-trace cache paths.
        """
        paths = self.source_cache.paths(self.NETWORK_NAME)
        if paths is None:
            self.fail("The active test job did not resolve generated-test cache paths.")
        return paths

    def test_paths_are_project_local_and_isolated_by_job(self) -> None:
        """Keep independent nsflow jobs out of one another's cache files."""
        first_results_path, _first_thinking_path = self._cache_paths()

        with patch.dict(os.environ, {"NSFLOW_JOB_ID": "job-2"}):
            target_cache = self._cache(self.TARGET_RUN_ID)
            second_paths = target_cache.paths(self.NETWORK_NAME)
            if second_paths is None:
                self.fail("The second test job did not resolve generated-test cache paths.")
            second_results_path, _second_thinking_path = second_paths

        cache_directory = self.root / GeneratedTestsCache.CACHE_DIRECTORY_NAME
        self.assertEqual(cache_directory, Path(first_results_path).parent)
        self.assertEqual(cache_directory, Path(second_results_path).parent)
        self.assertNotEqual(first_results_path, second_results_path)

    def test_paths_are_unavailable_outside_an_nsflow_job(self) -> None:
        """Do not create a persistent cache for a direct terminal run."""
        with patch.dict(os.environ, {"NSFLOW_JOB_ID": ""}):
            paths = self._cache(self.SOURCE_RUN_ID).paths(self.NETWORK_NAME)

        self.assertIsNone(paths)

    def test_save_and_load_restores_a_matching_baseline_once(self) -> None:
        """Restore matching results and thinking traces, then consume the cache."""
        results: list[dict[str, object]] = [{"fixture": "fixture.hocon", "passed": True}]
        self.source_cache.save(self.NETWORK_NAME, str(self.hocon_path), results)
        shutil.rmtree(self.thinking_root / self.SOURCE_RUN_ID)

        with patch.dict(os.environ, {"NSFLOW_JOB_ID": "job-2"}):
            target_cache = self._cache(self.TARGET_RUN_ID)
            loaded = target_cache.load(self.NETWORK_NAME, str(self.hocon_path))
            consumed = target_cache.load(self.NETWORK_NAME, str(self.hocon_path))

        self.assertEqual(results, loaded)
        self.assertIsNone(consumed)
        restored_path = self.thinking_root / self.TARGET_RUN_ID / "fixture.txt"
        self.assertEqual("trace", restored_path.read_text(encoding="utf-8"))
        self.assertFalse((self.thinking_root / self.SOURCE_RUN_ID).exists())

    def test_load_rejects_a_cache_after_fixture_content_changes(self) -> None:
        """Consume but do not reuse results whose fixture fingerprint is stale."""
        results: list[dict[str, object]] = [{"fixture": "fixture.hocon", "passed": True}]
        self.source_cache.save(self.NETWORK_NAME, str(self.hocon_path), results)
        self.fixture_path.write_text('{"agent": "changed"}', encoding="utf-8")

        loaded = self.source_cache.load(self.NETWORK_NAME, str(self.hocon_path))

        self.assertIsNone(loaded)

    def test_load_reports_and_consumes_malformed_cache_data(self) -> None:
        """Treat malformed cache JSON as a reported cache miss."""
        results_path = Path(self._cache_paths()[0])
        results_path.write_text("{not json", encoding="utf-8")
        with self.assertLogs(
            "neuro_san_studio.agent_network_consultant.generated_tests_cache", level="INFO"
        ) as captured:
            loaded = self.source_cache.load(self.NETWORK_NAME, str(self.hocon_path))

        self.assertIsNone(loaded)
        self.assertFalse(results_path.exists())
        self.assertIn("Ignoring unreadable generated-tests cache", "\n".join(captured.output))

    def test_load_reports_a_cache_with_missing_required_fields(self) -> None:
        """Report a cache object that cannot provide a fingerprinted result list."""
        results_path = Path(self._cache_paths()[0])
        results_path.write_text("{}", encoding="utf-8")
        with self.assertLogs(
            "neuro_san_studio.agent_network_consultant.generated_tests_cache", level="INFO"
        ) as captured:
            loaded = self.source_cache.load(self.NETWORK_NAME, str(self.hocon_path))

        self.assertIsNone(loaded)
        self.assertIn("required fields are missing", "\n".join(captured.output))

    def test_load_redacts_sensitive_messages_from_an_existing_cache(self) -> None:
        """Sanitize a cached failure before returning it to orchestration and logging code."""
        secret = "sk-proj-cached-secret-value"
        results: list[dict[str, object]] = [
            {"fixture": "fixture.hocon", "passed": False, "message": f"OPENAI_API_KEY={secret}"}
        ]
        self.source_cache.save(self.NETWORK_NAME, str(self.hocon_path), results)

        loaded = self.source_cache.load(self.NETWORK_NAME, str(self.hocon_path))

        self.assertIsNotNone(loaded)
        message = str((loaded or [{}])[0].get("message"))
        self.assertNotIn(secret, message)
        self.assertIn("[REDACTED]", message)

    def test_save_redacts_sensitive_messages_before_persisting_the_cache(self) -> None:
        """Sanitize failure details before publishing a generated-test cache file."""
        secret = "sk-proj-cached-secret-value"
        results: list[dict[str, object]] = [
            {"fixture": "fixture.hocon", "passed": False, "message": f"OPENAI_API_KEY={secret}"}
        ]

        self.source_cache.save(self.NETWORK_NAME, str(self.hocon_path), results)

        persisted = Path(self._cache_paths()[0]).read_text(encoding="utf-8")
        self.assertNotIn(secret, persisted)
        self.assertIn("[REDACTED]", persisted)

    def test_load_reports_a_thinking_trace_cleanup_failure(self) -> None:
        """Return a matching cache while reporting a failed trace cleanup."""
        results: list[dict[str, object]] = [{"fixture": "fixture.hocon", "passed": True}]
        self.source_cache.save(self.NETWORK_NAME, str(self.hocon_path), results)
        with (
            patch.object(shutil, "rmtree", side_effect=OSError("cleanup denied")),
            self.assertLogs(
                "neuro_san_studio.agent_network_consultant.generated_tests_cache", level="WARNING"
            ) as captured,
        ):
            loaded = self.source_cache.load(self.NETWORK_NAME, str(self.hocon_path))

        self.assertEqual(results, loaded)
        self.assertIn("cleanup denied", "\n".join(captured.output))
