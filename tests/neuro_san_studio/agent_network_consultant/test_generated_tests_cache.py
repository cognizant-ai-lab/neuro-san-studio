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

import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from neuro_san_studio.agent_network_consultant import generated_tests_cache
from neuro_san_studio.agent_network_consultant.fixture_runner import FixtureRunner
from neuro_san_studio.agent_network_consultant.generated_tests_cache import GeneratedTestsCache


class TestGeneratedTestsCache(TestCase):
    """Verify cached results and thinking traces are reused only when inputs match."""

    def setUp(self) -> None:
        """Create isolated cache, network, fixture, and thinking-trace paths."""
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        self.cache_dir = self.root / "cache"
        self.hocon_path = self.root / "network.hocon"
        self.fixture_path = self.root / "fixture.hocon"
        self.thinking_dir = self.root / "thinking"
        self.hocon_path.write_text('{"tools": []}', encoding="utf-8")
        self.fixture_path.write_text('{"agent": "network"}', encoding="utf-8")
        self.thinking_dir.mkdir()
        (self.thinking_dir / "fixture.txt").write_text("trace", encoding="utf-8")

    def test_save_and_load_restores_a_matching_baseline_once(self) -> None:
        """Restore matching results and thinking traces, then consume the cache."""
        results: list[dict[str, object]] = [{"fixture": "fixture.hocon", "passed": True}]
        with (
            patch.object(GeneratedTestsCache, "GENTESTS_CACHE_DIR", str(self.cache_dir)),
            patch.object(generated_tests_cache, "IMPROVEMENT_THINKING_DIR", str(self.thinking_dir)),
            patch.object(FixtureRunner, "fixture_paths", return_value=[str(self.fixture_path)]),
        ):
            GeneratedTestsCache.save("sample/network", str(self.hocon_path), results)
            shutil.rmtree(self.thinking_dir)

            loaded = GeneratedTestsCache.load("sample/network", str(self.hocon_path))
            consumed = GeneratedTestsCache.load("sample/network", str(self.hocon_path))

        self.assertEqual(results, loaded)
        self.assertIsNone(consumed)
        self.assertEqual("trace", (self.thinking_dir / "fixture.txt").read_text(encoding="utf-8"))

    def test_load_rejects_a_cache_after_fixture_content_changes(self) -> None:
        """Consume but do not reuse results whose fixture fingerprint is stale."""
        results: list[dict[str, object]] = [{"fixture": "fixture.hocon", "passed": True}]
        with (
            patch.object(GeneratedTestsCache, "GENTESTS_CACHE_DIR", str(self.cache_dir)),
            patch.object(generated_tests_cache, "IMPROVEMENT_THINKING_DIR", str(self.thinking_dir)),
            patch.object(FixtureRunner, "fixture_paths", return_value=[str(self.fixture_path)]),
        ):
            GeneratedTestsCache.save("sample/network", str(self.hocon_path), results)
            self.fixture_path.write_text('{"agent": "changed"}', encoding="utf-8")

            loaded = GeneratedTestsCache.load("sample/network", str(self.hocon_path))

        self.assertIsNone(loaded)

    def test_load_reports_and_consumes_malformed_cache_data(self) -> None:
        """Treat malformed cache JSON as a cache miss while reporting the parsing failure."""
        self.cache_dir.mkdir()
        results_path = self.cache_dir / "sample_network.json"
        results_path.write_text("{not json", encoding="utf-8")
        with (
            patch.object(GeneratedTestsCache, "GENTESTS_CACHE_DIR", str(self.cache_dir)),
            self.assertLogs(
                "neuro_san_studio.agent_network_consultant.generated_tests_cache", level="WARNING"
            ) as captured,
        ):
            loaded = GeneratedTestsCache.load("sample/network", str(self.hocon_path))

        self.assertIsNone(loaded)
        self.assertFalse(results_path.exists())
        self.assertIn("Could not read generated-tests cache", "\n".join(captured.output))

    def test_load_reports_a_cache_with_missing_required_fields(self) -> None:
        """Report a cache object that cannot provide a fingerprinted result list."""
        self.cache_dir.mkdir()
        results_path = self.cache_dir / "sample_network.json"
        results_path.write_text("{}", encoding="utf-8")
        with (
            patch.object(GeneratedTestsCache, "GENTESTS_CACHE_DIR", str(self.cache_dir)),
            self.assertLogs(
                "neuro_san_studio.agent_network_consultant.generated_tests_cache", level="WARNING"
            ) as captured,
        ):
            loaded = GeneratedTestsCache.load("sample/network", str(self.hocon_path))

        self.assertIsNone(loaded)
        self.assertIn("required fields are missing", "\n".join(captured.output))

    def test_load_redacts_sensitive_messages_from_an_existing_cache(self) -> None:
        """Sanitize a cached failure before returning it to orchestration and logging code."""
        secret = "sk-proj-cached-secret-value"
        results: list[dict[str, object]] = [
            {"fixture": "fixture.hocon", "passed": False, "message": f"OPENAI_API_KEY={secret}"}
        ]
        with (
            patch.object(GeneratedTestsCache, "GENTESTS_CACHE_DIR", str(self.cache_dir)),
            patch.object(generated_tests_cache, "IMPROVEMENT_THINKING_DIR", str(self.thinking_dir)),
            patch.object(FixtureRunner, "fixture_paths", return_value=[str(self.fixture_path)]),
        ):
            GeneratedTestsCache.save("sample/network", str(self.hocon_path), results)
            loaded = GeneratedTestsCache.load("sample/network", str(self.hocon_path))

        self.assertIsNotNone(loaded)
        message = str((loaded or [{}])[0].get("message"))
        self.assertNotIn(secret, message)
        self.assertIn("[REDACTED]", message)

    def test_load_reports_a_thinking_trace_cleanup_failure(self) -> None:
        """Return the matching cache while reporting a failed best-effort trace cleanup."""
        results: list[dict[str, object]] = [{"fixture": "fixture.hocon", "passed": True}]
        with (
            patch.object(GeneratedTestsCache, "GENTESTS_CACHE_DIR", str(self.cache_dir)),
            patch.object(generated_tests_cache, "IMPROVEMENT_THINKING_DIR", str(self.thinking_dir)),
            patch.object(FixtureRunner, "fixture_paths", return_value=[str(self.fixture_path)]),
        ):
            GeneratedTestsCache.save("sample/network", str(self.hocon_path), results)
            with (
                patch.object(generated_tests_cache.shutil, "rmtree", side_effect=OSError("cleanup denied")),
                self.assertLogs(
                    "neuro_san_studio.agent_network_consultant.generated_tests_cache", level="WARNING"
                ) as captured,
            ):
                loaded = GeneratedTestsCache.load("sample/network", str(self.hocon_path))

        self.assertEqual(results, loaded)
        self.assertIn("cleanup denied", "\n".join(captured.output))
